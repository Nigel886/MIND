"""Native-free contract tests for the remediated offline writer candidate."""
from __future__ import annotations

import ctypes
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest import mock

from src.evaluation import m20_destination_guard as guard_module
from src.evaluation.m20_destination_guard import (M20DestinationGuard, M20DestinationGuardViolation,
                                   M20DestinationIdentity, M20DestinationNativeError, WindowsNativeOps)
from src.evaluation.m20_harness import (GuardedEvidenceWriter, M20EvidenceStore, M20GuardedEvidenceDestination,
                         M20GuardedEvidenceWriterFactory, M20IntegrityError, M20LifecycleState,
                         M20Namespace, M20_RECORD_SCHEMA)
from src.evaluation.m20_prospective_feasibility import M20ProspectiveFeasibilityRunner


def directory_identity() -> M20DestinationIdentity:
    return M20DestinationIdentity(1, b"d" * 16, True, False)


def file_identity() -> M20DestinationIdentity:
    return M20DestinationIdentity(1, b"f" * 16, False, False)


class Ops:
    def __init__(self, *, write_error: BaseException | None = None,
                 rename_error: BaseException | None = None, source_bytes: bytes = b"{}") -> None:
        self.root, self.destination = object(), object()
        self.write_error, self.rename_error, self.source_bytes = write_error, rename_error, source_bytes
        self.closed: list[object] = []; self.creates: list[str] = []; self.renames: list[tuple[object, str, bool]] = []
        self.source_handle: object | None = None

    def open_trusted_root(self, _path: str) -> object: return self.root
    def open_relative_directory(self, _parent: object, _name: str) -> object: return object()
    def identity(self, handle: object) -> M20DestinationIdentity:
        return file_identity() if handle in getattr(self, "files", set()) else directory_identity()
    def close(self, handle: object) -> None: self.closed.append(handle)
    def create_exclusive(self, _parent: object, name: str) -> object:
        self.creates.append(name); handle = object(); self.files = getattr(self, "files", set()) | {handle}; return handle
    def write_flush(self, _handle: object, _data: bytes) -> None:
        if self.write_error is not None: raise self.write_error
    def rename_relative(self, _parent: object, source: str, target: str, *, replace_existing: bool) -> None:
        if self.rename_error is not None: raise self.rename_error
        self.renames.append((source, target, replace_existing))
    def open_relative_file(self, _parent: object, _name: str) -> object:
        self.source_handle = object(); self.files = getattr(self, "files", set()) | {self.source_handle}; return self.source_handle
    def read_file(self, handle: object, _maximum: int) -> bytes:
        assert handle is self.source_handle; return self.source_bytes
    def rename_open_file(self, handle: object, _parent: object, target: str, *, replace_existing: bool) -> None:
        if self.rename_error is not None: raise self.rename_error
        self.renames.append((handle, target, replace_existing))


def admitted_guard(ops: Ops) -> M20DestinationGuard:
    return M20DestinationGuard(ops, ops.root, (ops.destination,), ("evidence",), (directory_identity(),))


