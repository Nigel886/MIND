"""Provider-free tests for M18 v2 pilot operational diagnostics."""
from __future__ import annotations

import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m18_shared_provider import M18ProviderTransportError
from src.evaluation.m18_v2_pilot_runner import M18V2PilotPlan, M18V2PilotRunner
from src.evaluation.m18_v2_provider_diagnostics import (
    M18V2ProviderDiagnostic, M18V2ProviderDiagnosticCategory,
    M18V2ProviderExecutionFailure, M18V2SystematicProviderStop,
    M18V2SystematicProviderStopEvent, canonical_provider_category,
    normalize_provider_failure,
    sanitize_diagnostic_value, sanitize_provider_message,
)
from src.evaluation.m18_v2_provenance import M18V2ResultRecord
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
        self.assertEqual(diagnostic.to_dict()["category"], "http_5xx")
        self.assertEqual(diagnostic.http_status, 503)
        self.assertEqual(diagnostic.logical_call_index, 2)
        self.assertTrue(diagnostic.retry_exhausted)

    def test_url_query_headers_free_text_and_structures_are_sanitized(self):
        secrets = ("diagnostic-secret", "sk-test-123", "BearerSecretXYZ", "supersecretvalue")
        text = sanitize_provider_message(
            "https://api.example.test/v1/chat?KEY=diagnostic-secret&api_key=sk-test-123&"
            "access_token=BearerSecretXYZ&mode=json#client_secret=supersecretvalue&view=public "
            "Authorization: Basic basic-secret X-API-Key: x-secret key=another-secret"
        )
        for secret in secrets + ("basic-secret", "x-secret", "another-secret"):
            self.assertNotIn(secret, text)
        self.assertIn("mode=json", text)
        self.assertIn("http_503", sanitize_provider_message("http_503 planner logical_call=2 transport_attempts=3"))
        self.assertEqual(sanitize_provider_message("missing required key in JSON object"), "missing required key in JSON object")
        structured = sanitize_diagnostic_value({
            "key": "diagnostic-secret", "headers": {"Authorization": "Bearer BearerSecretXYZ"},
            "items": [{"client_secret": "supersecretvalue"}, "https://x.test/?token=sk-test-123"],
        })
        rendered = json.dumps(structured, sort_keys=True)
        for secret in secrets:
            self.assertNotIn(secret, rendered)

    def test_diagnostic_constructor_and_result_persistence_cannot_bypass_sanitizer(self):
        diagnostic = M18V2ProviderDiagnostic(
            "http_503", "direct_tool_calling", "direct_decision", 1, 3, True,
            "https://example.test/fail?key=diagnostic-secret&mode=json Authorization: Bearer sk-test-123",
        )
        self.assertNotIn("diagnostic-secret", json.dumps(diagnostic.to_dict()))
        self.assertNotIn("sk-test-123", json.dumps(diagnostic.to_dict()))
        with TemporaryDirectory() as directory:
            runner = self.runner(Path(directory) / "pilot")
            expected = self.plan.expected[0]
            record = M18V2ResultRecord(expected, None, "provider_failure",
                {"logical_provider_calls": 1, "transport_attempts": 3}, None, diagnostic)
            persisted = runner.store.persist(record)
            on_disk = next(runner.result_root.glob("*.json")).read_text(encoding="utf-8")
            self.assertNotIn("diagnostic-secret", on_disk)
            self.assertNotIn("sk-test-123", on_disk)
            self.assertEqual(persisted.provider_diagnostic, runner.store.records()[0].provider_diagnostic)

    def test_untrusted_machine_fields_are_canonical_and_whole_objects_are_secret_free(self):
        secret = "diagnostic-secret"
        raw_corpus = (
            "http_503?key=" + secret,
            "invalid_request_error?token=" + secret,
            "code=" + secret,
            "type=" + secret,
            "stage?api_key=" + secret,
            "reason=" + secret,
        )
        diagnostic = M18V2ProviderDiagnostic(
            raw_corpus[0], "direct_tool_calling?token=" + secret,
            raw_corpus[4], 1, 3, True, " ".join(raw_corpus[1:]),
        )
        serialized = json.dumps(diagnostic.to_dict(), sort_keys=True)
        self.assertNotIn(secret, serialized)
        self.assertEqual(diagnostic.category, M18V2ProviderDiagnosticCategory.HTTP_5XX)
        self.assertEqual(diagnostic.http_status, 503)
        self.assertEqual(diagnostic.comparator, "unknown_comparator")
        self.assertEqual(diagnostic.stage, "unknown_provider_stage")
        equivalents = [canonical_provider_category(value) for value in (
            "http_503", "http_503?key=" + secret, "HTTP 503", "provider returned 503",
        )]
        self.assertEqual(equivalents, [(M18V2ProviderDiagnosticCategory.HTTP_5XX, 503)] * 4)
        unknown, status = canonical_provider_category("totally_new_provider_error?key=" + secret)
        self.assertEqual((unknown, status), (M18V2ProviderDiagnosticCategory.UNKNOWN_PROVIDER_ERROR, None))
        stop = M18V2SystematicProviderStopEvent(
            "direct_tool_calling", "direct_decision", "http_400?token=" + secret,
            ("run-1", "run-2"), 2, stopping_rule="reason=" + secret,
        )
        stop_serialized = json.dumps(stop.to_dict(), sort_keys=True)
        self.assertNotIn(secret, stop_serialized)
        self.assertEqual(stop.category.value, "systematic_provider_contract_failure")
        self.assertEqual(stop.provider_category, M18V2ProviderDiagnosticCategory.HTTP_4XX)
        self.assertEqual(stop.http_status, 400)
        self.assertEqual(
            stop.stopping_rule.value,
            "two_independent_structural_failures_same_comparator_stage_category_v1",
        )

    def test_malicious_structured_provider_values_cannot_escape_through_runner_output(self):
        secret = "diagnostic-secret"
        output, errors = StringIO(), StringIO()
        with TemporaryDirectory() as directory, redirect_stdout(output), redirect_stderr(errors):
            runner = self.runner(Path(directory) / "pilot")
            with self.assertRaises(M18V2SystematicProviderStop):
                runner.execute(provider_factory=lambda system: FailingProvider(
                    system, "http_400?type=" + secret + "&code=" + secret), limit=3)
        self.assertNotIn(secret, output.getvalue() + errors.getvalue())

    def test_transient_failure_is_persisted_and_does_not_stop(self):
        with TemporaryDirectory() as directory:
            runner = self.runner(Path(directory) / "pilot")
            records = runner.execute(provider_factory=lambda system: FailingProvider(system), limit=2)
            self.assertEqual(len(records), 2)
            self.assertTrue(all(record.failure_taxonomy == "provider_failure" for record in records))
            self.assertTrue(all(record.provider_diagnostic.category.value == "http_5xx" for record in records))
            self.assertIsNone(runner.store.systematic_stop())
            reread = runner.store.records()
            self.assertEqual([record.provider_diagnostic.to_dict() for record in reread], [record.provider_diagnostic.to_dict() for record in records])

    def test_repeated_contract_failure_persists_stop_and_blocks_restart(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "pilot"; runner = self.runner(root)
            secret = "diagnostic-secret"
            with self.assertRaises(M18V2SystematicProviderStop) as raised:
                runner.execute(provider_factory=lambda system: FailingProvider(system, "http_400?token=" + secret), limit=3)
            event = raised.exception.event
            self.assertEqual((event.comparator, event.stage, event.provider_category.value, event.category.value, event.evidence_count),
                             ("direct_tool_calling", "direct_decision", "http_4xx", "systematic_provider_contract_failure", 2))
            self.assertNotIn(secret, runner.store.systematic_stop_path.read_text(encoding="utf-8"))
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
