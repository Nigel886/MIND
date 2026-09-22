"""Focused immutable M19 decision provenance and telemetry tests."""

from unittest import TestCase

from src.core.meta_control_policy import MetaDecision, MetaDecisionType
from src.core.meta_control_provenance import MetaControlExecutionTelemetry, MetaDecisionProvenance, ResourceDelta
from src.core.meta_control_runtime import MetaControlExecutionContext, MetaControlRuntimeIntegrator
from tests.test_meta_control_runtime import state


def decision(kind=MetaDecisionType.CONTINUE_REASONING):
    return MetaDecision(kind, "reason", "rule", "p1", "f1", "runtime", "deliberation", "resource")


class ProvenanceTest(TestCase):
    def test_decision_provenance_round_trips_without_private_text(self) -> None:
        record = MetaDecisionProvenance.from_decision("decision:1", decision(), "intent:1")
        self.assertEqual(MetaDecisionProvenance.from_dict(record.to_dict()), record)
        self.assertFalse(hasattr(record, "chain_of_thought"))

    def test_execution_telemetry_derives_reasoning_act_observe_and_terminal_deltas(self) -> None:
        cases = ((MetaDecisionType.CONTINUE_REASONING, MetaControlExecutionContext("next", advance_reasoning=lambda: None), (1, 0, 0)), (MetaDecisionType.ACT, MetaControlExecutionContext("next", execute_action=lambda: None), (0, 1, 1)), (MetaDecisionType.OBSERVE, MetaControlExecutionContext("next", acquire_observation=lambda: None), (0, 0, 1)), (MetaDecisionType.STOP, MetaControlExecutionContext("next"), (0, 0, 0)))
        for kind, context, expected in cases:
            pre = state(); provenance = MetaDecisionProvenance.from_decision("decision:1", decision(kind), "intent:1")
            telemetry = MetaControlExecutionTelemetry.from_execution(provenance, pre, MetaControlRuntimeIntegrator.execute(decision(kind), pre, context))
            self.assertEqual(tuple(telemetry.resource_delta.to_dict().values()), expected)
            self.assertEqual(MetaControlExecutionTelemetry.from_dict(telemetry.to_dict()), telemetry)

    def test_identity_and_delta_mismatches_fail_closed(self) -> None:
        pre = state(); result = MetaControlRuntimeIntegrator.execute(decision(), pre, MetaControlExecutionContext("next", advance_reasoning=lambda: None))
        wrong = MetaDecisionProvenance.from_decision("decision:1", decision(MetaDecisionType.ACT), "intent:1")
        with self.assertRaises(ValueError): MetaControlExecutionTelemetry.from_execution(wrong, pre, result)
        with self.assertRaises(ValueError): ResourceDelta.between(result.state.resource_state, pre.resource_state)
