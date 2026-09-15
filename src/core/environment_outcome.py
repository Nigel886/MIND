"""Typed public environment/tool outcome semantics for M17."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping

from src.core.observation import Observation
from src.core.tool import ToolRegistry, ToolResult


class EnvironmentOutcomeCategory(str, Enum):
    """Public architecture-level categories for one environment outcome."""

    SUCCESS = "success"
    RECOVERABLE_FAILURE = "recoverable_failure"
    UNRECOVERABLE_FAILURE = "unrecoverable_failure"
    INVALID_ACTION = "invalid_action"


class EnvironmentOutcomeReason(str, Enum):
    """Closed, non-evaluative reasons permitted for public outcomes."""

    SUCCESSFUL_RESULT = "successful_result"
    TOOL_NOT_FOUND = "tool_not_found"
    INVALID_ARGUMENTS = "invalid_arguments"
    INVOCATION_REJECTED = "invocation_rejected"
    TOOL_TRANSIENT_FAILURE = "tool_transient_failure"
    TOOL_PERMANENT_FAILURE = "tool_permanent_failure"
    TOOL_EXECUTION_ERROR = "tool_execution_error"
    ENVIRONMENT_REJECTED = "environment_rejected"


_VALID_REASONS = {
    EnvironmentOutcomeCategory.SUCCESS: frozenset({EnvironmentOutcomeReason.SUCCESSFUL_RESULT}),
    EnvironmentOutcomeCategory.RECOVERABLE_FAILURE: frozenset(
        {EnvironmentOutcomeReason.TOOL_TRANSIENT_FAILURE},
    ),
    EnvironmentOutcomeCategory.UNRECOVERABLE_FAILURE: frozenset(
        {
            EnvironmentOutcomeReason.TOOL_PERMANENT_FAILURE,
            EnvironmentOutcomeReason.TOOL_EXECUTION_ERROR,
            EnvironmentOutcomeReason.ENVIRONMENT_REJECTED,
        },
    ),
    EnvironmentOutcomeCategory.INVALID_ACTION: frozenset(
        {
            EnvironmentOutcomeReason.TOOL_NOT_FOUND,
            EnvironmentOutcomeReason.INVALID_ARGUMENTS,
            EnvironmentOutcomeReason.INVOCATION_REJECTED,
        },
    ),
}

_FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "expected_answer",
        "ground_truth",
        "correct_tool",
        "correct_action",
        "completion_status",
        "completion_label",
        "evaluator_success",
        "judge_metadata",
        "private_judge_metadata",
        "difficulty",
        "benchmark_completion_state",
        "chain_of_thought",
        "hidden_reasoning",
        "private_prompt",
        "credentials",
        "api_key",
        "exception",
        "traceback",
        "stack_trace",
    },
)


def _freeze_public(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("outcome payload floats must be finite")
        return value
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("outcome payload keys must be strings")
            if key in _FORBIDDEN_PUBLIC_KEYS:
                raise ValueError(f"outcome payload contains forbidden key: {key}")
            output[key] = _freeze_public(item)
        return MappingProxyType(output)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_public(item) for item in value)
    raise TypeError("outcome payload must be JSON-compatible")


def _thaw_public(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_public(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_public(item) for item in value]
    return value


@dataclass(frozen=True)
class EnvironmentOutcome:
    """Immutable public result of an environment admission or tool event."""

    category: EnvironmentOutcomeCategory
    reason: EnvironmentOutcomeReason
    payload: dict[str, Any] = field(default_factory=dict)
    diagnostic: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.category, EnvironmentOutcomeCategory):
            raise TypeError("category must be an EnvironmentOutcomeCategory")
        if not isinstance(self.reason, EnvironmentOutcomeReason):
            raise TypeError("reason must be an EnvironmentOutcomeReason")
        if self.reason not in _VALID_REASONS[self.category]:
            raise ValueError("reason is not valid for outcome category")
        if not isinstance(self.payload, dict):
            raise TypeError("payload must be a dict")
        if self.diagnostic is not None:
            if not isinstance(self.diagnostic, str):
                raise TypeError("diagnostic must be a string or None")
            if len(self.diagnostic) > 256:
                raise ValueError("diagnostic must be at most 256 characters")
        object.__setattr__(self, "payload", _freeze_public(self.payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "reason": self.reason.value,
            "payload": _thaw_public(self.payload),
            "diagnostic": self.diagnostic,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnvironmentOutcome":
        if not isinstance(data, dict):
            raise TypeError("EnvironmentOutcome data must be a dict")
        try:
            return cls(
                EnvironmentOutcomeCategory(data["category"]),
                EnvironmentOutcomeReason(data["reason"]),
                data.get("payload", {}),
                data.get("diagnostic"),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid EnvironmentOutcome data") from error

    def to_observation(self) -> Observation:
        """Embed this public outcome in the established external boundary."""

        return Observation(
            source="agent_environment",
            content={"environment_outcome": self.to_dict()},
        )

    @classmethod
    def from_observation(cls, observation: Observation) -> "EnvironmentOutcome":
        if not isinstance(observation, Observation):
            raise TypeError("observation must be an Observation")
        if observation.source != "agent_environment":
            raise ValueError("outcome observation source must be agent_environment")
        if not isinstance(observation.content, dict) or set(observation.content) != {
            "environment_outcome",
        }:
            raise ValueError("outcome observation must contain only environment_outcome")
        return cls.from_dict(observation.content["environment_outcome"])


def outcome_from_tool_result(
    result: ToolResult,
    failure_reason: EnvironmentOutcomeReason | None = None,
) -> EnvironmentOutcome:
    """Map public tool result semantics selected by the external executor."""

    if not isinstance(result, ToolResult):
        raise TypeError("result must be a ToolResult")
    if result.success:
        if failure_reason is not None:
            raise ValueError("successful tool result cannot have a failure reason")
        return EnvironmentOutcome(
            EnvironmentOutcomeCategory.SUCCESS,
            EnvironmentOutcomeReason.SUCCESSFUL_RESULT,
            {"tool_name": result.tool_name, "output": result.output},
        )
    if failure_reason is EnvironmentOutcomeReason.TOOL_TRANSIENT_FAILURE:
        category = EnvironmentOutcomeCategory.RECOVERABLE_FAILURE
    elif failure_reason in {
        EnvironmentOutcomeReason.TOOL_PERMANENT_FAILURE,
        EnvironmentOutcomeReason.TOOL_EXECUTION_ERROR,
    }:
        category = EnvironmentOutcomeCategory.UNRECOVERABLE_FAILURE
    else:
        raise ValueError("failed tool result requires an explicit tool failure reason")
    return EnvironmentOutcome(category, failure_reason, {"tool_name": result.tool_name})


def outcome_from_registry_admission(
    registry: ToolRegistry,
    tool_name: str,
    parameters: dict[str, Any],
) -> EnvironmentOutcome | None:
    """Return an admission outcome; ``None`` means registry admission passed."""

    if not isinstance(registry, ToolRegistry):
        raise TypeError("registry must be a ToolRegistry")
    try:
        registry.validate_call(tool_name, parameters)
    except LookupError:
        return EnvironmentOutcome(
            EnvironmentOutcomeCategory.INVALID_ACTION,
            EnvironmentOutcomeReason.TOOL_NOT_FOUND,
            {"tool_name": tool_name},
        )
    except (TypeError, ValueError):
        return EnvironmentOutcome(
            EnvironmentOutcomeCategory.INVALID_ACTION,
            EnvironmentOutcomeReason.INVALID_ARGUMENTS,
            {"tool_name": tool_name},
        )
    return None