class RemediationContracts(unittest.TestCase):
    def writer(self, ops: Ops, root: Path) -> GuardedEvidenceWriter:
        return GuardedEvidenceWriter(root, admitted_guard(ops), identity=ops.identity, close_handle=ops.close)

    def test_created_file_access_mask_is_production_compatible(self) -> None:
        ops = object.__new__(WindowsNativeOps); ops._nt_create_relative = mock.Mock(return_value=7)
        ops.create_exclusive(3, "x.json")
        self.assertEqual(ops._nt_create_relative.call_args.kwargs["desired_access"],
                         ops._FILE_READ_ATTRIBUTES | ops._FILE_WRITE_DATA | ops._SYNCHRONIZE)

    def test_partial_source_open_uses_required_read_delete_access_without_write_sharing(self) -> None:
        ops = object.__new__(WindowsNativeOps); ops._nt_create_relative = mock.Mock(return_value=7)
        ops.open_relative_file(3, "x.partial.json")
        kwargs = ops._nt_create_relative.call_args.kwargs
        self.assertEqual(kwargs["desired_access"],
                         ops._FILE_READ_ATTRIBUTES | ops._FILE_READ_DATA | ops._DELETE | ops._SYNCHRONIZE)
        self.assertEqual(kwargs["share_access"], ops._FILE_SHARE_READ)

    def test_native_write_failure_preserves_original_error_and_closes_created_handle_once(self) -> None:
        with TemporaryDirectory() as directory:
            ops = Ops(write_error=M20DestinationNativeError("WriteFile", win32_error=5))
            writer = self.writer(ops, Path(directory).resolve())
            with self.assertRaisesRegex(M20DestinationNativeError, "WriteFile failed"):
                writer.write_new_atomic("marker.json", b"x")
            file_handles = [item for item in ops.closed if item in ops.files]
            self.assertEqual(len(file_handles), 1)
            self.assertEqual(ops.renames, [])

    def test_two_writes_share_one_admitted_guard_and_no_replace_rename(self) -> None:
        with TemporaryDirectory() as directory:
            ops = Ops(); writer = self.writer(ops, Path(directory).resolve())
            writer.write_new_atomic("one.json", b"1"); writer.write_new_atomic("two.json", b"2")
            self.assertEqual(len(ops.creates), 2)
            self.assertEqual([(item[1], item[2]) for item in ops.renames], [("one.json", False), ("two.json", False)])

    def test_guard_invalidation_during_write_and_rename_latches_writer(self) -> None:
        with TemporaryDirectory() as directory:
            for write_error, rename_error in ((M20DestinationGuardViolation("write"), None),
                                               (None, M20DestinationNativeError("Rename", win32_error=80))):
                ops = Ops(write_error=write_error, rename_error=rename_error)
                writer = self.writer(ops, Path(directory).resolve())
                with self.assertRaises(Exception): writer.write_new_atomic("x.json", b"x")
                with self.assertRaisesRegex(M20IntegrityError, "fail-closed"):
                    writer.write_new_atomic("y.json", b"y")

    def test_partial_read_validate_and_rename_uses_the_same_open_source_handle(self) -> None:
        payload = json.dumps({"lifecycle": M20LifecycleState.ZERO_COMMIT_PARTIAL.value,
                              "execution_id": "a" * 64, "spec": "a" * 64, "telemetry": {}}).encode()
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve(); ops = Ops(source_bytes=payload); writer = self.writer(ops, root)
            seen: list[bytes] = []
            writer.validate_and_rename_no_replace("a" * 64 + ".partial.json",
                                                  "a" * 64 + ".partial.resolved.json", seen.append)
            self.assertEqual(seen, [payload])
            self.assertIs(ops.renames[-1][0], ops.source_handle)
            self.assertEqual(ops.renames[-1][1:], ("a" * 64 + ".partial.resolved.json", False))
            self.assertEqual(ops.closed.count(ops.source_handle), 1)

    def test_partial_rename_collision_preserves_source_and_fails_closed(self) -> None:
        with TemporaryDirectory() as directory:
            ops = Ops(rename_error=M20DestinationNativeError("NtSetInformationFile", ntstatus=-1))
            writer = self.writer(ops, Path(directory).resolve())
            with self.assertRaises(M20DestinationNativeError):
                writer.validate_and_rename_no_replace("x.partial.json", "x.partial.resolved.json", lambda _value: None)
            self.assertEqual(ops.closed.count(ops.source_handle), 1)
            with self.assertRaisesRegex(M20IntegrityError, "fail-closed"):
                writer.validate_and_rename_no_replace("x.partial.json", "x.partial.resolved.json", lambda _value: None)

    def test_store_partial_resolution_uses_handle_bound_source_without_path_presence_check(self) -> None:
        execution_id = "a" * 64
        payload = json.dumps({"lifecycle": M20LifecycleState.ZERO_COMMIT_PARTIAL.value,
                              "execution_id": execution_id, "spec": execution_id, "telemetry": {}}).encode()
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve(); ops = Ops(source_bytes=payload); writer = self.writer(ops, root)
            store = M20EvidenceStore(root, SimpleNamespace(digest="d"), M20Namespace.FAKE, writer=writer)
            store.resume_partial(SimpleNamespace(namespace=M20Namespace.FAKE, manifest_digest="d", execution_id=execution_id))
            self.assertIs(ops.renames[-1][0], ops.source_handle)

    def test_factory_requires_fixed_preprovisioned_destination_and_admits_once(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve(); authority = M20GuardedEvidenceDestination(str(root.parent), (root.name,), root)
            ops = Ops(); factory = M20GuardedEvidenceWriterFactory(authority, ops_factory=lambda: ops)
            writer = factory(root)
            self.assertIsInstance(writer, GuardedEvidenceWriter)
            with self.assertRaises(M20IntegrityError): factory(root)
            with self.assertRaises(M20IntegrityError): factory(root.parent)
            missing = root / "missing"
            missing_authority = M20GuardedEvidenceDestination(str(root), ("missing",), missing)
            with self.assertRaises(M20IntegrityError):
                M20GuardedEvidenceWriterFactory(missing_authority, ops_factory=lambda: Ops())(missing)
            runner_factory = M20GuardedEvidenceWriterFactory(authority, ops_factory=lambda: Ops())
            runner = M20ProspectiveFeasibilityRunner(evidence_writer_factory=runner_factory)
            store = runner.store(root)
            store.close()

    def test_marker_failure_and_store_close_are_fail_closed_and_idempotent(self) -> None:
        class FailingWriter:
            def __init__(self, root: Path) -> None: self.destination, self.closed = root, 0
            def write_new_atomic(self, _name: str, _data: bytes) -> None: raise M20DestinationNativeError("WriteFile", win32_error=5)
            def rename_no_replace(self, *_args: object) -> None: raise AssertionError
            def validate_and_rename_no_replace(self, *_args: object) -> None: raise AssertionError
            def close(self) -> None: self.closed += 1
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve(); failing = FailingWriter(root)
            with self.assertRaises(M20DestinationNativeError):
                M20EvidenceStore(root, SimpleNamespace(digest="d"), M20Namespace.FAKE, writer=failing)
            self.assertEqual(failing.closed, 1)
            writer = type("Writer", (), {"destination": root, "write_new_atomic": lambda *_: None,
                                          "rename_no_replace": lambda *_: None,
                                          "validate_and_rename_no_replace": lambda *_: None,
                                          "close": lambda self: setattr(self, "closed", getattr(self, "closed", 0) + 1)})()
            store = M20EvidenceStore(root, SimpleNamespace(digest="d"), M20Namespace.FAKE, writer=writer)
            store.close(); store.close(); self.assertEqual(writer.closed, 1)
            with self.assertRaisesRegex(M20IntegrityError, "closed"):
                store.mark_partial(SimpleNamespace(namespace=M20Namespace.FAKE, manifest_digest="d", execution_id="z"), SimpleNamespace(reasoning_steps=0, tool_attempts=0, provider_interactions=0, decision_cycles=0, provider_transport_attempts=0))

    def test_cleanup_failure_does_not_replace_primary_failure(self) -> None:
        with TemporaryDirectory() as directory:
            ops = Ops(write_error=M20DestinationNativeError("WriteFile", win32_error=5))
            writer = GuardedEvidenceWriter(Path(directory).resolve(), admitted_guard(ops), identity=ops.identity,
                                           close_handle=lambda _handle: (_ for _ in ()).throw(M20DestinationNativeError("CloseHandle", win32_error=6)))
            with self.assertRaisesRegex(M20DestinationNativeError, "WriteFile failed") as raised:
                writer.write_new_atomic("x.json", b"x")
            self.assertTrue(any("cleanup failed" in note for note in getattr(raised.exception, "__notes__", [])))

    def test_runner_cleanup_preserves_primary_failure(self) -> None:
        class Store:
            def close(self) -> None: raise RuntimeError("close")
        try:
            try:
                raise ValueError("primary")
            finally:
                M20ProspectiveFeasibilityRunner._close_store_preserving_primary(Store())
        except ValueError as error:
            self.assertEqual(str(error), "primary")
            self.assertTrue(any("cleanup failed" in note for note in getattr(error, "__notes__", [])))
        else:
            self.fail("primary failure was replaced")


if __name__ == "__main__":
    unittest.main()
