from pathlib import Path
import unittest

from src.evaluation.m20_evaluator_failure_diagnostics import M20EvaluatorDiagnosticStore, M20EvaluatorFailureDiagnostic
from src.evaluation.m20_harness import M20GuardedEvidenceDestination, M20IntegrityError
from tests.m20_memory_native_ops import MemoryNativeOps
from tests.m20_test_scratch import TemporaryDirectory


class GuardedEvaluatorDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.ops = MemoryNativeOps()
        evaluation = self.ops.provision(self.ops.root, "evaluation")
        results = self.ops.provision(evaluation, "results")
        self.destination_node = self.ops.provision(results, "m20_task_evaluator_feasibility_v2")
        self.diagnostics_node = self.ops.provision(self.destination_node, "private_evaluator_diagnostics")

    def destination(self, directory):
        root = Path(directory) / "repository"
        diagnostic = root / "evaluation" / "results" / "m20_task_evaluator_feasibility_v2" / "private_evaluator_diagnostics"
        diagnostic.mkdir(parents=True)
        return M20GuardedEvidenceDestination(str(root), ("evaluation", "results", "m20_task_evaluator_feasibility_v2", "private_evaluator_diagnostics"), diagnostic)

    @staticmethod
    def value(execution_id="a" * 64):
        return M20EvaluatorFailureDiagnostic(execution_id, "evaluator", "m20_evaluator_failure_diagnostic_v1",
            True, "pass", "present", "success", "complete", {"authority": "test"})

    @staticmethod
    def completed(execution_id, *, handoff=True):
        return ({"execution_id": execution_id, "telemetry": {"evaluator_handoff": handoff}},)

    def test_create_read_and_fresh_reopen_are_handle_relative(self):
        with TemporaryDirectory() as directory:
            destination = self.destination(directory)
            first = M20EvaluatorDiagnosticStore.guarded(destination, lambda: self.ops)
            first.persist(self.value()); self.assertEqual(first.load("a" * 64), self.value()); first.close()
            reopened = M20EvaluatorDiagnosticStore.guarded(destination, lambda: self.ops)
            reopened.validate_inventory(self.completed("a" * 64)); self.assertEqual(reopened.load("a" * 64), self.value()); reopened.close()
            self.assertFalse((destination.destination / (("a" * 64) + ".json")).exists())

    def test_foreign_malformed_reparse_and_io_fail_closed(self):
        with TemporaryDirectory() as directory:
            destination = self.destination(directory)
            self.ops.provision(self.diagnostics_node, "foreign.json", directory=False, data=b"{}")
            store = M20EvaluatorDiagnosticStore.guarded(destination, lambda: self.ops)
            with self.assertRaises(M20IntegrityError): store.validate_inventory(())
            store.close()
            self.ops.nodes[self.diagnostics_node].children.pop("foreign.json")
            self.ops.provision(self.diagnostics_node, "bad.json", reparse=True)
            with self.assertRaises(Exception): M20EvaluatorDiagnosticStore.guarded(destination, lambda: self.ops).validate_inventory(())

    def test_missing_required_and_optional_absence_are_distinguished(self):
        with TemporaryDirectory() as directory:
            destination = self.destination(directory)
            store = M20EvaluatorDiagnosticStore.guarded(destination, lambda: self.ops)
            with self.assertRaises(M20IntegrityError): store.validate_inventory(self.completed("b" * 64))
            store.validate_inventory(self.completed("c" * 64, handoff=False)); store.close()


if __name__ == "__main__": unittest.main()
