"""Focused tests for the pure deterministic M19 meta-control policy."""

from dataclasses import replace
import unittest

from src.core.deliberation_state import DeliberationState, EpistemicSignal, EpistemicState, FailureRecoveryProjection, RecoveryEvent, RecoveryEventCategory, SignalAvailability, SignalSource
from src.core.meta_control_policy import MetaControlPolicy, MetaControlPolicyConfig, MetaControlPolicyInput, MetaControlRuntimeProjection, MetaDecisionType, RuntimeTerminalState
from src.core.resource_accounting import ResourceAllocation, ResourceDimension, ResourceState


def signal(value: float) -> EpistemicSignal:
    return EpistemicSignal(SignalAvailability.AVAILABLE, value, SignalSource.RUNTIME_DERIVED, "value", "v1")


def policy_input(*, gain=2.0, task=1.0, action=1.0, stability=0.0, runtime=None, events=(), exhausted=()) -> MetaControlPolicyInput:
    epistemic = EpistemicState(signal(0), signal(gain), signal(stability), signal(task), signal(action), "e1", "et1")
    deliberation = DeliberationState("runtime:1", epistemic, FailureRecoveryProjection(events, "h1", "ht1"), "d1", "dt1")
    allocations = tuple(ResourceAllocation(dimension, 1, int(dimension in exhausted)) for dimension in ResourceDimension)
    resources = ResourceState(allocations, "allocation:1", "r1", "rt1")
    runtime = runtime or MetaControlRuntimeProjection("runtime:1", RuntimeTerminalState.ACTIVE, False, True, True, True)
    return MetaControlPolicyInput(deliberation, resources, runtime)


def config() -> MetaControlPolicyConfig:
    return MetaControlPolicyConfig("policy:v1", "formalism:v1", 0, 0, 0, 0, 0, 0, 1)


class MetaControlPolicyTest(unittest.TestCase):
    def test_decision_space_and_semantic_branches(self) -> None:
        self.assertEqual(MetaControlPolicy.decide(policy_input(), config()).decision, MetaDecisionType.OBSERVE)
        no_observe = MetaControlRuntimeProjection("runtime:1", RuntimeTerminalState.ACTIVE, False, True, False, True)
        self.assertEqual(MetaControlPolicy.decide(policy_input(gain=0, task=1, action=3, runtime=no_observe), config()).decision, MetaDecisionType.ACT)
        no_action = MetaControlRuntimeProjection("runtime:1", RuntimeTerminalState.ACTIVE, False, False, False, True)
        self.assertEqual(MetaControlPolicy.decide(policy_input(runtime=no_action), config()).decision, MetaDecisionType.CONTINUE_REASONING)
        answer = MetaControlRuntimeProjection("runtime:1", RuntimeTerminalState.ACTIVE, True, True, True, True)
        self.assertEqual(MetaControlPolicy.decide(policy_input(runtime=answer), config()).decision, MetaDecisionType.ANSWER)
        recovery = (RecoveryEvent(RecoveryEventCategory.RECOVERABLE_FAILURE, "f1"),)
        self.assertEqual(MetaControlPolicy.decide(policy_input(events=recovery), config()).decision, MetaDecisionType.REPLAN)
        self.assertEqual(MetaControlPolicy.decide(policy_input(gain=0, task=-1, action=-1), config()).decision, MetaDecisionType.STOP)

    def test_hard_stop_precedes_answer_and_unrecoverable_failure(self) -> None:
        terminal = MetaControlRuntimeProjection("runtime:1", RuntimeTerminalState.TERMINAL, True, True, True, True)
        self.assertEqual(MetaControlPolicy.decide(policy_input(runtime=terminal), config()).decision, MetaDecisionType.STOP)
        failure = (RecoveryEvent(RecoveryEventCategory.UNRECOVERABLE_FAILURE, "f1"),)
        self.assertEqual(MetaControlPolicy.decide(policy_input(events=failure), config()).decision, MetaDecisionType.STOP)

    def test_hard_exhaustion_unknown_and_adaptive_stop_fail_closed(self) -> None:
        exhausted = tuple(ResourceDimension)
        self.assertEqual(MetaControlPolicy.decide(policy_input(exhausted=exhausted), config()).reason_code, "hard_stop")
        source = policy_input()
        unknown = replace(source.deliberation_state.epistemic_state, expected_information_gain=EpistemicSignal.unknown())
        unknown_input = replace(source, deliberation_state=replace(source.deliberation_state, epistemic_state=unknown))
        self.assertEqual(MetaControlPolicy.decide(unknown_input, config()).decision, MetaDecisionType.ACT)
        self.assertEqual(MetaControlPolicy.decide(policy_input(gain=0, task=0, action=0, stability=1), config()).reason_code, "adaptive_stop")

    def test_ties_are_deterministic_and_inputs_remain_unchanged(self) -> None:
        original = policy_input()
        before = (original.deliberation_state.to_dict(), original.resource_state.to_dict())
        first = MetaControlPolicy.decide(original, config())
        second = MetaControlPolicy.decide(original, config())
        self.assertEqual(first, second)
        self.assertEqual(first.decision, MetaDecisionType.OBSERVE)
        self.assertTrue(first.tie_break_applied)
        self.assertEqual(before, (original.deliberation_state.to_dict(), original.resource_state.to_dict()))
        self.assertEqual(original.resource_state.allocation(ResourceDimension.REASONING_STEP).consumed, 0)
        self.assertEqual(first.rule_code, "rule_6_8")


if __name__ == "__main__":
    unittest.main()
