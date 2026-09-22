"""Focused M19 runtime-integration tests using local stub boundaries only."""

from unittest import TestCase

from src.core.deliberation_state import DeliberationState, EpistemicSignal, EpistemicState, FailureRecoveryProjection, SignalAvailability, SignalSource
from src.core.meta_control_policy import MetaDecision, MetaDecisionType
from src.core.meta_control_runtime import MetaControlExecutionContext, MetaControlRuntimeIntegrator, MetaControlRuntimePhase, MetaControlRuntimeState
from src.core.resource_accounting import ResourceAllocation, ResourceDimension, ResourceState


def state() -> MetaControlRuntimeState:
    signal = EpistemicSignal(SignalAvailability.AVAILABLE, 0, SignalSource.RUNTIME_DERIVED, "v", "v")
    deliberation = DeliberationState("r", EpistemicState(signal, signal, signal, signal, signal, "v", "t"), FailureRecoveryProjection((), "v", "t"), "v", "t")
    resources = ResourceState(tuple(ResourceAllocation(dimension, 1) for dimension in ResourceDimension), "a", "v", "t")
    return MetaControlRuntimeState(deliberation, resources, MetaControlRuntimePhase.ACTIVE, "t")


def decision(kind: MetaDecisionType) -> MetaDecision:
    return MetaDecision(kind, "reason", "rule", "policy", "formalism", "runtime", "deliberation", "resource")


class MetaControlRuntimeTest(TestCase):
    def test_all_six_decisions_and_exact_charges(self) -> None:
        calls: list[str] = []
        callbacks = {
            MetaDecisionType.CONTINUE_REASONING: MetaControlExecutionContext("next", advance_reasoning=lambda: calls.append("reason")),
            MetaDecisionType.REPLAN: MetaControlExecutionContext("next", replan=lambda: calls.append("replan")),
            MetaDecisionType.OBSERVE: MetaControlExecutionContext("next", acquire_observation=lambda: calls.append("observe")),
            MetaDecisionType.ACT: MetaControlExecutionContext("next", execute_action=lambda: calls.append("act")),
            MetaDecisionType.ANSWER: MetaControlExecutionContext("next", answer="answer"),
            MetaDecisionType.STOP: MetaControlExecutionContext("next"),
        }
        for kind, context in callbacks.items():
            result = MetaControlRuntimeIntegrator.execute(decision(kind), state(), context)
            self.assertIn(result.outcome_code, {"executed", "answer_committed", "stopped"})
        self.assertEqual(calls, ["reason", "replan", "observe", "act"])

    def test_exhaustion_rejection_failure_no_charge_and_terminal_consistency(self) -> None:
        original = state()
        exhausted = original.resource_state.consume(ResourceDimension.REASONING_STEP, 1, "used")
        blocked = MetaControlRuntimeIntegrator.execute(decision(MetaDecisionType.CONTINUE_REASONING), MetaControlRuntimeState(original.deliberation_state, exhausted, MetaControlRuntimePhase.ACTIVE, "t"), MetaControlExecutionContext("next", advance_reasoning=lambda: None))
        self.assertEqual(blocked.outcome_code, "resource_exhausted")
        self.assertEqual(blocked.state.resource_state, exhausted)
        rejected = MetaControlRuntimeIntegrator.execute(decision(MetaDecisionType.ACT), original, MetaControlExecutionContext("next"))
        self.assertEqual(rejected.outcome_code, "invalid_action_context")
        stopped = MetaControlRuntimeIntegrator.execute(decision(MetaDecisionType.STOP), original, MetaControlExecutionContext("next"))
        self.assertIsNone(stopped.state.answer)
        self.assertEqual(MetaControlRuntimeIntegrator.execute(decision(MetaDecisionType.ACT), stopped.state, MetaControlExecutionContext("later", execute_action=lambda: None)).outcome_code, "already_terminal")
