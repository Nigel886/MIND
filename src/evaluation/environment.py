"""Deterministic local environment for M14 evaluation contracts.

The environment simulates public tool feedback from frozen configuration.  It
does not execute MIND tools, access Agent-private state, or assign outcomes.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping

from src.evaluation.contracts import (
    EvaluationAction,
    EvaluationActionType,
    EvaluationCase,
    EvaluationFeedback,
    EvaluationFeedbackType,
)
from src.evaluation.execution import EvaluationBudgetState


class FailureInjectionType(str, Enum):
    """Explicit deterministic environmental failure categories."""

    TOOL_FAILURE = "tool_failure"
    INVALID_ACTION = "invalid_action"
    TIMEOUT = "timeout"
    BUDGET_EXHAUSTION = "budget_exhaustion"


def _freeze_json(value: Any) -> Any:
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


@dataclass(frozen=True)
class FailureInjectionRule:
    """A one-shot, public failure matched against one submitted action."""

    rule_id: str
    trigger_step: int
    failure_type: FailureInjectionType
    action_type: EvaluationActionType | None = None
    tool_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _text(self.rule_id, "rule_id")
        if isinstance(self.trigger_step, bool) or not isinstance(self.trigger_step, int):
            raise TypeError("trigger_step must be an int, not bool")
        if self.trigger_step < 1:
            raise ValueError("trigger_step must be at least 1")
        if not isinstance(self.failure_type, FailureInjectionType):
            raise TypeError("failure_type must be a FailureInjectionType")
        if self.action_type is not None and not isinstance(self.action_type, EvaluationActionType):
            raise TypeError("action_type must be an EvaluationActionType or None")
        if self.tool_name is not None:
            _text(self.tool_name, "tool_name")
            if self.action_type not in (None, EvaluationActionType.TOOL_CALL):
                raise ValueError("tool_name requires tool_call action_type or None")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def matches(self, action: EvaluationAction, action_index: int) -> bool:
        """Return whether this rule targets the supplied public action."""

        if action_index != self.trigger_step:
            return False
        if self.action_type is not None and action.action_type is not self.action_type:
            return False
        if self.tool_name is not None:
            return (
                action.action_type is EvaluationActionType.TOOL_CALL
                and action.payload.get("tool_name") == self.tool_name
            )
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "trigger_step": self.trigger_step,
            "failure_type": self.failure_type.value,
            "action_type": self.action_type.value if self.action_type else None,
            "tool_name": self.tool_name,
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FailureInjectionRule":
        if not isinstance(data, dict):
            raise TypeError("FailureInjectionRule data must be a dict")
        try:
            failure_type = FailureInjectionType(data["failure_type"])
            action_type = (
                None
                if data.get("action_type") is None
                else EvaluationActionType(data["action_type"])
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid FailureInjectionRule enum value") from error
        return cls(
            rule_id=data["rule_id"],
            trigger_step=data["trigger_step"],
            failure_type=failure_type,
            action_type=action_type,
            tool_name=data.get("tool_name"),
            metadata=data.get("metadata", {}),
        )


def _rules_overlap(left: FailureInjectionRule, right: FailureInjectionRule) -> bool:
    if left.trigger_step != right.trigger_step:
        return False
    action_overlap = (
        left.action_type is None
        or right.action_type is None
        or left.action_type is right.action_type
    )
    tool_overlap = (
        left.tool_name is None
        or right.tool_name is None
        or left.tool_name == right.tool_name
    )
    return action_overlap and tool_overlap


@dataclass(frozen=True)
class EnvironmentConfig:
    """Immutable public configuration for one deterministic environment."""

    environment_id: str
    tool_responses: dict[str, dict[str, Any]]
    failure_injections: tuple[FailureInjectionRule, ...] = field(default_factory=tuple)
    initial_payload: dict[str, Any] = field(default_factory=dict)
    completion_context: dict[str, Any] = field(default_factory=dict)
    public_tool_state: dict[str, Any] = field(default_factory=dict)
    scenario_seed: int = 0

    def __post_init__(self) -> None:
        _text(self.environment_id, "environment_id")
        if not isinstance(self.tool_responses, dict):
            raise TypeError("tool_responses must be a dict")
        for tool_name, response in self.tool_responses.items():
            _text(tool_name, "tool response name")
            if not isinstance(response, dict):
                raise TypeError("tool response values must be dicts")
        rules = tuple(self.failure_injections)
        if not isinstance(self.failure_injections, (tuple, list)):
            raise TypeError("failure_injections must be an ordered sequence")
        if any(not isinstance(rule, FailureInjectionRule) for rule in rules):
            raise TypeError("failure_injections must contain FailureInjectionRule values")
        if len({rule.rule_id for rule in rules}) != len(rules):
            raise ValueError("failure_injections must not contain duplicate rule_id values")
        if any(_rules_overlap(left, right) for index, left in enumerate(rules) for right in rules[index + 1:]):
            raise ValueError("failure_injections must not contain overlapping rules")
        if isinstance(self.scenario_seed, bool) or not isinstance(self.scenario_seed, int):
            raise TypeError("scenario_seed must be an int, not bool")
        if self.scenario_seed < 0:
            raise ValueError("scenario_seed must not be negative")
        object.__setattr__(self, "tool_responses", _freeze_mapping(self.tool_responses, "tool_responses"))
        object.__setattr__(self, "failure_injections", rules)
        object.__setattr__(self, "initial_payload", _freeze_mapping(self.initial_payload, "initial_payload"))
        object.__setattr__(self, "completion_context", _freeze_mapping(self.completion_context, "completion_context"))
        object.__setattr__(self, "public_tool_state", _freeze_mapping(self.public_tool_state, "public_tool_state"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "tool_responses": _thaw_json(self.tool_responses),
            "failure_injections": [rule.to_dict() for rule in self.failure_injections],
            "initial_payload": _thaw_json(self.initial_payload),
            "completion_context": _thaw_json(self.completion_context),
            "public_tool_state": _thaw_json(self.public_tool_state),
            "scenario_seed": self.scenario_seed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnvironmentConfig":
        if not isinstance(data, dict):
            raise TypeError("EnvironmentConfig data must be a dict")
        return cls(
            environment_id=data["environment_id"],
            tool_responses=data["tool_responses"],
            failure_injections=tuple(
                FailureInjectionRule.from_dict(item)
                for item in data.get("failure_injections", ())
            ),
            initial_payload=data.get("initial_payload", {}),
            completion_context=data.get("completion_context", {}),
            public_tool_state=data.get("public_tool_state", {}),
            scenario_seed=data.get("scenario_seed", 0),
        )


@dataclass(frozen=True)
class EnvironmentSnapshot:
    """Compact public state excluding Agent and MIND-core implementation data."""

    environment_id: str
    action_count: int
    consumed_failures: tuple[str, ...]
    public_tool_state: dict[str, Any]

    def __post_init__(self) -> None:
        _text(self.environment_id, "environment_id")
        if isinstance(self.action_count, bool) or not isinstance(self.action_count, int):
            raise TypeError("action_count must be an int, not bool")
        if self.action_count < 0:
            raise ValueError("action_count must not be negative")
        if not isinstance(self.consumed_failures, (tuple, list)):
            raise TypeError("consumed_failures must be an ordered sequence")
        consumed = tuple(self.consumed_failures)
        if any(not isinstance(identifier, str) or not identifier.strip() for identifier in consumed):
            raise TypeError("consumed_failures must contain non-empty strings")
        object.__setattr__(self, "consumed_failures", consumed)
        object.__setattr__(self, "public_tool_state", _freeze_mapping(self.public_tool_state, "public_tool_state"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "action_count": self.action_count,
            "consumed_failures": list(self.consumed_failures),
            "public_tool_state": _thaw_json(self.public_tool_state),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnvironmentSnapshot":
        if not isinstance(data, dict):
            raise TypeError("EnvironmentSnapshot data must be a dict")
        return cls(
            environment_id=data["environment_id"],
            action_count=data["action_count"],
            consumed_failures=tuple(data["consumed_failures"]),
            public_tool_state=data["public_tool_state"],
        )


class DeterministicEvaluationEnvironment:
    """A local, stateful evaluator component with deterministic feedback only."""

    def __init__(self, config: EnvironmentConfig) -> None:
        if not isinstance(config, EnvironmentConfig):
            raise TypeError("config must be an EnvironmentConfig")
        self._config = config
        self._is_reset = False
        self._action_count = 0
        self._consumed_failures: list[str] = []
        self._public_tool_state: dict[str, Any] = _thaw_json(config.public_tool_state)

    def reset(self, case: EvaluationCase) -> EvaluationFeedback:
        """Start a fresh local episode and return public initial input."""

        if not isinstance(case, EvaluationCase):
            raise TypeError("case must be an EvaluationCase")
        self._is_reset = True
        self._action_count = 0
        self._consumed_failures = []
        self._public_tool_state = _thaw_json(self._config.public_tool_state)
        return EvaluationFeedback(
            EvaluationFeedbackType.INITIAL_INPUT,
            {
                "environment_id": self._config.environment_id,
                "initial": _thaw_json(self._config.initial_payload),
                "completion_context": _thaw_json(self._config.completion_context),
            },
        )

    def _matching_rule(self, action: EvaluationAction) -> FailureInjectionRule | None:
        for rule in self._config.failure_injections:
            if rule.rule_id not in self._consumed_failures and rule.matches(action, self._action_count):
                return rule
        return None

    def _failure_feedback(self, rule: FailureInjectionRule) -> EvaluationFeedback:
        self._consumed_failures.append(rule.rule_id)
        payload = {"failure_id": rule.rule_id, "metadata": _thaw_json(rule.metadata)}
        if rule.failure_type is FailureInjectionType.TIMEOUT:
            return EvaluationFeedback(EvaluationFeedbackType.TIMEOUT, payload)
        if rule.failure_type is FailureInjectionType.BUDGET_EXHAUSTION:
            return EvaluationFeedback(EvaluationFeedbackType.BUDGET, payload)
        if rule.failure_type is FailureInjectionType.INVALID_ACTION:
            return EvaluationFeedback(EvaluationFeedbackType.INVALID_ACTION, payload)
        return EvaluationFeedback(EvaluationFeedbackType.TOOL_FAILURE, payload)

    def apply(
        self,
        action: EvaluationAction,
        budget_state: EvaluationBudgetState,
    ) -> EvaluationFeedback:
        """Apply one public tool action under frozen priority rules.

        Real wall-clock deadlines are evaluator-owned and therefore must stop
        the loop before this method is called. Logical timeout injection is
        supported here as deterministic public feedback.
        """

        if not self._is_reset:
            raise RuntimeError("environment must be reset before apply")
        if not isinstance(action, EvaluationAction):
            raise TypeError("action must be an EvaluationAction")
        if not isinstance(budget_state, EvaluationBudgetState):
            raise TypeError("budget_state must be an EvaluationBudgetState")

        self._action_count += 1
        if budget_state.remaining_steps <= 0:
            return EvaluationFeedback(EvaluationFeedbackType.BUDGET, {"reason": "max_steps"})
        if (
            action.action_type is EvaluationActionType.TOOL_CALL
            and budget_state.remaining_tool_calls <= 0
        ):
            return EvaluationFeedback(EvaluationFeedbackType.BUDGET, {"reason": "max_tool_calls"})

        rule = self._matching_rule(action)
        if rule is not None and rule.failure_type in {
            FailureInjectionType.TIMEOUT,
            FailureInjectionType.BUDGET_EXHAUSTION,
        }:
            return self._failure_feedback(rule)

        if action.action_type is not EvaluationActionType.TOOL_CALL:
            return EvaluationFeedback(EvaluationFeedbackType.INVALID_ACTION, {"reason": "environment_accepts_tool_call_only"})
        tool_name = action.payload["tool_name"]
        if tool_name not in self._config.tool_responses:
            return EvaluationFeedback(EvaluationFeedbackType.INVALID_ACTION, {"reason": "unknown_tool", "tool_name": tool_name})

        if rule is not None:
            return self._failure_feedback(rule)

        return EvaluationFeedback(
            EvaluationFeedbackType.TOOL_RESPONSE,
            {
                "tool_name": tool_name,
                "parameters": _thaw_json(action.payload["parameters"]),
                "response": _thaw_json(self._config.tool_responses[tool_name]),
            },
        )

    def snapshot(self) -> EnvironmentSnapshot:
        """Return an immutable public state snapshot without private references."""

        return EnvironmentSnapshot(
            environment_id=self._config.environment_id,
            action_count=self._action_count,
            consumed_failures=tuple(self._consumed_failures),
            public_tool_state=_thaw_json(self._public_tool_state),
        )
