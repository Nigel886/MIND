"""Fail-closed, Generation-v2 destination-identity guard core.

This module deliberately does *not* provide pathname persistence.  Its
``NativeDestinationOps`` boundary is backed by Windows directory-handle-relative
operations.  The ABI declarations are Host-static-reviewed only; Guest NTFS
validation is still required before any production integration.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from enum import Enum
import os
import re
import sys
from typing import Any, Callable, Protocol, Sequence


class M20DestinationGuardError(RuntimeError):
    """Base class for a v2 destination security failure."""


class M20DestinationGuardUnsupported(M20DestinationGuardError):
    """A required native capability is unavailable; callers must stop."""


class M20DestinationGuardViolation(M20DestinationGuardError):
    """A handle-derived identity, type, or reparse contract changed."""


class M20DestinationGuardClosed(M20DestinationGuardError):
    """The capability is closed or invalidated."""


class M20DestinationNativeError(M20DestinationGuardError):
    """A native operation failed with its original diagnostic status preserved."""

    def __init__(self, api: str, *, ntstatus: int | None = None,
                 io_status: int | None = None, win32_error: int | None = None) -> None:
        self.api, self.ntstatus, self.io_status, self.win32_error = api, ntstatus, io_status, win32_error
        details = ", ".join(f"{name}=0x{value & 0xFFFFFFFF:08x}" for name, value in
                            (("ntstatus", ntstatus), ("io_status", io_status)) if value is not None)
        if win32_error is not None:
            details = ", ".join(filter(None, (details, f"win32={win32_error}")))
        super().__init__(f"{api} failed" + (f" ({details})" if details else ""))


class M20DestinationGuardState(str, Enum):
    ADMITTED = "admitted"
    INVALIDATED = "invalidated"
    CLOSED = "closed"


@dataclass(frozen=True)
class M20DestinationIdentity:
    """Identity observed from one native handle, never from a mutable pathname."""
    volume_serial: int
    file_id: bytes
    is_directory: bool
    is_reparse_point: bool
    reparse_tag: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.volume_serial, int) or self.volume_serial < 0:
            raise ValueError("volume serial is invalid")
        if not isinstance(self.file_id, bytes) or len(self.file_id) != 16:
            raise ValueError("file id must be exactly 16 bytes")
        if not isinstance(self.reparse_tag, int) or not 0 <= self.reparse_tag <= 0xFFFFFFFF:
            raise ValueError("reparse tag is invalid")


class NativeDestinationOps(Protocol):
    """Narrow native boundary; every returned handle must be explicitly closed."""
    def open_trusted_root(self, absolute_path: str) -> Any: ...
    def open_relative_directory(self, parent_handle: Any, component: str) -> Any: ...
    def identity(self, handle: Any) -> M20DestinationIdentity: ...
    def close(self, handle: Any) -> None: ...
    def create_exclusive(self, parent_handle: Any, leaf_name: str) -> Any: ...
    def write_flush(self, file_handle: Any, data: bytes) -> None: ...
    def open_relative_file(self, parent_handle: Any, leaf_name: str) -> Any: ...
    def read_file(self, file_handle: Any, maximum_bytes: int) -> bytes: ...
    def rename_open_file(self, file_handle: Any, parent_handle: Any, target_name: str,
                         *, replace_existing: bool) -> None: ...
    def rename_relative(self, parent_handle: Any, source_name: str, target_name: str,
                        *, replace_existing: bool) -> None: ...


_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _component(value: str) -> str:
    if not isinstance(value, str) or not _SAFE_COMPONENT.fullmatch(value) or value in {".", ".."}:
        raise M20DestinationGuardViolation("destination component is not a safe single component")
    return value


class M20DestinationGuard:
    """A non-forgeable-at-call-site capability for one admitted v2 directory chain."""

    def __init__(self, ops: NativeDestinationOps, root_handle: Any, destination_handles: Sequence[Any],
                 components: Sequence[str], identities: Sequence[M20DestinationIdentity]) -> None:
        self._ops = ops
        self._root_handle = root_handle
        self._destination_handles = tuple(destination_handles)
        self._components = tuple(components)
        self._identities = tuple(identities)
        self._state = M20DestinationGuardState.ADMITTED

    @classmethod
    def admit(cls, trusted_root: str, destination_components: Sequence[str], ops: NativeDestinationOps | None = None) -> "M20DestinationGuard":
        """Open and pin an exact relative directory chain from a trusted root.

        A partial admission closes every opened handle.  The default Windows
        backend intentionally refuses unsupported relative operations rather
        than accepting a pathname fallback.
        """
        if not isinstance(trusted_root, str) or not trusted_root or not os.path.isabs(trusted_root):
            raise M20DestinationGuardViolation("trusted root must be an absolute path")
        components = tuple(_component(value) for value in destination_components)
        if not components:
            raise M20DestinationGuardViolation("destination must contain at least one component")
        native = WindowsNativeOps() if ops is None else ops
        root_handle: Any | None = None
        handles: list[Any] = []
        identities: list[M20DestinationIdentity] = []
        try:
            root_handle = native.open_trusted_root(trusted_root)
            root_identity = native.identity(root_handle)
            cls._require_directory(root_identity, "trusted root")
            parent = root_handle
            for component in components:
                child = native.open_relative_directory(parent, component)
                identity = native.identity(child)
                cls._require_directory(identity, component)
                handles.append(child)
                identities.append(identity)
                parent = child
            return cls(native, root_handle, handles, components, identities)
        except BaseException:
            for handle in reversed(handles):
                native.close(handle)
            if root_handle is not None:
                native.close(root_handle)
            raise

    @staticmethod
    def _require_directory(identity: M20DestinationIdentity, label: str) -> None:
        if not identity.is_directory:
            raise M20DestinationGuardViolation(f"{label} is not a directory")
        if identity.is_reparse_point:
            raise M20DestinationGuardViolation(f"{label} is a reparse point")

    @property
    def state(self) -> M20DestinationGuardState:
        return self._state

    def _usable(self) -> None:
        if self._state is M20DestinationGuardState.CLOSED:
            raise M20DestinationGuardClosed("destination guard is closed")
        if self._state is M20DestinationGuardState.INVALIDATED:
            raise M20DestinationGuardViolation("destination guard was invalidated")

    def _invalidate(self, message: str) -> None:
        self._state = M20DestinationGuardState.INVALIDATED
        raise M20DestinationGuardViolation(message)

    def _native_failure(self, error: M20DestinationGuardError) -> None:
        self._state = M20DestinationGuardState.INVALIDATED
        raise error

    def check_intact(self) -> None:
        """Reopen all admitted components relative to the pinned trusted root."""
        self._usable()
        parent = self._root_handle
        reopened: list[Any] = []
        try:
            for component, expected in zip(self._components, self._identities, strict=True):
                handle = self._ops.open_relative_directory(parent, component)
                reopened.append(handle)
                observed = self._ops.identity(handle)
                try:
                    self._require_directory(observed, component)
                except M20DestinationGuardViolation as error:
                    self._invalidate(str(error))
                if observed != expected:
                    self._invalidate(f"destination identity changed at {component}")
                parent = handle
        finally:
            for handle in reversed(reopened):
                self._ops.close(handle)

    def create_exclusive(self, leaf_name: str) -> Any:
        self._usable(); _component(leaf_name); self.check_intact()
        try:
            return self._ops.create_exclusive(self._destination_handles[-1], leaf_name)
        except M20DestinationGuardError as error:
            self._native_failure(error)
        except BaseException as error:
            self._invalidate(f"relative create failed: {type(error).__name__}")

    def write_flush(self, file_handle: Any, data: bytes) -> None:
        self._usable()
        if not isinstance(data, bytes):
            raise TypeError("guarded write data must be bytes")
        self.check_intact()
        try:
            self._ops.write_flush(file_handle, data)
        except M20DestinationGuardError as error:
            # The caller that received create_exclusive's handle owns exactly
            # one close, including native write/flush failures.
            self._native_failure(error)
        except BaseException as error:
            self._invalidate(f"guarded write/flush failed: {type(error).__name__}")

    def read_verified_then_rename(self, source_name: str, target_name: str,
                                  validator: Callable[[bytes], None], *, maximum_bytes: int) -> None:
        """Validate bytes from one opened source object, then rename that handle.

        The source is never reopened by pathname after validation.  This binds
        the validated source identity to the object passed to NtSetInformationFile.
        """
        self._usable(); _component(source_name); _component(target_name)
        if not isinstance(maximum_bytes, int) or not 0 < maximum_bytes <= 0xFFFFFFFF - 1:
            raise ValueError("maximum source bytes is invalid")
        handle: Any | None = None
        try:
            self.check_intact()
            handle = self._ops.open_relative_file(self._destination_handles[-1], source_name)
            observed = self._ops.identity(handle)
            self._require_ordinary_file(observed, source_name)
            payload = self._ops.read_file(handle, maximum_bytes)
            validator(payload)
            self.check_intact()
            self._ops.rename_open_file(handle, self._destination_handles[-1], target_name,
                                       replace_existing=False)
        except M20DestinationGuardError as error:
            self._native_failure(error)
        except BaseException as error:
            self._invalidate(f"guarded source validation/rename failed: {type(error).__name__}")
        finally:
            if handle is not None:
                primary = sys.exc_info()[1]
                try:
                    self._ops.close(handle)
                except BaseException as cleanup_error:
                    if primary is None:
                        raise
                    primary.add_note(f"source-handle cleanup failed: {type(cleanup_error).__name__}: {cleanup_error}")

    @staticmethod
    def _require_ordinary_file(identity: M20DestinationIdentity, label: str) -> None:
        if identity.is_directory or identity.is_reparse_point:
            raise M20DestinationGuardViolation(f"{label} is not an ordinary file")

    def rename_relative(self, source_name: str, target_name: str, *, replace_existing: bool = False) -> None:
        self._usable(); _component(source_name); _component(target_name); self.check_intact()
        try:
            self._ops.rename_relative(self._destination_handles[-1], source_name, target_name,
                                      replace_existing=replace_existing)
        except M20DestinationGuardError as error:
            self._native_failure(error)
        except BaseException as error:
            self._invalidate(f"relative rename failed: {type(error).__name__}")

    def close(self) -> None:
        if self._state is M20DestinationGuardState.CLOSED:
            return
        try:
            for handle in reversed(self._destination_handles):
                self._ops.close(handle)
        finally:
            self._ops.close(self._root_handle)
            self._state = M20DestinationGuardState.CLOSED

    def __enter__(self) -> "M20DestinationGuard":
        self._usable(); return self

    def __exit__(self, *_: object) -> None:
        self.close()


class WindowsNativeOps:
    """Windows handle-relative ABI backend; never falls back to pathname I/O.

    ``NtCreateFile`` performs component opens/create relative to a retained
    directory handle.  ``NtSetInformationFile(FileRenameInformation)`` binds a
    same-directory target name to that same retained directory handle.  The
    implementation is deliberately minimal: cross-directory moves, arbitrary
    security descriptors, and recovery cleanup are unsupported.
    """
    _FILE_READ_ATTRIBUTES = 0x80
    _FILE_READ_DATA = 0x1
    _FILE_TRAVERSE = 0x20
    _FILE_WRITE_DATA = 0x2
    _DELETE = 0x00010000
    _SYNCHRONIZE = 0x00100000
    _FILE_SHARE_READ = 0x1
    _FILE_SHARE_WRITE = 0x2
    _OPEN_EXISTING = 3
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _FILE_ID_INFO_CLASS = 18
    _FILE_ATTRIBUTE_TAG_INFO_CLASS = 9
    _FILE_OPEN = 1
    _FILE_CREATE = 2
    _FILE_DIRECTORY_FILE = 0x1
    _FILE_SYNCHRONOUS_IO_NONALERT = 0x20
    _FILE_NON_DIRECTORY_FILE = 0x40
    _FILE_OPEN_REPARSE_POINT = 0x00200000
    _FILE_RENAME_INFORMATION = 10
    _OBJ_CASE_INSENSITIVE = 0x40
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    _MAX_GUARDED_SOURCE_BYTES = 1024 * 1024

    class _FILE_ID_INFO(ctypes.Structure):
        _fields_ = [("VolumeSerialNumber", ctypes.c_ulonglong), ("FileId", ctypes.c_ubyte * 16)]

    class _FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
        _fields_ = [("FileAttributes", ctypes.c_ulong), ("ReparseTag", ctypes.c_ulong)]

    class _UNICODE_STRING(ctypes.Structure):
        _fields_ = [("Length", ctypes.c_ushort), ("MaximumLength", ctypes.c_ushort),
                    ("Buffer", ctypes.c_void_p)]

    class _OBJECT_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Length", ctypes.c_ulong), ("RootDirectory", ctypes.c_void_p),
                    # Stored as an explicit pointer because nested ctypes class
                    # namespaces cannot resolve a sibling structure name.
                    ("ObjectName", ctypes.c_void_p), ("Attributes", ctypes.c_ulong),
                    ("SecurityDescriptor", ctypes.c_void_p), ("SecurityQualityOfService", ctypes.c_void_p)]

    class _IO_STATUS_BLOCK(ctypes.Structure):
        _fields_ = [("Status", ctypes.c_long), ("Information", ctypes.c_size_t)]

    class _FILE_RENAME_INFORMATION_HEADER(ctypes.Structure):
        _fields_ = [("ReplaceIfExists", ctypes.c_ubyte), ("_pad", ctypes.c_ubyte * 7),
                    ("RootDirectory", ctypes.c_void_p), ("FileNameLength", ctypes.c_ulong),
                    ("FileName", ctypes.c_ushort * 1)]

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise M20DestinationGuardUnsupported("Windows destination guard is unavailable on this platform")
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
        self._kernel32.CreateFileW.argtypes = (ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong,
                                               ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong,
                                               ctypes.c_void_p)
        self._kernel32.CreateFileW.restype = ctypes.c_void_p
        self._kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        self._kernel32.CloseHandle.restype = ctypes.c_int
        self._kernel32.GetFileInformationByHandleEx.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong)
        self._kernel32.GetFileInformationByHandleEx.restype = ctypes.c_int
        self._kernel32.WriteFile.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong,
                                             ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p)
        self._kernel32.WriteFile.restype = ctypes.c_int
        self._kernel32.FlushFileBuffers.argtypes = (ctypes.c_void_p,)
        self._kernel32.FlushFileBuffers.restype = ctypes.c_int
        self._kernel32.ReadFile.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong,
                                            ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p)
        self._kernel32.ReadFile.restype = ctypes.c_int
        self._ntdll.NtCreateFile.argtypes = (ctypes.POINTER(ctypes.c_void_p), ctypes.c_ulong,
            ctypes.POINTER(self._OBJECT_ATTRIBUTES), ctypes.POINTER(self._IO_STATUS_BLOCK), ctypes.c_void_p,
            ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong)
        self._ntdll.NtCreateFile.restype = ctypes.c_long
        self._ntdll.NtSetInformationFile.argtypes = (ctypes.c_void_p, ctypes.POINTER(self._IO_STATUS_BLOCK),
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int)
        self._ntdll.NtSetInformationFile.restype = ctypes.c_long

    def open_trusted_root(self, absolute_path: str) -> int:
        handle = self._kernel32.CreateFileW(absolute_path, self._FILE_READ_ATTRIBUTES,
            self._FILE_SHARE_READ | self._FILE_SHARE_WRITE, None, self._OPEN_EXISTING,
            self._FILE_FLAG_BACKUP_SEMANTICS | self._FILE_FLAG_OPEN_REPARSE_POINT, None)
        if handle == self._INVALID_HANDLE_VALUE:
            raise M20DestinationGuardUnsupported(f"CreateFileW trusted-root open failed: {ctypes.get_last_error()}")
        return int(handle)

    def identity(self, handle: int) -> M20DestinationIdentity:
        file_id, attributes = self._FILE_ID_INFO(), self._FILE_ATTRIBUTE_TAG_INFO()
        if not self._kernel32.GetFileInformationByHandleEx(handle, self._FILE_ID_INFO_CLASS, ctypes.byref(file_id), ctypes.sizeof(file_id)):
            raise M20DestinationGuardUnsupported(f"FileIdInfo failed: {ctypes.get_last_error()}")
        if not self._kernel32.GetFileInformationByHandleEx(handle, self._FILE_ATTRIBUTE_TAG_INFO_CLASS, ctypes.byref(attributes), ctypes.sizeof(attributes)):
            raise M20DestinationGuardUnsupported(f"FileAttributeTagInfo failed: {ctypes.get_last_error()}")
        return M20DestinationIdentity(int(file_id.VolumeSerialNumber), bytes(file_id.FileId),
            bool(attributes.FileAttributes & 0x10), bool(attributes.FileAttributes & 0x400), int(attributes.ReparseTag))

    def close(self, handle: int) -> None:
        if not self._kernel32.CloseHandle(handle):
            raise M20DestinationNativeError("CloseHandle", win32_error=ctypes.get_last_error())

    @staticmethod
    def _name(value: str) -> tuple[Any, _UNICODE_STRING]:
        _component(value)
        encoded = value.encode("utf-16-le")
        buffer = ctypes.create_unicode_buffer(value)
        unicode = WindowsNativeOps._UNICODE_STRING(len(encoded), len(encoded) + 2,
            ctypes.cast(buffer, ctypes.c_void_p))
        return buffer, unicode

    def _nt_create_relative(self, parent_handle: int, name: str, *, desired_access: int,
                            disposition: int, options: int, share_access: int | None = None) -> int:
        buffer, unicode = self._name(name)
        attributes = self._OBJECT_ATTRIBUTES(ctypes.sizeof(self._OBJECT_ATTRIBUTES), parent_handle,
            ctypes.cast(ctypes.pointer(unicode), ctypes.c_void_p), self._OBJ_CASE_INSENSITIVE, None, None)
        handle, iosb = ctypes.c_void_p(), self._IO_STATUS_BLOCK()
        share = self._FILE_SHARE_READ | self._FILE_SHARE_WRITE if share_access is None else share_access
        status = self._ntdll.NtCreateFile(ctypes.byref(handle), desired_access, ctypes.byref(attributes),
            ctypes.byref(iosb), None, 0, share,
            disposition, options, None, 0)
        # Keep ``buffer`` alive through the syscall.  Its value is intentionally unused.
        _ = buffer
        if status != 0:
            raise M20DestinationNativeError("NtCreateFile(relative)", ntstatus=int(status), io_status=int(iosb.Status))
        return int(handle.value)

    def open_relative_directory(self, parent_handle: int, component: str) -> int:
        return self._nt_create_relative(parent_handle, component,
            desired_access=self._FILE_READ_ATTRIBUTES | self._FILE_TRAVERSE | self._SYNCHRONIZE,
            disposition=self._FILE_OPEN,
            options=self._FILE_DIRECTORY_FILE | self._FILE_OPEN_REPARSE_POINT | self._FILE_SYNCHRONOUS_IO_NONALERT)

    def create_exclusive(self, parent_handle: int, leaf_name: str) -> int:
        return self._nt_create_relative(parent_handle, leaf_name,
            desired_access=self._FILE_READ_ATTRIBUTES | self._FILE_WRITE_DATA | self._SYNCHRONIZE,
            disposition=self._FILE_CREATE,
            options=self._FILE_NON_DIRECTORY_FILE | self._FILE_SYNCHRONOUS_IO_NONALERT)

    def open_relative_file(self, parent_handle: int, leaf_name: str) -> int:
        return self._nt_create_relative(parent_handle, leaf_name,
            desired_access=self._FILE_READ_ATTRIBUTES | self._FILE_READ_DATA | self._DELETE | self._SYNCHRONIZE,
            disposition=self._FILE_OPEN,
            options=self._FILE_NON_DIRECTORY_FILE | self._FILE_SYNCHRONOUS_IO_NONALERT,
            share_access=self._FILE_SHARE_READ)

    def read_file(self, file_handle: int, maximum_bytes: int) -> bytes:
        if not isinstance(maximum_bytes, int) or not 0 < maximum_bytes <= self._MAX_GUARDED_SOURCE_BYTES:
            raise M20DestinationGuardUnsupported("guarded source read size is invalid")
        buffer = ctypes.create_string_buffer(maximum_bytes + 1)
        read = ctypes.c_ulong()
        if not self._kernel32.ReadFile(file_handle, buffer, maximum_bytes + 1, ctypes.byref(read), None):
            raise M20DestinationNativeError("ReadFile", win32_error=ctypes.get_last_error())
        if read.value > maximum_bytes:
            raise M20DestinationGuardUnsupported("guarded source exceeds maximum size")
        return bytes(buffer.raw[:read.value])

    def rename_open_file(self, file_handle: int, parent_handle: int, target_name: str,
                         *, replace_existing: bool) -> None:
        encoded = _component(target_name).encode("utf-16-le")
        offset = self._FILE_RENAME_INFORMATION_HEADER.FileName.offset
        allocated = offset + len(encoded)
        raw = ctypes.create_string_buffer(allocated)
        header = ctypes.cast(raw, ctypes.POINTER(self._FILE_RENAME_INFORMATION_HEADER)).contents
        header.ReplaceIfExists = 1 if replace_existing else 0
        header.RootDirectory = parent_handle
        header.FileNameLength = len(encoded)
        ctypes.memmove(ctypes.addressof(raw) + offset, encoded, len(encoded))
        iosb = self._IO_STATUS_BLOCK()
        status = self._ntdll.NtSetInformationFile(file_handle, ctypes.byref(iosb), raw, allocated,
                                                   self._FILE_RENAME_INFORMATION)
        if status != 0:
            raise M20DestinationNativeError("NtSetInformationFile(FileRenameInformation)",
                                            ntstatus=int(status), io_status=int(iosb.Status))

    def write_flush(self, file_handle: int, data: bytes) -> None:
        if len(data) > 0xFFFFFFFF:
            raise M20DestinationGuardUnsupported("guarded write exceeds DWORD length")
        payload = ctypes.create_string_buffer(data)
        written = ctypes.c_ulong()
        if not self._kernel32.WriteFile(file_handle, payload, len(data), ctypes.byref(written), None):
            raise M20DestinationNativeError("WriteFile", win32_error=ctypes.get_last_error())
        if written.value != len(data):
            raise M20DestinationNativeError("WriteFile", win32_error=0)
        if not self._kernel32.FlushFileBuffers(file_handle):
            raise M20DestinationNativeError("FlushFileBuffers", win32_error=ctypes.get_last_error())

    def rename_relative(self, parent_handle: int, source_name: str, target_name: str,
                        *, replace_existing: bool) -> None:
        source = self._nt_create_relative(parent_handle, source_name,
            desired_access=self._DELETE | self._SYNCHRONIZE,
            disposition=self._FILE_OPEN,
            options=self._FILE_NON_DIRECTORY_FILE | self._FILE_SYNCHRONOUS_IO_NONALERT)
        try:
            self.rename_open_file(source, parent_handle, target_name, replace_existing=replace_existing)
        finally:
            self.close(source)
