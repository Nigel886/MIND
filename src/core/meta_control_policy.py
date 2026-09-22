"""Pure deterministic M19 meta-control policy; no runtime execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from src.core.deliberation_state import (
    DeliberationState,
    RecoveryEventCategory,
    SignalAvailability,
)
from src.core.resource_accounting import ResourceDimension, ResourceState


class MetaDecisionType(str, Enum):
    CONTINUE_REASONING = "continue_reasoning"
    ACT = "act"
    OBSERVE = "observe"
    REPLAN = "replan"
    ANSWER = "answer"
    STOP = "stop"


class RuntimeTerminalState(str, Enum):
    ACTIVE = "active"
    ANSWER_TERMINAL = "answer_terminal"
    TERMINAL = "terminal"


def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _non_negative(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number")
    if not isfinite(float(value)) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return float(value)


@dataclass(frozen=True)
class MetaControlRuntimeProjection:
    """Minimal typed runtime projection required by the #210 decision relation."""

    identity: str
    terminal_state: RuntimeTerminalState
    answer_condition: bool
    action_available: bool
    observation_available: bool
    recovery_admissible: bool

    def __post_init__(self) -> None:
        _text(self.identity, "identity")
        if not isinstance(self.terminal_state, RuntimeTerminalState):
            raise TypeError("terminal_state must be a RuntimeTerminalState")
        for name in ("answer_condition", "action_available", "observation_available", "recovery_admissible"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be a bool")


@dataclass(frozen=True)
class MetaControlPolicyConfig:
    """Explicit, immutable symbolic parameters for the reference relation."""

    version: str
    formalism_version: str
    marginal_threshold: float
    diminishing_threshold: float
    reasoning_cost: float
    observation_cost: float
    action_cost: float
    recovery_penalty: float
    recovery_event_threshold: int

    def __post_init__(self) -> None:
        _text(self.version, "version")
        _text(self.formalism_version, "formalism_version")
        for name in ("marginal_threshold", "diminishing_threshold", "reasoning_cost", "observation_cost", "action_cost", "recovery_penalty"):
            object.__setattr__(self, name, _non_negative(getattr(self, name), name))
        if isinstance(self.recovery_event_threshold, bool) or not isinstance(self.recovery_event_threshold, int):
            raise TypeError("recovery_event_threshold must be an int")
        if self.recovery_event_threshold < 1:
            raise ValueError("recovery_event_threshold must be positive")


@dataclass(frozen=True)
class MetaControlPolicyInput:
    """Immutable composition of delivered state and the minimal runtime view."""

    deliberation_state: DeliberationState
    resource_state: ResourceState
    runtime: MetaControlRuntimeProjection

    def __post_init__(self) -> None:
        if not isinstance(self.deliberation_state, DeliberationState):
            raise TypeError("deliberation_state must be a DeliberationState")
        if not isinstance(self.resource_state, ResourceState):
            raise TypeError("resource_state must be a ResourceState")
        if not isinstance(self.runtime, MetaControlRuntimeProjection):
            raise TypeError("runtime must be a MetaControlRuntimeProjection")


@dataclass(frozen=True)
class MetaDecision:
    """Structured pure policy result suitable for later provenance admission."""

    decision: MetaDecisionType
    reason_code: str
    rule_code: str
    policy_version: str
    formalism_version: str
    runtime_projection_identity: str
    deliberation_transition_identity: str
    resource_transition_identity: str
    tie_break_applied: bool = False
    fallback_applied: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.decision, MetaDecisionType):
            raise TypeError("decision must be a MetaDecisionType")
        for name in ("reason_code", "rule_code", "policy_version", "formalism_version", "runtime_projection_identity", "deliberation_transition_identity", "resource_transition_identity"):
            _text(getattr(self, name), name)
        if not isinstance(self.tie_break_applied, bool) or not isinstance(self.fallback_applied, bool):
            raise TypeError("tie_break_applied and fallback_applied must be bool")


