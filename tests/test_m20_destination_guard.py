from __future__ import annotations

import unittest

from src.evaluation.m20_destination_guard import (
    M20DestinationGuard, M20DestinationGuardClosed, M20DestinationGuardState,
    M20DestinationGuardUnsupported, M20DestinationGuardViolation, M20DestinationIdentity,
    M20DestinationNativeError, WindowsNativeOps,
)


def identity(number: int, *, directory: bool = True, reparse: bool = False) -> M20DestinationIdentity:
    return M20DestinationIdentity(7, number.to_bytes(16, "big"), directory, reparse, 0xA0000003 if reparse else 0)


class FakeNativeOps:
    def __init__(self) -> None:
        self.root, self.components = object(), {"evaluation": object(), "results": object(), "v2": object()}
        self.identities = {self.root: identity(1), self.components["evaluation"]: identity(2),
                           self.components["results"]: identity(3), self.components["v2"]: identity(4)}
        self.children = {(self.root, "evaluation"): self.components["evaluation"],
                         (self.components["evaluation"], "results"): self.components["results"],
                         (self.components["results"], "v2"): self.components["v2"]}
        self.closed: list[object] = []; self.created: list[str] = []; self.writes: list[bytes] = []; self.renames: list[tuple[str, str, bool]] = []
        self.fail_create = self.fail_rename = self.fail_write = False

    def open_trusted_root(self, path):
        if path != r"C:\\synthetic": raise AssertionError("unexpected root")
        return self.root
    def open_relative_directory(self, parent, component): return self.children[(parent, component)]
    def identity(self, handle): return self.identities[handle]
    def close(self, handle): self.closed.append(handle)
    def create_exclusive(self, parent, leaf):
        if self.fail_create: raise OSError("create")
        self.created.append(leaf); return (parent, leaf)
    def write_flush(self, handle, data):
        if self.fail_write: raise OSError("write")
        self.writes.append(data)
    def rename_relative(self, parent, source, target, *, replace_existing):
        if self.fail_rename: raise OSError("rename")
        self.renames.append((source, target, replace_existing))


class UnsupportedOps(FakeNativeOps):
    def open_trusted_root(self, path):
        raise M20DestinationGuardUnsupported("mock unavailable")


class DestinationGuardTests(unittest.TestCase):
    def admitted(self):
        ops = FakeNativeOps()
        return ops, M20DestinationGuard.admit(r"C:\\synthetic", ("evaluation", "results", "v2"), ops)

    def test_admission_reopens_component_chain_and_closes_resources(self):
        ops, guard = self.admitted()
        self.assertEqual(guard.state, M20DestinationGuardState.ADMITTED)
        guard.check_intact(); guard.close(); guard.close()
        self.assertEqual(guard.state, M20DestinationGuardState.CLOSED)
        self.assertGreaterEqual(len(ops.closed), 7)

    def test_rejects_malformed_root_and_component(self):
        ops = FakeNativeOps()
        with self.assertRaises(M20DestinationGuardViolation): M20DestinationGuard.admit("relative", ("v2",), ops)
        with self.assertRaises(M20DestinationGuardViolation): M20DestinationGuard.admit(r"C:\\synthetic", ("..",), ops)
        with self.assertRaises(M20DestinationGuardViolation): M20DestinationGuard.admit(r"C:\\synthetic", ("a/b",), ops)

    def test_rejects_reparse_and_non_directory_identity(self):
        ops = FakeNativeOps(); ops.identities[ops.components["v2"]] = identity(4, reparse=True)
        with self.assertRaises(M20DestinationGuardViolation): M20DestinationGuard.admit(r"C:\\synthetic", ("evaluation", "results", "v2"), ops)
        self.assertIn(ops.root, ops.closed)

    def test_detects_ancestor_and_destination_replacement(self):
        ops, guard = self.admitted(); ops.identities[ops.components["evaluation"]] = identity(99)
        with self.assertRaises(M20DestinationGuardViolation): guard.check_intact()
        self.assertEqual(guard.state, M20DestinationGuardState.INVALIDATED)
        with self.assertRaises(M20DestinationGuardViolation): guard.create_exclusive("x.json")
        ops, guard = self.admitted(); ops.identities[ops.components["v2"]] = identity(100)
        with self.assertRaises(M20DestinationGuardViolation): guard.check_intact()

    def test_create_write_and_rename_are_handle_relative_in_the_fake_boundary(self):
        ops, guard = self.admitted(); handle = guard.create_exclusive("temp.json")
        guard.write_flush(handle, b"synthetic"); guard.rename_relative("temp.json", "final.json")
        self.assertEqual(ops.created, ["temp.json"]); self.assertEqual(ops.writes, [b"synthetic"])
        self.assertEqual(ops.renames, [("temp.json", "final.json", False)])

    def test_failed_create_rename_and_write_invalidate_without_path_fallback(self):
        for name in ("fail_create", "fail_rename", "fail_write"):
            ops, guard = self.admitted(); setattr(ops, name, True)
            with self.assertRaises(M20DestinationGuardViolation):
                if name == "fail_create": guard.create_exclusive("x.json")
                elif name == "fail_rename": guard.rename_relative("x.json", "y.json")
                else: guard.write_flush(object(), b"x")
            self.assertEqual(guard.state, M20DestinationGuardState.INVALIDATED)

    def test_closed_guard_and_unsupported_default_backend_fail_closed(self):
        ops, guard = self.admitted(); guard.close()
        with self.assertRaises(M20DestinationGuardClosed): guard.check_intact()
        with self.assertRaises(M20DestinationGuardUnsupported): M20DestinationGuard.admit(r"C:\\synthetic", ("v2",), UnsupportedOps())

    def test_native_failure_invalidates_and_write_failure_leaves_handle_to_caller(self):
        class NativeFailOps(FakeNativeOps):
            def create_exclusive(self, parent, leaf):
                raise M20DestinationNativeError("NtCreateFile(relative)", ntstatus=-1, io_status=-1)
        ops, guard = NativeFailOps(), None
        guard = M20DestinationGuard.admit(r"C:\\synthetic", ("evaluation", "results", "v2"), ops)
        with self.assertRaises(M20DestinationNativeError): guard.create_exclusive("x.json")
        self.assertEqual(guard.state, M20DestinationGuardState.INVALIDATED)
        ops, guard = self.admitted(); handle = object()
        class WriteNativeFailOps(FakeNativeOps):
            def write_flush(self, file_handle, data):
                raise M20DestinationNativeError("WriteFile", win32_error=5)
        ops = WriteNativeFailOps(); guard = M20DestinationGuard.admit(r"C:\\synthetic", ("evaluation", "results", "v2"), ops)
        with self.assertRaises(M20DestinationNativeError): guard.write_flush(handle, b"x")
        self.assertNotIn(handle, ops.closed)

    def test_native_abi_contract_has_flexible_rename_offset_and_no_pathname_backend_methods(self):
        self.assertEqual(WindowsNativeOps._FILE_RENAME_INFORMATION_HEADER.FileName.offset, 20)
        self.assertTrue(hasattr(WindowsNativeOps, "open_relative_directory"))
        self.assertTrue(hasattr(WindowsNativeOps, "rename_relative"))


if __name__ == "__main__":
    unittest.main()
