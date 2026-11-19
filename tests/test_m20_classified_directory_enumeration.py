"""Native-free contracts for classified retained-handle directory inventory."""
from __future__ import annotations
from pathlib import Path
import unittest
from unittest.mock import patch

from src.evaluation.m20_destination_guard import (
    M20ClassifiedDirectoryEntry, M20DestinationGuard, M20DestinationGuardState,
    M20DestinationGuardViolation, M20DirectoryEntry,
)
from tests.m20_memory_native_ops import MemoryNativeOps


class ClassifiedDirectoryEnumerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ops = MemoryNativeOps(); self.destination = self.ops.provision(self.ops.root, "evidence")

    def guard(self) -> M20DestinationGuard:
        return M20DestinationGuard.admit("X:/synthetic", ("evidence",), self.ops)

    def test_mixed_files_and_directories_are_classified_deterministically(self) -> None:
        self.ops.provision(self.destination, "z.json", directory=False)
        self.ops.provision(self.destination, "private_evaluator_diagnostics")
        self.ops.provision(self.destination, ".m20_execution_control")
        with self.guard() as guard:
            result = guard.enumerate_classified()
            self.assertEqual(result, (
                M20ClassifiedDirectoryEntry(".m20_execution_control", 44, True, False),
                M20ClassifiedDirectoryEntry("private_evaluator_diagnostics", 58, True, False),
                M20ClassifiedDirectoryEntry("z.json", 12, False, False),
            ))

    def test_strict_ordinary_enumeration_still_rejects_directories(self) -> None:
        self.ops.provision(self.destination, "control")
        with self.assertRaises(M20DestinationGuardViolation): self.guard().enumerate_ordinary()

    def test_reparse_entries_and_unknown_types_are_rejected(self) -> None:
        self.ops.provision(self.destination, "link.json", directory=False, reparse=True)
        with self.assertRaises(M20DestinationGuardViolation): self.guard().enumerate_classified()
        self.ops.nodes[self.destination].children.pop("link.json")
        self.ops.provision(self.destination, "linkdir", reparse=True)
        with self.assertRaises(M20DestinationGuardViolation): self.guard().enumerate_classified()
        self.ops.nodes[self.destination].children.pop("linkdir")
        self.ops.enumeration_override = (M20DirectoryEntry("unknown", 14, "unknown", False),)
        with self.assertRaises(M20DestinationGuardViolation): self.guard().enumerate_classified()

    def test_duplicate_collision_invalid_name_and_bounds_are_rejected(self) -> None:
        self.ops.enumeration_override = (M20DirectoryEntry("A.json", 12, False, False),
                                         M20DirectoryEntry("a.json", 12, False, False))
        with self.assertRaises(M20DestinationGuardViolation): self.guard().enumerate_classified()
        self.ops.enumeration_override = (M20DirectoryEntry("bad name", 16, False, False),)
        with self.assertRaises(M20DestinationGuardViolation): self.guard().enumerate_classified()
        self.ops.enumeration_override = (M20DirectoryEntry("a.json", 12, False, False),
                                         M20DirectoryEntry("b.json", 12, True, False))
        with self.assertRaises(M20DestinationGuardViolation): self.guard().enumerate_classified(maximum_entries=1)
        with self.assertRaises(M20DestinationGuardViolation): self.guard().enumerate_classified(maximum_name_bytes=16,
                                                                                                  maximum_entry_name_bytes=16)

    def test_identity_drift_and_mid_enumeration_failure_are_fatal(self) -> None:
        self.ops.provision(self.destination, "a.json", directory=False)
        replacement = self.ops.mkdir_node(); self.ops.on_enumerate = lambda: self.ops.substitute(self.ops.root, "evidence", replacement)
        guard = self.guard()
        with self.assertRaises(M20DestinationGuardViolation): guard.enumerate_classified()
        self.assertEqual(guard.state, M20DestinationGuardState.INVALIDATED)
        self.ops.on_enumerate = None; self.ops.substitute(self.ops.root, "evidence", self.destination)
        self.ops.provision(self.destination, "b.json", directory=False); self.ops.fail["enumerate_mid"] = OSError("midway")
        with self.assertRaises(M20DestinationGuardViolation): self.guard().enumerate_classified()

    def test_classification_grants_no_traversal_and_leaf_type_changes_fail_read(self) -> None:
        self.ops.provision(self.destination, "private_evaluator_diagnostics")
        self.ops.provision(self.destination, "record.json", directory=False, data=b"before")
        with self.guard() as guard:
            entries = guard.enumerate_classified()
            directory = next(entry for entry in entries if entry.is_directory)
            self.assertFalse(hasattr(directory, "handle"))
            self.assertEqual(guard.read_ordinary("record.json", maximum_bytes=16), b"before")
            self.ops.substitute(self.destination, "record.json", self.ops.file_node(b"after", reparse=True))
            with self.assertRaises(M20DestinationGuardViolation): guard.read_ordinary("record.json", maximum_bytes=16)

    def test_classified_enumeration_never_uses_host_path_io(self) -> None:
        self.ops.provision(self.destination, "record.json", directory=False)
        with patch.object(Path, "iterdir", side_effect=AssertionError("host enumeration")), \
             patch.object(Path, "glob", side_effect=AssertionError("host enumeration")), \
             patch.object(Path, "read_text", side_effect=AssertionError("host read")):
            with self.guard() as guard:
                self.assertEqual(tuple(entry.name for entry in guard.enumerate_classified()), ("record.json",))


if __name__ == "__main__":
    unittest.main()
