"""Deterministic composition evidence for M19 validation and closure."""

import unittest

from src.core.deliberation_state import DeliberationState, EpistemicSignal, EpistemicState, FailureRecoveryProjection, RecoveryEvent, RecoveryEventCategory, SignalAvailability, SignalSource
from src.core.meta_control_policy import MetaControlPolicy, MetaControlPolicyConfig, MetaControlPolicyInput, MetaControlRuntimeProjection, MetaDecisionType, RuntimeTerminalState
from src.core.meta_control_provenance import MetaControlExecutionTelemetry, MetaDecisionProvenance
from src.core.meta_control_runtime import MetaControlExecutionContext, MetaControlRuntimeIntegrator, MetaControlRuntimePhase, MetaControlRuntimeState
from src.core.resource_accounting import ResourceAllocation, ResourceDimension, ResourceState


def signal(value: float) -> EpistemicSignal:
    return EpistemicSignal(SignalAvailability.AVAILABLE, value, SignalSource.RUNTIME_DERIVED, "scale", "v1")


def config() -> MetaControlPolicyConfig:
    return MetaControlPolicyConfig("policy", "formalism", 0, 0, 0, 0, 0, 0, 1)


def compose(*, gain=2, task=1, action=1, stability=0, answer=False, action_available=True, observation_available=True, events=(), consumed=()):
    epistemic = EpistemicState(signal(0), signal(gain), signal(stability), signal(task), signal(action), "e", "et")
    deliberation = DeliberationState("runtime", epistemic, FailureRecoveryProjection(events, "h", "ht"), "d", "dt")
    resources = ResourceState(tuple(ResourceAllocation(kind, 1, int(kind in consumed)) for kind in ResourceDimension), "allocation", "r", "rt")
    policy_input = MetaControlPolicyInput(deliberation, resources, MetaControlRuntimeProjection("runtime", RuntimeTerminalState.ACTIVE, answer, action_available, observation_available, True))
    return policy_input, MetaControlRuntimeState(deliberation, resources, MetaControlRuntimePhase.ACTIVE, "state")


class M19ClosureTest(unittest.TestCase):
    def test_six_composed_decision_paths_have_exact_delta_and_evidence(self) -> None:
        cases = (
            (compose(), MetaDecisionType.OBSERVE, MetaControlExecutionContext("observe", acquire_observation=lambda: None), (0, 0, 1), False),
            (compose(gain=0, task=1, action=3, observation_available=False), MetaDecisionType.ACT, MetaControlExecutionContext("act", execute_action=lambda: None), (0, 1, 1), False),
            (compose(gain=1, task=0, action=0, action_available=False, observation_available=False), MetaDecisionType.CONTINUE_REASONING, MetaControlExecutionContext("reason", advance_reasoning=lambda: None), (1, 0, 0), False),
            (compose(events=(RecoveryEvent(RecoveryEventCategory.RECOVERABLE_FAILURE, "f"),)), MetaDecisionType.REPLAN, MetaControlExecutionContext("replan", replan=lambda: None), (1, 0, 0), False),
            (compose(answer=True), MetaDecisionType.ANSWER, MetaControlExecutionContext("answer", answer="answer"), (0, 0, 0), True),
            (compose(gain=0, task=-1, action=-1), MetaDecisionType.STOP, MetaControlExecutionContext("stop"), (0, 0, 0), True),
        )
        for (policy_input, runtime_state), expected, context, delta, terminal in cases:
            decision = MetaControlPolicy.decide(policy_input, config())
            self.assertEqual(decision.decision, expected)
            before = (policy_input.deliberation_state.to_dict(), policy_input.resource_state.to_dict())
            result = MetaControlRuntimeIntegrator.execute(decision, runtime_state, context)
            provenance = MetaDecisionProvenance.from_decision("decision", decision, "intent")
            telemetry = MetaControlExecutionTelemetry.from_execution(provenance, runtime_state, result)
            self.assertEqual(tuple(telemetry.resource_delta.to_dict().values()), delta)
            self.assertEqual(telemetry.terminal, terminal)
            self.assertEqual(before, (policy_input.deliberation_state.to_dict(), policy_input.resource_state.to_dict()))

    def test_adaptive_hard_and_rejected_paths_are_distinct_and_deterministic(self) -> None:
        adaptive_input, adaptive_runtime = compose(gain=0, task=0, action=0, stability=1)
        adaptive = MetaControlPolicy.decide(adaptive_input, config())
        self.assertEqual(adaptive, MetaControlPolicy.decide(adaptive_input, config()))
        self.assertEqual(adaptive.reason_code, "adaptive_stop")
        hard = MetaControlPolicy.decide(compose(consumed=tuple(ResourceDimension))[0], config())
        self.assertEqual(hard.reason_code, "hard_stop")
        rejected_input, rejected_runtime = compose(gain=0, task=1, action=3, observation_available=False)
        rejected = MetaControlRuntimeIntegrator.execute(MetaControlPolicy.decide(rejected_input, config()), rejected_runtime, MetaControlExecutionContext("reject"))
        self.assertEqual(rejected.outcome_code, "invalid_action_context")
        stopped = MetaControlRuntimeIntegrator.execute(adaptive, adaptive_runtime, MetaControlExecutionContext("stop"))
        self.assertIsNone(stopped.state.answer)


if __name__ == "__main__":
    unittest.main()