class MetaControlPolicy:
    """Implementation of the frozen deterministic #210 reference relation."""

    @staticmethod
    def decide(policy_input: MetaControlPolicyInput, config: MetaControlPolicyConfig) -> MetaDecision:
        if not isinstance(policy_input, MetaControlPolicyInput):
            raise TypeError("policy_input must be a MetaControlPolicyInput")
        if not isinstance(config, MetaControlPolicyConfig):
            raise TypeError("config must be a MetaControlPolicyConfig")
        state = policy_input.deliberation_state
        resources = policy_input.resource_state
        runtime = policy_input.runtime
        epistemic = state.epistemic_state

        def result(decision: MetaDecisionType, reason: str, rule: str, *, tie: bool = False, fallback: bool = False) -> MetaDecision:
            return MetaDecision(
                decision, reason, rule, config.version, config.formalism_version,
                runtime.identity, state.transition_identity, resources.transition_identity,
                tie, fallback,
            )

        # Rule 1: immutable state constructors have validated structure; unknown
        # mandatory value merely makes its dependent candidate unavailable.
        if runtime.terminal_state is RuntimeTerminalState.ANSWER_TERMINAL:
            return result(MetaDecisionType.ANSWER, "terminal_answer_state", "rule_2")
        if runtime.terminal_state is RuntimeTerminalState.TERMINAL:
            return result(MetaDecisionType.STOP, "already_terminal", "rule_2")

        reasoning = resources.allocation(ResourceDimension.REASONING_STEP)
        tool = resources.allocation(ResourceDimension.TOOL_ATTEMPT)
        provider = resources.allocation(ResourceDimension.PROVIDER_INTERACTION)
        if reasoning.exhausted and tool.exhausted and provider.exhausted:
            return result(MetaDecisionType.STOP, "hard_stop", "rule_3")
        if any(event.category is RecoveryEventCategory.UNRECOVERABLE_FAILURE for event in state.failure_recovery.events):
            return result(MetaDecisionType.STOP, "hard_stop", "rule_3")

        recovery_events = sum(
            event.category in {RecoveryEventCategory.RECOVERABLE_FAILURE, RecoveryEventCategory.UNAVAILABLE_ACTION_OR_TOOL}
            for event in state.failure_recovery.events
        )
        if runtime.recovery_admissible and not reasoning.exhausted and recovery_events >= config.recovery_event_threshold:
            return result(MetaDecisionType.REPLAN, "recovery_required", "rule_4")
        if runtime.answer_condition:
            return result(MetaDecisionType.ANSWER, "answer_condition", "rule_5")

        gain = epistemic.expected_information_gain
        task = epistemic.expected_task_value
        action = epistemic.expected_action_value
        candidates: list[tuple[MetaDecisionType, float, str]] = []
        if gain.availability is SignalAvailability.AVAILABLE and task.availability is SignalAvailability.AVAILABLE:
            if runtime.observation_available and not provider.exhausted and gain.value > 0:
                candidates.append((MetaDecisionType.OBSERVE, gain.value + task.value - config.observation_cost, "value_information"))
            if not reasoning.exhausted:
                candidates.append((MetaDecisionType.CONTINUE_REASONING, gain.value + task.value - config.reasoning_cost, "value_reasoning"))
        if task.availability is SignalAvailability.AVAILABLE and action.availability is SignalAvailability.AVAILABLE:
            if runtime.action_available and not tool.exhausted and not provider.exhausted:
                candidates.append((MetaDecisionType.ACT, task.value + action.value - config.action_cost, "value_action"))

        positive = [candidate for candidate in candidates if candidate[1] > config.marginal_threshold]
        if positive:
            highest = max(candidate[1] for candidate in positive)
            ranked = [candidate for candidate in positive if candidate[1] == highest]
            order = (MetaDecisionType.OBSERVE, MetaDecisionType.ACT, MetaDecisionType.CONTINUE_REASONING)
            winner = next(candidate for kind in order for candidate in ranked if candidate[0] is kind)
            return result(winner[0], winner[2], "rule_6_8", tie=len(ranked) > 1)

        stability = epistemic.belief_stability
        if candidates and all(candidate[1] <= config.diminishing_threshold for candidate in candidates):
            return result(MetaDecisionType.STOP, "adaptive_stop", "rule_9")
        if stability.availability is SignalAvailability.AVAILABLE and stability.value > 0 and not positive:
            return result(MetaDecisionType.STOP, "adaptive_stop", "rule_9")
        return result(MetaDecisionType.STOP, "insufficient_admissible_evidence", "rule_10", fallback=True)
