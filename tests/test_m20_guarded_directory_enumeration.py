"""Native-free contracts for retained-handle guarded directory inventories."""
from __future__ import annotations
from pathlib import Path
import unittest
from unittest.mock import patch

from src.evaluation.m20_destination_guard import (
    M20DestinationGuard, M20DestinationGuardClosed, M20DestinationGuardState,
    M20DestinationGuardViolation, M20DirectoryEntry,
)
from tests.m20_memory_native_ops import MemoryNativeOps


class GuardedDirectoryEnumerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ops = MemoryNativeOps()
        self.destination = self.ops.provision(self.ops.root, "evidence")

    def guard(self) -> M20DestinationGuard:
        return M20DestinationGuard.admit("X:/synthetic", ("evidence",), self.ops)

    def test_empty_directory_is_a_complete_empty_inventory(self) -> None:
        with self.guard() as guard:
            self.assertEqual(guard.enumerate_ordinary(), ())

    def test_ordinary_entries_are_deterministic_and_require_per_leaf_reads(self) -> None:
        self.ops.provision(self.destination, "z.json", directory=False, data=b"z")
        self.ops.provision(self.destination, "a.json", directory=False, data=b"a")
        with self.guard() as guard:
            names = guard.enumerate_ordinary()
            self.assertEqual(names, ("a.json", "z.json"))
            self.assertEqual({name: guard.read_ordinary(name, maximum_bytes=8) for name in names},
                             {"a.json": b"a", "z.json": b"z"})

    def test_closed_or_missing_retained_handle_fails_closed(self) -> None:
        guard = self.guard(); guard.close()
        with self.assertRaises(M20DestinationGuardClosed):
            guard.enumerate_ordinary()
        guard = self.guard(); self.ops.handles.clear()
        with self.assertRaises(M20DestinationGuardViolation):
            guard.enumerate_ordinary()
        self.assertEqual(guard.state, M20DestinationGuardState.INVALIDATED)

    def test_reparse_entry_is_rejected(self) -> None:
        self.ops.provision(self.destination, "link.json", directory=False, reparse=True)
        guard = self.guard()
        with self.assertRaises(M20DestinationGuardViolation): guard.enumerate_ordinary()
        self.assertEqual(guard.state, M20DestinationGuardState.INVALIDATED)

    def test_nonordinary_directory_entry_is_rejected(self) -> None:
        self.ops.provision(self.destination, "child")
        with self.assertRaises(M20DestinationGuardViolation): self.guard().enumerate_ordinary()

    def test_invalid_name_is_rejected(self) -> None:
        self.ops.provision(self.destination, "bad name", directory=False)
        with self.assertRaises(M20DestinationGuardViolation): self.guard().enumerate_ordinary()

    def test_duplicate_and_casefold_colliding_names_are_rejected(self) -> None:
        self.ops.enumeration_override = (
            M20DirectoryEntry("same.json", 18, False, False),
            M20DirectoryEntry("same.json", 18, False, False),
        )
        with self.assertRaises(M20DestinationGuardViolation): self.guard().enumerate_ordinary()
        self.ops.enumeration_override = (
            M20DirectoryEntry("A.json", 12, False, False),
            M20DirectoryEntry("a.json", 12, False, False),
        )
        with self.assertRaises(M20DestinationGuardViolation): self.guard().enumerate_ordinary()

    def test_entry_and_name_byte_limits_are_enforced(self) -> None:
        self.ops.provision(self.destination, "a.json", directory=False)
        self.ops.provision(self.destination, "b.json", directory=False)
        with self.assertRaises(M20DestinationGuardViolation):
            self.guard().enumerate_ordinary(maximum_entries=1)
        with self.assertRaises(M20DestinationGuardViolation):
            self.guard().enumerate_ordinary(maximum_name_bytes=10, maximum_entry_name_bytes=10)
        with self.assertRaises(M20DestinationGuardViolation):
            self.guard().enumerate_ordinary(maximum_name_bytes=64, maximum_entry_name_bytes=4)

    def test_mid_enumeration_failure_never_returns_partial_inventory(self) -> None:
        self.ops.provision(self.destination, "a.json", directory=False)
        self.ops.provision(self.destination, "b.json", directory=False)
        self.ops.fail["enumerate_mid"] = RuntimeError("synthetic midway failure")
        guard = self.guard()
        with self.assertRaises(M20DestinationGuardViolation): guard.enumerate_ordinary()
        self.assertEqual(guard.state, M20DestinationGuardState.INVALIDATED)

    def test_directory_identity_drift_after_query_is_rejected(self) -> None:
        self.ops.provision(self.destination, "a.json", directory=False)
        replacement = self.ops.mkdir_node()
        self.ops.on_enumerate = lambda: self.ops.substitute(self.ops.root, "evidence", replacement)
        guard = self.guard()
        with self.assertRaises(M20DestinationGuardViolation): guard.enumerate_ordinary()
        self.assertEqual(guard.state, M20DestinationGuardState.INVALIDATED)

    def test_entry_substitution_is_not_treated_as_validated_content(self) -> None:
        self.ops.provision(self.destination, "record.json", directory=False, data=b"before")
        guard = self.guard(); self.assertEqual(guard.enumerate_ordinary(), ("record.json",))
        replacement = self.ops.file_node(b"after", reparse=True)
        self.ops.substitute(self.destination, "record.json", replacement)
        with self.assertRaises(M20DestinationGuardViolation):
            guard.read_ordinary("record.json", maximum_bytes=16)

    def test_deleted_entry_after_query_is_not_treated_as_validated_content(self) -> None:
        self.ops.provision(self.destination, "record.json", directory=False, data=b"before")
        self.ops.on_enumerate = lambda: self.ops.nodes[self.destination].children.pop("record.json")
        with self.guard() as guard:
            self.assertEqual(guard.enumerate_ordinary(), ("record.json",))
            # A future store requiring this enumerated record must reject this
            # absence; inventory metadata never authorizes content access.
            self.assertIsNone(guard.read_ordinary("record.json", maximum_bytes=16))

    def test_enumeration_never_uses_host_path_apis(self) -> None:
        self.ops.provision(self.destination, "record.json", directory=False, data=b"ok")
        with patch.object(Path, "iterdir", side_effect=AssertionError("host enumeration")), \
             patch.object(Path, "glob", side_effect=AssertionError("host enumeration")), \
             patch.object(Path, "read_text", side_effect=AssertionError("host read")):
            with self.guard() as guard:
                self.assertEqual(guard.enumerate_ordinary(), ("record.json",))
                self.assertEqual(guard.read_ordinary("record.json", maximum_bytes=8), b"ok")


if __name__ == "__main__":
    unittest.main()
