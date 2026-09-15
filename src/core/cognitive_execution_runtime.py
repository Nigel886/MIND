"""Opt-in bounded multi-cycle orchestration for MIND-Lite cognitive sessions."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping, Protocol

from src.core.cognitive_session import (
    CognitiveActionRequest,
    CognitiveAgentSession,
    CognitiveSessionTerminationReason,
)
from src.core.environment_outcome import EnvironmentOutcome, EnvironmentOutcomeCategory
from src.core.policy_context import PolicyDecisionEngine
from src.core.task import Task
from src.core.tool import CapabilityDescriptor


class CognitiveExecutionEnvironment(Protocol):
    """Provider-independent external boundary for public tool-call requests."""

    def apply(self, action: CognitiveActionRequest) -> EnvironmentOutcome:
        """Apply a public action and return one typed public outcome."""


def _freeze_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("execution result floats must be finite")
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("execution result keys must be strings")
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    raise TypeError("execution result values must be JSON-compatible")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return deepcopy(value)


class CognitiveExecutionTerminationReason(str, Enum):
    """Architecture-level controller termination reasons, not evaluator scores."""

    ANSWER_SUBMITTED = "answer_submitted"
    UNRECOVERABLE_ENVIRONMENT_FAILURE = "unrecoverable_environment_failure"
    BUDGET_EXHAUSTED = "budget_exhausted"
    POLICY_FAILURE = "policy_failure"
    ENVIRONMENT_FAILURE = "environment_failure"


@dataclass(frozen=True)
class CognitiveExecutionBudget:
    """Finite deterministic limits for one opt-in execution controller run."""

    max_cycles: int
    max_tool_calls: int | None = None
    max_invalid_actions: int | None = None
    max_recoverable_failures: int | None = None

    def __post_init__(self) -> None:
        values = {
            "max_cycles": self.max_cycles,
            "max_tool_calls": self.max_tool_calls,
            "max_invalid_actions": self.max_invalid_actions,
            "max_recoverable_failures": self.max_recoverable_failures,
        }
        for name, value in values.items():
            if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                raise TypeError(f"{name} must be an int or None")
            if value is not None and value < 0:
                raise ValueError(f"{name} must not be negative")
        for name in ("max_tool_calls", "max_invalid_actions", "max_recoverable_failures"):
            if getattr(self, name) is None:
                object.__setattr__(self, name, self.max_cycles)

    def to_dict(self) -> dict[str, int]:
        return {
            "max_cycles": self.max_cycles,
            "max_tool_calls": self.max_tool_calls,
            "max_invalid_actions": self.max_invalid_actions,
            "max_recoverable_failures": self.max_recoverable_failures,
        }

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> "CognitiveExecutionBudget":
        if not isinstance(data, dict):
            raise TypeError("CognitiveExecutionBudget data must be a dict")
        return cls(
            data["max_cycles"],
            data.get("max_tool_calls"),
            data.get("max_invalid_actions"),
            data.get("max_recoverable_failures"),
        )


@dataclass(frozen=True)
class CognitiveExecutionResult:
    """Compact public outcome of one bounded controller execution."""

    termination_reason: CognitiveExecutionTerminationReason
    cycles: int
    tool_calls: int
    invalid_actions: int
    recoverable_failures: int
    answer: object | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.termination_reason, CognitiveExecutionTerminationReason):
            raise TypeError("termination_reason must be a CognitiveExecutionTerminationReason")
        for name in ("cycles", "tool_calls", "invalid_actions", "recoverable_failures"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")
        if self.termination_reason is not CognitiveExecutionTerminationReason.ANSWER_SUBMITTED and self.answer is not None:
            raise ValueError("only submitted-answer results may include an answer")
        object.__setattr__(self, "answer", _freeze_json(self.answer))

    def to_dict(self) -> dict[str, Any]:
        return {
            "termination_reason": self.termination_reason.value,
            "cycles": self.cycles,
            "tool_calls": self.tool_calls,
            "invalid_actions": self.invalid_actions,
            "recoverable_failures": self.recoverable_failures,
            "answer": _thaw_json(self.answer),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CognitiveExecutionResult":
        if not isinstance(data, dict):
            raise TypeError("CognitiveExecutionResult data must be a dict")
        try:
            return cls(
                CognitiveExecutionTerminationReason(data["termination_reason"]),
                data["cycles"],
                data["tool_calls"],
                data["invalid_actions"],
                data["recoverable_failures"],
                data.get("answer"),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid CognitiveExecutionResult data") from error


class CognitiveExecutionController:
    """Orchestrate policy/environment cycles without choosing semantic actions."""

    def __init__(
        self,
        environment: CognitiveExecutionEnvironment,
        budget: CognitiveExecutionBudget,
        *,
        policy_engine: PolicyDecisionEngine | None = None,
        capabilities: tuple[CapabilityDescriptor, ...] = (),
    ) -> None:
        if not callable(getattr(environment, "apply", None)):
            raise TypeError("environment must provide apply(action)")
        if not isinstance(budget, CognitiveExecutionBudget):
            raise TypeError("budget must be a CognitiveExecutionBudget")
        if policy_engine is not None and not callable(getattr(policy_engine, "decide", None)):
            raise TypeError("policy_engine must provide decide(context) or be None")
        if isinstance(capabilities, list) or not isinstance(capabilities, tuple):
            raise TypeError("capabilities must be an ordered tuple")
        if any(not isinstance(item, CapabilityDescriptor) for item in capabilities):
            raise TypeError("capabilities must contain CapabilityDescriptor values")
        self._environment = environment
        self._budget = budget
        self._policy_engine = policy_engine
        self._capabilities = tuple(capabilities)

    def run(self, task: Task) -> CognitiveExecutionResult:
        """Run policy/action/outcome cycles until a public runtime termination."""

        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        session = CognitiveAgentSession(
            self._budget.max_cycles,
            policy_engine=self._policy_engine,
            capabilities=self._capabilities,
        )
        session.start(task)
        cycles = tool_calls = invalid_actions = recoverable_failures = 0

        while True:
            if cycles >= self._budget.max_cycles:
                return self._finish(
                    session,
                    CognitiveExecutionTerminationReason.BUDGET_EXHAUSTED,
                    cycles,
                    tool_calls,
                    invalid_actions,
                    recoverable_failures,
                )
            try:
                step = session.step()
            except Exception:
                return self._finish(
                    session,
                    CognitiveExecutionTerminationReason.POLICY_FAILURE,
                    cycles,
                    tool_calls,
                    invalid_actions,
                    recoverable_failures,
                )
            if step.action_request is None:
                return self._finish(
                    session,
                    CognitiveExecutionTerminationReason.POLICY_FAILURE,
                    cycles,
                    tool_calls,
                    invalid_actions,
                    recoverable_failures,
                )

            action = step.action_request
            cycles += 1
            if action.action == "answer":
                return CognitiveExecutionResult(
                    CognitiveExecutionTerminationReason.ANSWER_SUBMITTED,
                    cycles,
                    tool_calls,
                    invalid_actions,
                    recoverable_failures,
                    action.parameters["answer"],
                )
            if tool_calls >= self._budget.max_tool_calls:
                return self._finish(
                    session,
                    CognitiveExecutionTerminationReason.BUDGET_EXHAUSTED,
                    cycles,
                    tool_calls,
                    invalid_actions,
                    recoverable_failures,
                )
            tool_calls += 1
            try:
                outcome = self._environment.apply(action)
            except Exception:
                return self._finish(
                    session,
                    CognitiveExecutionTerminationReason.ENVIRONMENT_FAILURE,
                    cycles,
                    tool_calls,
                    invalid_actions,
                    recoverable_failures,
                )
            if not isinstance(outcome, EnvironmentOutcome):
                return self._finish(
                    session,
                    CognitiveExecutionTerminationReason.ENVIRONMENT_FAILURE,
                    cycles,
                    tool_calls,
                    invalid_actions,
                    recoverable_failures,
                )
            try:
                session.observe(outcome.to_observation())
                session._admit_pending_observation_for_controller()
            except Exception:
                return self._finish(
                    session,
                    CognitiveExecutionTerminationReason.ENVIRONMENT_FAILURE,
                    cycles,
                    tool_calls,
                    invalid_actions,
                    recoverable_failures,
                )

            if outcome.category is EnvironmentOutcomeCategory.UNRECOVERABLE_FAILURE:
                return self._finish(
                    session,
                    CognitiveExecutionTerminationReason.UNRECOVERABLE_ENVIRONMENT_FAILURE,
                    cycles,
                    tool_calls,
                    invalid_actions,
                    recoverable_failures,
                )
            if outcome.category is EnvironmentOutcomeCategory.INVALID_ACTION:
                invalid_actions += 1
                if invalid_actions >= self._budget.max_invalid_actions:
                    return self._finish(
                        session,
                        CognitiveExecutionTerminationReason.BUDGET_EXHAUSTED,
                        cycles,
                        tool_calls,
                        invalid_actions,
                        recoverable_failures,
                    )
            if outcome.category is EnvironmentOutcomeCategory.RECOVERABLE_FAILURE:
                recoverable_failures += 1
                if recoverable_failures >= self._budget.max_recoverable_failures:
                    return self._finish(
                        session,
                        CognitiveExecutionTerminationReason.BUDGET_EXHAUSTED,
                        cycles,
                        tool_calls,
                        invalid_actions,
                        recoverable_failures,
                    )

    @staticmethod
    def _finish(
        session: CognitiveAgentSession,
        reason: CognitiveExecutionTerminationReason,
        cycles: int,
        tool_calls: int,
        invalid_actions: int,
        recoverable_failures: int,
    ) -> CognitiveExecutionResult:
        if session.phase.value != "terminated":
            session.terminate(CognitiveSessionTerminationReason.FAILED)
        return CognitiveExecutionResult(
            reason,
            cycles,
            tool_calls,
            invalid_actions,
            recoverable_failures,
        )
