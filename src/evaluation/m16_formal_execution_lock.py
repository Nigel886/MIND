"""Atomic, explicit ownership for one formal M16 result namespace."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import time
import uuid


class FormalExecutionAlreadyActiveError(RuntimeError):
    """Raised before any formal provider or Agent work when ownership exists."""


class FormalExecutionStaleLockError(RuntimeError):
    """Raised when stale-lock recovery is not explicitly and safely verified."""


def _canonical_directory(directory: Path) -> str:
    return str(directory.resolve()).casefold()


def _lock_path(directory: Path, manifest_hash: str) -> Path:
    identity = hashlib.sha256(f"{_canonical_directory(directory)}|{manifest_hash}".encode("utf-8")).hexdigest()
    return directory.parent / ".m16_execution_locks" / f"{identity}.lock"


def _process_start_identity(pid: int) -> str | None:
    """Return a verifiable local process identity, or None when it is absent."""
    if pid < 1:
        return None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            created = wintypes.FILETIME(); exited = wintypes.FILETIME(); kernel = wintypes.FILETIME(); user = wintypes.FILETIME()
            if not ctypes.windll.kernel32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
                return None
            return str((created.dwHighDateTime << 32) | created.dwLowDateTime)
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    return "alive-unverified"


class M16FormalExecutionLock:
    """An exclusive lock held from preflight through formal-run shutdown."""

    def __init__(self, result_directory: str | Path, manifest_hash: str) -> None:
        self.result_directory = Path(result_directory)
        self.manifest_hash = manifest_hash
        self.path = _lock_path(self.result_directory, manifest_hash)
        self._nonce: str | None = None

    def acquire(self) -> "M16FormalExecutionLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        nonce = uuid.uuid4().hex
        metadata = {
            "schema_version": "m16-formal-execution-lock-v1",
            "result_directory": _canonical_directory(self.result_directory),
            "manifest_hash": self.manifest_hash,
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "process_start_identity": _process_start_identity(os.getpid()),
            "owner_nonce": nonce,
            "created_ns": time.time_ns(),
        }
        try:
            descriptor = os.open(str(self.path), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError as error:
            raise FormalExecutionAlreadyActiveError("FORMAL EXECUTION ALREADY ACTIVE") from error
        try:
            os.write(descriptor, json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        finally:
            os.close(descriptor)
        self._nonce = nonce
        return self

    def release(self) -> None:
        if self._nonce is None or not self.path.exists():
            return
        try:
            metadata = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if metadata.get("owner_nonce") == self._nonce:
            self.path.unlink()
        self._nonce = None

    def __enter__(self) -> "M16FormalExecutionLock":
        return self.acquire()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()


def recover_stale_lock(result_directory: str | Path, manifest_hash: str) -> Path:
    """Explicitly archive a conclusively dead local owner; never auto-take over."""
    directory = Path(result_directory)
    path = _lock_path(directory, manifest_hash)
    if not path.exists():
        raise FormalExecutionStaleLockError("no formal execution lock exists")
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FormalExecutionStaleLockError("lock metadata is not safely recoverable") from error
    if metadata.get("result_directory") != _canonical_directory(directory) or metadata.get("manifest_hash") != manifest_hash:
        raise FormalExecutionStaleLockError("lock does not belong to this formal experiment")
    if metadata.get("hostname") != socket.gethostname() or not isinstance(metadata.get("pid"), int):
        raise FormalExecutionStaleLockError("lock ownership cannot be locally verified")
    observed = _process_start_identity(metadata["pid"])
    if observed is not None and observed == metadata.get("process_start_identity"):
        raise FormalExecutionStaleLockError("formal execution owner is still active")
    if observed == "alive-unverified":
        raise FormalExecutionStaleLockError("lock ownership cannot be safely verified")
    archived = path.with_name(f"{path.name}.stale.{metadata.get('owner_nonce', 'unknown')}")
    os.replace(path, archived)
    return archived
