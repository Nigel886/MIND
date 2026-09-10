import unittest

from src.evaluation.contracts import EvaluationActionType
from src.evaluation.m16_diagnostic_telemetry import (
    DIAGNOSTIC_SCHEMA_VERSION, M16DiagnosticStage, M16DiagnosticTelemetry,
    diagnostic_run_id, validate_diagnostic_result_directory,
)
from src.evaluation.m16_failure_mechanism_audit import _resolver, _step_input, synthetic_task
from src.evaluation.m16_mind_session_adapter import M16MINDSessionEvaluationAdapter
from src.integration.llm_provider import ProviderFailure, ProviderFailureCategory, ProviderResponse
from src.integration.llm_session_admission import M13SessionAdmissionResolver
from src.integration.task_interpreter import TaskInterpreter


VALID = ProviderResponse({"intent": "synthetic", "required_capabilities": ["calculator"], "constraints": {}, "evidence": {}})


class M16DiagnosticTelemetryTests(unittest.TestCase):
    def _run(self, family, result=VALID, selected=True, sink=None, max_cycles=2):
        events = []
        telemetry = M16DiagnosticTelemetry(sink or events.append)
        provider, resolver = _resolver(result, selected)
        resolver = M13SessionAdmissionResolver(TaskInterpreter(provider), resolver._registry, telemetry)
        adapter = M16MINDSessionEvaluationAdapter(resolver, max_cycles=max_cycles, telemetry=telemetry)
        step = adapter.step(_step_input(synthetic_task(family)))
        return step, provider.calls, events

    def test_schema_and_identity_are_distinct_from_formal_ids(self):
        self.assertEqual(DIAGNOSTIC_SCHEMA_VERSION, "m16-mind-diagnostic-stage-v1")
        self.assertTrue(diagnostic_run_id("manifest", "case", 1).startswith("m16diag:v1:"))

    def test_direct_answer_off_on_equivalence_and_event_order(self):
        off, off_calls, _ = self._run("direct_answer", sink=lambda event: None)
        on, on_calls, events = self._run("direct_answer")
        self.assertEqual((off.to_dict(), off_calls), (on.to_dict(), on_calls))
        self.assertEqual(on.action.action_type, EvaluationActionType.ANSWER)
        self.assertEqual([event.stage_ordinal for event in events], list(range(1, len(events) + 1)))
        self.assertIn(M16DiagnosticStage.PROJECTED_ANSWER_ACTION, [event.stage_name for event in events])

    def test_calculator_off_on_equivalence(self):
        off, off_calls, _ = self._run("controlled_single_tool", sink=lambda event: object())
        on, on_calls, events = self._run("controlled_single_tool")
        self.assertEqual((off.to_dict(), off_calls), (on.to_dict(), on_calls))
        self.assertEqual(on.action.action_type, EvaluationActionType.TOOL_CALL)
        self.assertIn(M16DiagnosticStage.PROJECTED_TOOL_ACTION, [event.stage_name for event in events])

    def test_sink_failure_has_no_feedback_effect(self):
        def failed_sink(event): raise RuntimeError("synthetic observer failure")
        off, off_calls, _ = self._run("direct_answer", sink=lambda event: None)
        on, on_calls, _ = self._run("direct_answer", sink=failed_sink)
        self.assertEqual((off.to_dict(), off_calls), (on.to_dict(), on_calls))

    def test_failure_controls_are_observed_without_changing_fail_action(self):
        controls = (ProviderFailure(ProviderFailureCategory.UNAVAILABLE, {"reason": "synthetic"}), ProviderResponse({"missing": "intent"}), ProviderResponse({"intent": "synthetic", "required_capabilities": ["unknown"], "constraints": {}, "evidence": {}}))
        for result in controls:
            step, calls, events = self._run("direct_answer", result)
            self.assertEqual((step.action.action_type, calls), (EvaluationActionType.FAIL, 1))
            self.assertIn(M16DiagnosticStage.ADMISSION_FAILED, [event.stage_name for event in events])
            self.assertNotIn(M16DiagnosticStage.INTEGRATION_SELECTED, [event.stage_name for event in events])
            self.assertNotIn(M16DiagnosticStage.PRIVATE_TASK_PROJECTED, [event.stage_name for event in events])

    def test_malformed_response_preserves_behavior_and_records_received_before_decode_failure(self):
        malformed = ProviderResponse({"missing": "intent"})
        off, off_calls, _ = self._run("direct_answer", malformed, sink=lambda event: None)
        on, on_calls, events = self._run("direct_answer", malformed)
        self.assertEqual((off.to_dict(), off_calls), (on.to_dict(), on_calls))
        stages = [event.stage_name for event in events]
        self.assertEqual(
            stages[:3],
            [
                M16DiagnosticStage.PROVIDER_REQUEST_STARTED,
                M16DiagnosticStage.PROVIDER_RESPONSE_RECEIVED,
                M16DiagnosticStage.PROVIDER_DECODE_FAILURE,
            ],
        )

    def test_nonselection_and_max_cycle_failures_are_distinct_event_paths(self):
        step, _, events = self._run("direct_answer", ProviderResponse({"intent": "synthetic", "required_capabilities": [], "constraints": {}, "evidence": {}}), selected=False)
        self.assertEqual(step.action.action_type, EvaluationActionType.FAIL)
        self.assertIn(M16DiagnosticStage.META_INFERENCE_NOT_SELECTED, [event.stage_name for event in events])
        self.assertNotIn(M16DiagnosticStage.INTEGRATION_SELECTED, [event.stage_name for event in events])
        self.assertNotIn(M16DiagnosticStage.PRIVATE_TASK_PROJECTED, [event.stage_name for event in events])
        step, _, events = self._run("direct_answer", max_cycles=0)
        self.assertEqual(step.action.action_type, EvaluationActionType.FAIL)
        self.assertIn(M16DiagnosticStage.PRIVATE_SESSION_TERMINATED, [event.stage_name for event in events])

    def test_historical_namespaces_are_rejected(self):
        for path in ("evaluation/results/m16", "evaluation/results/m16_flash_lite", "evaluation/results/m16_deepseek_v4_flash", "evaluation/results/m16_deepseek_v4_flash_restart1"):
            with self.assertRaises(ValueError): validate_diagnostic_result_directory(path)
