"""Native-free guarded EvidenceStore read, inventory, and reopen contracts."""
from __future__ import annotations
from pathlib import Path
import unittest

from src.evaluation.m20_destination_guard import M20DestinationGuardViolation
from src.evaluation.m20_harness import M20EvidenceStore, M20IntegrityError, M20LifecycleState, M20Namespace, M20ResourceTelemetry
from src.evaluation.m20_prospective_feasibility import M20ProspectiveFeasibilityRunner
from tests.m20_memory_native_ops import MemoryNativeOps
from tests.m20_test_scratch import TemporaryDirectory


class GuardedEvidenceStoreReopenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.host_root = Path(self.temporary.name).resolve(); self.destination = self.host_root / "evidence"; self.destination.mkdir()
        self.ops = MemoryNativeOps(); self.evidence = self.ops.provision(self.ops.root, "evidence")
        self.runner = M20ProspectiveFeasibilityRunner(); self.item = self.runner.work_items()[0]

    def store(self) -> M20EvidenceStore:
        writer = self.ops.factory(self.host_root, self.destination)(self.destination)
        return M20EvidenceStore(self.destination, self.runner.harness.manifest, M20Namespace.FEASIBILITY, writer=writer)

    def persist_failed_record(self, store: M20EvidenceStore):
        return self.runner._run(self.item, lambda *_: (_ for _ in ()).throw(TimeoutError("offline")), store)

    def test_fresh_store_writes_and_reloads_manifest_without_host_evidence(self) -> None:
        store = self.store(); self.assertIn("manifest.json", self.ops.nodes[self.evidence].children); store.close()
        reopened = self.store(); self.assertEqual(reopened.records(), ()); self.assertFalse((self.destination / "manifest.json").exists()); reopened.close()

    def test_same_store_completed_record_read_and_inventory(self) -> None:
        store = self.store(); record = self.persist_failed_record(store)
        second_item = self.runner.work_items()[1]
        second = self.runner._run(second_item, lambda *_: (_ for _ in ()).throw(TimeoutError("offline")), store)
        self.assertEqual(store.completed_record(self.item.spec).execution_id, record.execution_id)
        self.assertEqual([value["execution_id"] for value in store.records()],
                         sorted((record.execution_id, second.execution_id)))
        self.assertEqual(tuple(self.destination.glob("*.json")), ())
        store.close()

    def test_fresh_factory_re_admits_closed_store_and_retrieves_record(self) -> None:
        store = self.store(); record = self.persist_failed_record(store); store.close()
        reopened = self.store(); self.assertEqual(reopened.completed_record(self.item.spec).execution_id, record.execution_id); reopened.close()

    def test_partial_and_resolved_partial_inventory_and_reconciliation(self) -> None:
        store = self.store(); store.mark_partial(self.item.spec, M20ResourceTelemetry())
        self.assertEqual(store.lifecycle(self.item.spec), M20LifecycleState.ZERO_COMMIT_PARTIAL)
        self.assertEqual(store.reconcile((self.item.spec,))["incomplete"], 1)
        store.resume_partial(self.item.spec); self.assertEqual(store.reconcile((self.item.spec,))["missing"], 0); store.close()
        reopened = self.store(); self.assertEqual(reopened.reconcile((self.item.spec,))["missing"], 0); reopened.close()

    def test_missing_required_completed_record_fails_closed(self) -> None:
        store = self.store()
        with self.assertRaises(M20IntegrityError): store.completed_record(self.item.spec)
        store.close()

    def test_unknown_reparse_and_nonordinary_entries_are_rejected(self) -> None:
        store = self.store(); store.close()
        self.ops.provision(self.evidence, "foreign.txt", directory=False)
        with self.assertRaises(M20IntegrityError): self.store()
        self.ops.nodes[self.evidence].children.pop("foreign.txt")
        self.ops.provision(self.evidence, "link.json", directory=False, reparse=True)
        with self.assertRaises(M20DestinationGuardViolation): self.store()
        self.ops.nodes[self.evidence].children.pop("link.json")
        self.ops.provision(self.evidence, "child")
        with self.assertRaises(M20IntegrityError): self.store()

    def test_enumeration_read_failure_and_identity_drift_propagate(self) -> None:
        store = self.store(); self.ops.fail["enumerate"] = OSError("offline enumerate")
        with self.assertRaises(M20DestinationGuardViolation): store.records()
        self.ops.fail.pop("enumerate"); store.close()
        store = self.store(); self.ops.provision(self.evidence, "a" * 64 + ".json", directory=False, data=b"{}")
        self.ops.fail["read"] = OSError("offline read")
        with self.assertRaises(M20DestinationGuardViolation): store.records()
        self.ops.fail.pop("read"); store.close()
        store = self.store(); self.ops.substitute(self.ops.root, "evidence", self.ops.mkdir_node())
        with self.assertRaises(M20DestinationGuardViolation): store.records()

    def test_factory_single_use_is_preserved_and_fresh_factory_is_required(self) -> None:
        factory = self.ops.factory(self.host_root, self.destination); first = factory(self.destination)
        with self.assertRaises(M20IntegrityError): factory(self.destination)
        first.close(); fresh = self.ops.factory(self.host_root, self.destination)(self.destination); fresh.close()

    def test_legacy_store_remains_path_based_only_when_no_guarded_writer_exists(self) -> None:
        legacy = self.host_root / "legacy"; store = M20EvidenceStore(legacy, self.runner.harness.manifest, M20Namespace.FEASIBILITY)
        self.assertTrue((legacy / "manifest.json").exists()); store.close()


if __name__ == "__main__":
    unittest.main()
