"""Immutable execution-side contracts for controlled M14 Agent evaluation.

The future evaluation loop is deliberately evaluator-owned:
budget -> agent step -> action -> environment feedback -> completion judge.
This module defines only public values and the judge interface.  It does not
implement an environment, execute an Agent, or change MIND runtime behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from src.evaluation.contracts import (
    EvaluationAction,
    EvaluationActionType,
    EvaluationCase,
    EvaluationFeedback,
    EvaluationOutcome,
)


class EvaluationTimeoutPolicy(str, Enum):
    """Evaluator-owned response when a hard execution limit is reached."""

    HARD_STOP = "hard_stop"


def _non_negative_int(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, not bool")
    if value < 0:
        raise ValueError(f"{name} must not be negative")


@dataclass(frozen=True)
class EvaluationBudget:
    """Immutable resource limits supplied by the evaluator."""

    max_steps: int
    max_tool_calls: int
    timeout_policy: EvaluationTimeoutPolicy = EvaluationTimeoutPolicy.HARD_STOP

    def __post_init__(self) -> None:
        _non_negative_int(self.max_steps, "max_steps")
        _non_negative_int(self.max_tool_calls, "max_tool_calls")
        if not isinstance(self.timeout_policy, EvaluationTimeoutPolicy):
            raise TypeError("timeout_policy must be an EvaluationTimeoutPolicy")

    def to_dict(self) -> dict[str, object]:
        return {
            "max_steps": self.max_steps,
            "max_tool_calls": self.max_tool_calls,
            "timeout_policy": self.timeout_policy.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "EvaluationBudget":
        if not isinstance(data, dict):
            raise TypeError("EvaluationBudget data must be a dict")
        try:
            timeout_policy = EvaluationTimeoutPolicy(data["timeout_policy"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid EvaluationBudget timeout_policy") from error
        return cls(
            max_steps=data["max_steps"],
            max_tool_calls=data["max_tool_calls"],
            timeout_policy=timeout_policy,
        )


@dataclass(frozen=True)
class EvaluationBudgetState:
    """Immutable public consumption view provided to an Agent step."""

    budget: EvaluationBudget
    steps_used: int = 0
    tool_calls_used: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.budget, EvaluationBudget):
            raise TypeError("budget must be an EvaluationBudget")
        _non_negative_int(self.steps_used, "steps_used")
        _non_negative_int(self.tool_calls_used, "tool_calls_used")
        if self.steps_used > self.budget.max_steps:
            raise ValueError("steps_used must not exceed max_steps")
        if self.tool_calls_used > self.budget.max_tool_calls:
            raise ValueError("tool_calls_used must not exceed max_tool_calls")

    @property
    def remaining_steps(self) -> int:
        """Return the evaluator-approved remaining Agent-step allowance."""

        return self.budget.max_steps - self.steps_used

    @property
    def remaining_tool_calls(self) -> int:
        """Return the evaluator-approved remaining tool-call allowance."""

        return self.budget.max_tool_calls - self.tool_calls_used

    def to_dict(self) -> dict[str, object]:
        return {
            "budget": self.budget.to_dict(),
            "steps_used": self.steps_used,
            "tool_calls_used": self.tool_calls_used,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "EvaluationBudgetState":
        if not isinstance(data, dict):
            raise TypeError("EvaluationBudgetState data must be a dict")
        return cls(
            budget=EvaluationBudget.from_dict(data["budget"]),
            steps_used=data.get("steps_used", 0),
            tool_calls_used=data.get("tool_calls_used", 0),
        )


@dataclass(frozen=True)
class AgentStepInput:
    """Public, immutable input supplied to a single Agent step."""

    case: EvaluationCase
    previous_feedback: EvaluationFeedback
    budget_state: EvaluationBudgetState

    def __post_init__(self) -> None:
        if not isinstance(self.case, EvaluationCase):
            raise TypeError("case must be an EvaluationCase")
        if not isinstance(self.previous_feedback, EvaluationFeedback):
            raise TypeError("previous_feedback must be an EvaluationFeedback")
        if not isinstance(self.budget_state, EvaluationBudgetState):
            raise TypeError("budget_state must be an EvaluationBudgetState")

    def to_dict(self) -> dict[str, object]:
        return {
            "case": self.case.to_dict(),
            "previous_feedback": self.previous_feedback.to_dict(),
            "budget_state": self.budget_state.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "AgentStepInput":
        if not isinstance(data, dict):
            raise TypeError("AgentStepInput data must be a dict")
        return cls(
            case=EvaluationCase.from_dict(data["case"]),
            previous_feedback=EvaluationFeedback.from_dict(data["previous_feedback"]),
            budget_state=EvaluationBudgetState.from_dict(data["budget_state"]),
        )


@dataclass(frozen=True)
class AgentStepResult:
    """One public action and a non-judgmental termination request."""

    action: EvaluationAction
    request_termination: bool

    def __post_init__(self) -> None:
        if not isinstance(self.action, EvaluationAction):
            raise TypeError("action must be an EvaluationAction")
        if not isinstance(self.request_termination, bool):
            raise TypeError("request_termination must be a bool")
        if self.action.action_type in {
            EvaluationActionType.ANSWER,
            EvaluationActionType.FAIL,
            EvaluationActionType.INVALID,
        } and not self.request_termination:
            raise ValueError("terminal actions must request termination")
        if (
            self.action.action_type is EvaluationActionType.TOOL_CALL
            and self.request_termination
        ):
            raise ValueError("tool_call actions must not request termination")

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action.to_dict(),
            "request_termination": self.request_termination,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "AgentStepResult":
        if not isinstance(data, dict):
            raise TypeError("AgentStepResult data must be a dict")
        return cls(
            action=EvaluationAction.from_dict(data["action"]),
            request_termination=data["request_termination"],
        )


@dataclass(frozen=True)
class EnvironmentInteraction:
    """One immutable public action/feedback pair owned by the evaluator."""

    action: EvaluationAction
    feedback: EvaluationFeedback

    def __post_init__(self) -> None:
        if not isinstance(self.action, EvaluationAction):
            raise TypeError("action must be an EvaluationAction")
        if not isinstance(self.feedback, EvaluationFeedback):
            raise TypeError("feedback must be an EvaluationFeedback")

    def to_dict(self) -> dict[str, object]:
        return {"action": self.action.to_dict(), "feedback": self.feedback.to_dict()}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "EnvironmentInteraction":
        if not isinstance(data, dict):
            raise TypeError("EnvironmentInteraction data must be a dict")
        return cls(
            action=EvaluationAction.from_dict(data["action"]),
            feedback=EvaluationFeedback.from_dict(data["feedback"]),
        )


class CompletionJudge(Protocol):
    """Evaluation-owned protocol that assigns the terminal public outcome."""

    def evaluate(
        self,
        case: EvaluationCase,
        interactions: tuple[EnvironmentInteraction, ...],
        budget_state: EvaluationBudgetState,
    ) -> EvaluationOutcome:
        """Judge public execution semantics without accessing Agent-private state."""
