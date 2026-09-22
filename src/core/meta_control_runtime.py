"""Opt-in execution admission for already-selected M19 meta-decisions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Callable

from src.core.deliberation_state import DeliberationState
from src.core.meta_control_policy import MetaDecision, MetaDecisionType
from src.core.resource_accounting import ResourceDimension, ResourceState


class MetaControlRuntimePhase(str, Enum):
    ACTIVE = "active"
    ANSWER_TERMINAL = "answer_terminal"
    STOP_TERMINAL = "stop_terminal"


@dataclass(frozen=True)
class MetaControlRuntimeState:
    """Immutable M19 runtime integration state; it does not own policy."""

    deliberation_state: DeliberationState
    resource_state: ResourceState
    phase: MetaControlRuntimePhase
    transition_identity: str
    answer: object | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.deliberation_state, DeliberationState):
            raise TypeError("deliberation_state must be a DeliberationState")
        if not isinstance(self.resource_state, ResourceState):
            raise TypeError("resource_state must be a ResourceState")
        if not isinstance(self.phase, MetaControlRuntimePhase):
            raise TypeError("phase must be a MetaControlRuntimePhase")
        if not isinstance(self.transition_identity, str) or not self.transition_identity.strip():
            raise ValueError("transition_identity must be non-empty")
        if self.phase is not MetaControlRuntimePhase.ANSWER_TERMINAL and self.answer is not None:
            raise ValueError("only answer-terminal state may carry an answer")


@dataclass(frozen=True)
class MetaControlExecutionContext:
    """Validated injected existing-boundary callbacks and optional payloads."""

    transition_identity: str
    advance_reasoning: Callable[[], None] | None = None
    execute_action: Callable[[], None] | None = None
    acquire_observation: Callable[[], None] | None = None
    replan: Callable[[], None] | None = None
    answer: object | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.transition_identity, str) or not self.transition_identity.strip():
            raise ValueError("transition_identity must be non-empty")
        for name in ("advance_reasoning", "execute_action", "acquire_observation", "replan"):
            value = getattr(self, name)
            if value is not None and not callable(value):
                raise TypeError(f"{name} must be callable or None")


@dataclass(frozen=True)
class MetaControlExecutionResult:
    """Compact provenance handoff without telemetry persistence."""

    state: MetaControlRuntimeState
    outcome_code: str
    decision: MetaDecisionType
    consumed_dimensions: tuple[ResourceDimension, ...] = ()


class MetaControlRuntimeIntegrator:
    """Admit one decision without selecting, overriding, or re-running policy."""

    @staticmethod
    def execute(
        decision: MetaDecision,
        state: MetaControlRuntimeState,
        context: MetaControlExecutionContext,
    ) -> MetaControlExecutionResult:
        if not isinstance(decision, MetaDecision):
            raise TypeError("decision must be a MetaDecision")
        if not isinstance(state, MetaControlRuntimeState):
            raise TypeError("state must be a MetaControlRuntimeState")
        if not isinstance(context, MetaControlExecutionContext):
            raise TypeError("context must be a MetaControlExecutionContext")
        if state.phase is not MetaControlRuntimePhase.ACTIVE:
            return MetaControlExecutionResult(state, "already_terminal", decision.decision)

        def fail(code: str) -> MetaControlExecutionResult:
            return MetaControlExecutionResult(state, code, decision.decision)

        def invoke(callback: Callable[[], None] | None, missing: str) -> bool:
            if callback is None:
                return False
            try:
                callback()
                return True
            except Exception:
                return False

        if decision.decision is MetaDecisionType.STOP:
            return MetaControlExecutionResult(
                replace(state, phase=MetaControlRuntimePhase.STOP_TERMINAL, transition_identity=context.transition_identity),
                "stopped", decision.decision,
            )
        if decision.decision is MetaDecisionType.ANSWER:
            if context.answer is None:
                return fail("invalid_answer_payload")
            return MetaControlExecutionResult(
                replace(state, phase=MetaControlRuntimePhase.ANSWER_TERMINAL, answer=context.answer, transition_identity=context.transition_identity),
                "answer_committed", decision.decision,
            )

        required = {
            MetaDecisionType.CONTINUE_REASONING: ((ResourceDimension.REASONING_STEP,), context.advance_reasoning, "invalid_reasoning_context"),
            MetaDecisionType.REPLAN: ((ResourceDimension.REASONING_STEP,), context.replan, "invalid_replan_context"),
            MetaDecisionType.OBSERVE: ((ResourceDimension.PROVIDER_INTERACTION,), context.acquire_observation, "invalid_observation_context"),
            MetaDecisionType.ACT: ((ResourceDimension.TOOL_ATTEMPT, ResourceDimension.PROVIDER_INTERACTION), context.execute_action, "invalid_action_context"),
        }
        dimensions, callback, missing = required[decision.decision]
        if callback is None:
            return fail(missing)
        if any(state.resource_state.allocation(dimension).exhausted for dimension in dimensions):
            return fail("resource_exhausted")
        if not invoke(callback, missing):
            return fail("execution_failure")
        resources = state.resource_state
        for index, dimension in enumerate(dimensions):
            resources = resources.consume(dimension, 1, f"{context.transition_identity}:{index}")
        return MetaControlExecutionResult(
            replace(state, resource_state=resources, transition_identity=context.transition_identity),
            "executed", decision.decision, dimensions,
        )
