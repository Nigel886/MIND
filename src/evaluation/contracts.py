"""Immutable public contracts for future M14 Agent evaluation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping

from src.core.task import Task


class EvaluationActionType(str, Enum):
    """Public action categories exposed by an evaluation adapter."""

    ANSWER = "answer"
    TOOL_CALL = "tool_call"
    FAIL = "fail"
    INVALID = "invalid"


class EvaluationFeedbackType(str, Enum):
    """Environment-owned feedback categories."""

    INITIAL_INPUT = "initial_input"
    TOOL_RESPONSE = "tool_response"
    INVALID_ACTION = "invalid_action"
    TOOL_FAILURE = "tool_failure"
    BUDGET = "budget"
    TIMEOUT = "timeout"


class EvaluationOutcomeType(str, Enum):
    """Evaluation-owned terminal judgments."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    INVALID_EXECUTION = "invalid_execution"


_FORBIDDEN_TRACE_KEYS = frozenset(
    {
        "chain_of_thought",
        "cot",
        "hidden_reasoning",
        "prompt",
        "prompts",
        "credential",
        "credentials",
        "api_key",
        "api_keys",
        "secret",
        "secrets",
    }
)


def _freeze_json(value: Any) -> Any:
    """Recursively detach and freeze JSON-compatible public data."""

    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("mapping keys must be strings")
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("float values must be finite")
        return value
    raise ValueError("values must be JSON-compatible data")


def _thaw_json(value: Any) -> Any:
    """Return fresh ordinary JSON-compatible containers."""

    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return deepcopy(value)


def _freeze_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict")
    return _freeze_json(value)


def _text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    if value != value.strip():
        raise ValueError(f"{name} must not have leading or trailing whitespace")


