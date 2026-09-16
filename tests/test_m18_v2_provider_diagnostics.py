"""Provider-free tests for M18 v2 pilot operational diagnostics."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m18_shared_provider import M18ProviderTransportError
from src.evaluation.m18_v2_pilot_runner import M18V2PilotPlan, M18V2PilotRunner
from src.evaluation.m18_v2_provider_diagnostics import (
    M18V2ProviderExecutionFailure, M18V2SystematicProviderStop,
    normalize_provider_failure, sanitize_provider_message,
)
from src.evaluation.m18_v2_runtime import M18V2PlanAdapter, M18V2ProviderCallGate
from src.evaluation.m18_v2_semantics import M18V2BudgetState
from src.evaluation.contracts import EvaluationFeedback, EvaluationFeedbackType


class FailingProvider:
    transport_attempts_per_logical_call = 3

    def __init__(self, system: str, category: str = "http_503") -> None:
        self.system, self.category = system, category

    def _fail(self):
        raise M18ProviderTransportError(self.category, 3, 1)

    def generate(self, request): self._fail()
    def plan(self, request): self._fail()
    def execute(self, request): self._fail()


class PlannerThenExecutorFailure(FailingProvider):
    def plan(self, request):
        tool_id = request.to_dict()["capabilities"][0]["tool_id"]
        return json.dumps({"steps": [{"step_id": "s0", "subgoal": "public", "capability_id": tool_id}]})


class ReplanFailureProvider(FailingProvider):
    def __init__(self):
        super().__init__("plan_and_execute")
        self.plan_calls = 0

    def plan(self, request):
        self.plan_calls += 1
        if self.plan_calls > 1:
            self._fail()
        tool_id = request.to_dict()["capabilities"][0]["tool_id"]
        return json.dumps({"steps": [{"step_id": "s0", "subgoal": "public", "capability_id": tool_id}]})

    def execute(self, request):
        tool_id = request.to_dict()["plan"]["steps"][0]["capability_id"]
        return json.dumps({"action": "tool_call", "tool_name": tool_id, "parameters": {}})


class M18V2ProviderDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = M18V2PilotPlan.from_repository(Path("."))

    def runner(self, root: Path) -> M18V2PilotRunner:
        return M18V2PilotRunner(self.plan, result_root=root)

    def test_sanitizer_retains_safe_categories_and_removes_credentials(self):
        value = sanitize_provider_message("http_503 Authorization: Bearer secret-token api_key=secret-key timeout")
        self.assertIn("http_503", value)
        self.assertIn("timeout", value)
        self.assertNotIn("secret-token", value)
        self.assertNotIn("secret-key", value)
        diagnostic = normalize_provider_failure(
            M18ProviderTransportError("http_503", 3, 2), comparator="direct_tool_calling",
            stage="direct_decision", logical_call_index=2, fallback_transport_attempts=3,
        )
        self.assertEqual(diagnostic.to_dict()["category"], "http_503")
        self.assertEqual(diagnostic.logical_call_index, 2)
        self.assertTrue(diagnostic.retry_exhausted)

    def test_transient_failure_is_persisted_and_does_not_stop(self):
        with TemporaryDirectory() as directory:
            runner = self.runner(Path(directory) / "pilot")
            records = runner.execute(provider_factory=lambda system: FailingProvider(system), limit=2)
            self.assertEqual(len(records), 2)
            self.assertTrue(all(record.failure_taxonomy == "provider_failure" for record in records))
            self.assertTrue(all(record.provider_diagnostic.category == "http_503" for record in records))
            self.assertIsNone(runner.store.systematic_stop())
            reread = runner.store.records()
            self.assertEqual([record.provider_diagnostic.to_dict() for record in reread], [record.provider_diagnostic.to_dict() for record in records])

    def test_repeated_contract_failure_persists_stop_and_blocks_restart(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "pilot"; runner = self.runner(root)
            with self.assertRaises(M18V2SystematicProviderStop) as raised:
                runner.execute(provider_factory=lambda system: FailingProvider(system, "http_400"), limit=3)
            event = raised.exception.event
            self.assertEqual((event.comparator, event.stage, event.category, event.evidence_count),
                             ("direct_tool_calling", "direct_decision", "http_400", 2))
            self.assertEqual(len(runner.store.records()), 2)
            with self.assertRaises(M18V2SystematicProviderStop):
                self.runner(root).execute(provider_factory=lambda system: FailingProvider(system), limit=1)

    def test_concrete_paths_preserve_stage(self):
        with TemporaryDirectory() as directory:
            runner = self.runner(Path(directory) / "pilot")
            # The ordered universe reaches direct, MIND, Plan planner, and ReAct.
            runner.execute(provider_factory=lambda system: FailingProvider(system), limit=16)
            diagnostics = {(record.provider_diagnostic.comparator, record.provider_diagnostic.stage)
                           for record in runner.store.records() if record.provider_diagnostic}
            self.assertIn(("direct_tool_calling", "direct_decision"), diagnostics)
            self.assertIn(("mind_lite_v11", "mind_policy"), diagnostics)
            self.assertIn(("plan_and_execute", "plan_planner"), diagnostics)
            self.assertIn(("react", "react_decision"), diagnostics)

    def test_plan_executor_failure_preserves_executor_stage(self):
        with TemporaryDirectory() as directory:
            runner = self.runner(Path(directory) / "pilot")
            records = runner.execute(provider_factory=lambda system: PlannerThenExecutorFailure(system), limit=11)
            diagnostic = next(record.provider_diagnostic for record in records
                              if record.provider_diagnostic and record.provider_diagnostic.comparator == "plan_and_execute")
            self.assertEqual(diagnostic.stage, "plan_executor")
            self.assertEqual(diagnostic.transport_attempts, 3)

    def test_plan_replan_failure_preserves_replan_stage(self):
        provider = ReplanFailureProvider()
        adapter = M18V2PlanAdapter(provider)
        adapter.initialize(self.plan.cases[0])
        gate = M18V2ProviderCallGate(M18V2BudgetState())
        initial = EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)
        adapter.next_decision(initial, M18V2BudgetState(), gate)
        recoverable = EvaluationFeedback(EvaluationFeedbackType.TOOL_FAILURE, {"category": "recoverable_failure"})
        with self.assertRaises(M18V2ProviderExecutionFailure) as raised:
            adapter.next_decision(recoverable, M18V2BudgetState(), gate)
        self.assertEqual(raised.exception.diagnostic.stage, "plan_replan")


if __name__ == "__main__":
    unittest.main()
