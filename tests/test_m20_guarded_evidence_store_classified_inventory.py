"""Guarded v2 evidence inventory permits only its two control directories."""
from __future__ import annotations
from pathlib import Path
import unittest

from src.evaluation.m20_destination_guard import M20DestinationGuardViolation, M20DirectoryEntry
from src.evaluation.m20_harness import M20EvidenceStore, M20IntegrityError, M20Namespace
from src.evaluation.m20_prospective_feasibility import M20ProspectiveFeasibilityRunner, M20_FEASIBILITY_GENERATION_V2
from tests.m20_memory_native_ops import MemoryNativeOps
from tests.m20_test_scratch import TemporaryDirectory


class GuardedEvidenceStoreClassifiedInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve(); self.destination = self.root / "evidence"; self.destination.mkdir()
        self.ops = MemoryNativeOps(); self.evidence = self.ops.provision(self.ops.root, "evidence")
        self.runner = M20ProspectiveFeasibilityRunner(generation=M20_FEASIBILITY_GENERATION_V2); self.item = self.runner.work_items()[0]

    def store(self) -> M20EvidenceStore:
        writer = self.ops.factory(self.root, self.destination)(self.destination)
        return M20EvidenceStore(self.destination, self.runner.harness.manifest, M20Namespace.FEASIBILITY_V2, writer=writer)

    def add_controls(self, *names: str) -> None:
        for name in names: self.ops.provision(self.evidence, name)

    def test_both_allowlisted_directories_permit_record_reopen_without_host_evidence(self) -> None:
        store = self.store()
        record = self.runner._run(self.item, lambda *_: (_ for _ in ()).throw(TimeoutError("offline")), store)
        store.close(); self.add_controls(".m20_execution_control", "private_evaluator_diagnostics")
        reopened = self.store()
        self.assertEqual(reopened.completed_record(self.item.spec).execution_id, record.execution_id)
        self.assertFalse((self.destination / "manifest.json").exists())
        self.assertFalse((self.destination / (record.execution_id + ".json")).exists())
        reopened.close()

    def test_zero_or_one_allowlisted_directory_is_permitted(self) -> None:
        store = self.store(); store.close(); self.store().close()
        self.add_controls(".m20_execution_control"); self.store().close()

    def test_unknown_directory_reparse_directory_and_allowlisted_file_are_rejected(self) -> None:
        store = self.store(); store.close(); self.add_controls("unknown")
        with self.assertRaises(M20IntegrityError): self.store()
        self.ops.nodes[self.evidence].children.pop("unknown")
        self.ops.provision(self.evidence, "private_evaluator_diagnostics", reparse=True)
        with self.assertRaises(M20DestinationGuardViolation): self.store()
        self.ops.nodes[self.evidence].children.pop("private_evaluator_diagnostics")
        self.ops.provision(self.evidence, ".m20_execution_control", directory=False)
        with self.assertRaises(M20IntegrityError): self.store()

    def test_case_collision_and_unexpected_evidence_file_are_rejected(self) -> None:
        store = self.store(); store.close()
        self.ops.enumeration_override = (
            M20DirectoryEntry(".m20_execution_control", 44, True, False),
            M20DirectoryEntry(".M20_execution_control", 44, True, False),
        )
        with self.assertRaises(M20DestinationGuardViolation): self.store()
        self.ops.enumeration_override = None; self.ops.provision(self.evidence, "foreign.txt", directory=False)
        with self.assertRaises(M20IntegrityError): self.store()

    def test_read_enumeration_and_identity_failures_propagate(self) -> None:
        store = self.store(); self.ops.fail["enumerate"] = OSError("inventory")
        with self.assertRaises(M20DestinationGuardViolation): store.records()
        self.ops.fail.pop("enumerate"); store.close()
        store = self.store(); self.ops.provision(self.evidence, "a" * 64 + ".json", directory=False, data=b"{}")
        self.ops.fail["read"] = OSError("read")
        with self.assertRaises(M20DestinationGuardViolation): store.records()
        self.ops.fail.pop("read"); store.close()
        store = self.store(); self.ops.substitute(self.ops.root, "evidence", self.ops.mkdir_node())
        with self.assertRaises(M20DestinationGuardViolation): store.records()


if __name__ == "__main__":
    unittest.main()