def _validate_trace_keys(value: Any) -> None:
    """Reject fields that would violate the compact public trace boundary."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            if key.casefold() in _FORBIDDEN_TRACE_KEYS:
                raise ValueError(f"trace must not contain {key}")
            _validate_trace_keys(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _validate_trace_keys(item)


@dataclass(frozen=True)
class EvaluationCase:
    """Immutable evaluation identity, user-level task, and environment setup."""

    evaluation_id: str
    task: Task
    environment_config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _text(self.evaluation_id, "evaluation_id")
        if not isinstance(self.task, Task):
            raise TypeError("task must be a Task")
        object.__setattr__(
            self,
            "environment_config",
            _freeze_mapping(self.environment_config, "environment_config"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "task": self.task.to_dict(),
            "environment_config": _thaw_json(self.environment_config),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationCase":
        if not isinstance(data, dict):
            raise TypeError("EvaluationCase data must be a dict")
        return cls(
            evaluation_id=data["evaluation_id"],
            task=Task.from_dict(data["task"]),
            environment_config=data.get("environment_config", {}),
        )


@dataclass(frozen=True)
class EvaluationAction:
    """External evaluation action, deliberately distinct from MIND Policy."""

    action_type: EvaluationActionType
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.action_type, EvaluationActionType):
            raise TypeError("action_type must be an EvaluationActionType")
        frozen_payload = _freeze_mapping(self.payload, "payload")
        if self.action_type is EvaluationActionType.TOOL_CALL:
            tool_name = frozen_payload.get("tool_name")
            if "parameters" not in frozen_payload:
                raise ValueError("tool_call payload requires parameters")
            parameters = frozen_payload["parameters"]
            _text(tool_name, "tool_name")
            if not isinstance(parameters, Mapping):
                raise TypeError("tool_call parameters must be a dict")
        object.__setattr__(self, "payload", frozen_payload)

    def to_dict(self) -> dict[str, Any]:
        return {"action_type": self.action_type.value, "payload": _thaw_json(self.payload)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationAction":
        if not isinstance(data, dict):
            raise TypeError("EvaluationAction data must be a dict")
        try:
            action_type = EvaluationActionType(data["action_type"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid EvaluationAction action_type") from error
        return cls(action_type=action_type, payload=data.get("payload", {}))


@dataclass(frozen=True)
class EvaluationFeedback:
    """Immutable public feedback owned by the evaluation environment."""

    feedback_type: EvaluationFeedbackType
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.feedback_type, EvaluationFeedbackType):
            raise TypeError("feedback_type must be an EvaluationFeedbackType")
        object.__setattr__(self, "payload", _freeze_mapping(self.payload, "payload"))

    def to_dict(self) -> dict[str, Any]:
        return {"feedback_type": self.feedback_type.value, "payload": _thaw_json(self.payload)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationFeedback":
        if not isinstance(data, dict):
            raise TypeError("EvaluationFeedback data must be a dict")
        try:
            feedback_type = EvaluationFeedbackType(data["feedback_type"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid EvaluationFeedback feedback_type") from error
        return cls(feedback_type=feedback_type, payload=data.get("payload", {}))


@dataclass(frozen=True)
class EvaluationOutcome:
    """Immutable terminal judgment owned by the evaluation layer."""

    outcome_type: EvaluationOutcomeType
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.outcome_type, EvaluationOutcomeType):
            raise TypeError("outcome_type must be an EvaluationOutcomeType")
        object.__setattr__(self, "payload", _freeze_mapping(self.payload, "payload"))

    def to_dict(self) -> dict[str, Any]:
        return {"outcome_type": self.outcome_type.value, "payload": _thaw_json(self.payload)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationOutcome":
        if not isinstance(data, dict):
            raise TypeError("EvaluationOutcome data must be a dict")
        try:
            outcome_type = EvaluationOutcomeType(data["outcome_type"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid EvaluationOutcome outcome_type") from error
        return cls(outcome_type=outcome_type, payload=data.get("payload", {}))


@dataclass(frozen=True)
class EvaluationTrace:
    """Compact immutable public record of evaluated actions and feedback."""

    actions: tuple[EvaluationAction, ...]
    feedback: tuple[EvaluationFeedback, ...]
    outcome: EvaluationOutcome
    resource_usage: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.actions, (tuple, list)):
            raise TypeError("actions must be an ordered sequence")
        if not isinstance(self.feedback, (tuple, list)):
            raise TypeError("feedback must be an ordered sequence")
        actions = tuple(self.actions)
        feedback = tuple(self.feedback)
        if any(not isinstance(action, EvaluationAction) for action in actions):
            raise TypeError("actions must contain EvaluationAction values")
        if any(not isinstance(item, EvaluationFeedback) for item in feedback):
            raise TypeError("feedback must contain EvaluationFeedback values")
        if not isinstance(self.outcome, EvaluationOutcome):
            raise TypeError("outcome must be an EvaluationOutcome")
        frozen_usage = _freeze_mapping(self.resource_usage, "resource_usage")
        _validate_trace_keys(
            {
                "actions": [action.to_dict() for action in actions],
                "feedback": [item.to_dict() for item in feedback],
                "outcome": self.outcome.to_dict(),
                "resource_usage": _thaw_json(frozen_usage),
            },
        )
        object.__setattr__(self, "actions", actions)
        object.__setattr__(self, "feedback", feedback)
        object.__setattr__(self, "resource_usage", frozen_usage)

    def to_dict(self) -> dict[str, Any]:
        return {
            "actions": [action.to_dict() for action in self.actions],
            "feedback": [item.to_dict() for item in self.feedback],
            "outcome": self.outcome.to_dict(),
            "resource_usage": _thaw_json(self.resource_usage),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationTrace":
        if not isinstance(data, dict):
            raise TypeError("EvaluationTrace data must be a dict")
        return cls(
            actions=tuple(EvaluationAction.from_dict(item) for item in data["actions"]),
            feedback=tuple(EvaluationFeedback.from_dict(item) for item in data["feedback"]),
            outcome=EvaluationOutcome.from_dict(data["outcome"]),
            resource_usage=data.get("resource_usage", {}),
        )
