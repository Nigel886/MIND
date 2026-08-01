"""Immutable contracts and metrics for M14 Cohort A evaluation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping

from src.evaluation.contracts import EvaluationOutcome, EvaluationOutcomeType
from src.evaluation.environment import EnvironmentConfig
from src.evaluation.execution import EvaluationBudget


class M14CohortATaskCategory(str, Enum):
    """Registered task categories for the frozen M14 suite."""

    DIRECT_TASK = "direct_task"
    CONTROLLED_TOOL_TASK = "controlled_tool_task"
    MULTI_STEP_DEPENDENCY_TASK = "multi_step_dependency_task"
    FAILURE_RECOVERY_TASK = "failure_recovery_task"


class M14CohortADifficulty(str, Enum):
    """Registered difficulty levels for the frozen M14 suite."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


_FORBIDDEN_RECORD_KEYS = frozenset(
    {
        "chain_of_thought", "cot", "hidden_reasoning", "prompt", "prompts",
        "credential", "credentials", "api_key", "api_keys", "secret", "secrets",
        "runtime_state", "belief", "policy",
    }
)


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("mapping keys must be strings")
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("float values must be finite")
        return value
    raise ValueError("value must be JSON-compatible")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return deepcopy(value)


def _text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    if value != value.strip():
        raise ValueError(f"{name} must not have leading or trailing whitespace")


def _non_negative_int(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, not bool")
    if value < 0:
        raise ValueError(f"{name} must not be negative")


def _validate_public_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key.casefold() in _FORBIDDEN_RECORD_KEYS:
                raise ValueError(f"public record must not contain {key}")
            _validate_public_keys(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _validate_public_keys(item)


def canonical_json_hash(data: Any) -> str:
    """Return a stable SHA-256 hash for JSON-compatible public data."""

    frozen = _freeze_json(data)
    encoded = json.dumps(
        _thaw_json(frozen),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class M14CohortATaskFixture:
    """Frozen task/environment/budget registration independent of an Agent."""

    task_id: str
    category: M14CohortATaskCategory
    difficulty: M14CohortADifficulty
    task_definition: dict[str, Any]
    environment_config: EnvironmentConfig
    budget: EvaluationBudget
    completion_rule_version: str

    def __post_init__(self) -> None:
        _text(self.task_id, "task_id")
        if not isinstance(self.category, M14CohortATaskCategory):
            raise TypeError("category must be an M14CohortATaskCategory")
        if not isinstance(self.difficulty, M14CohortADifficulty):
            raise TypeError("difficulty must be an M14CohortADifficulty")
        if not isinstance(self.task_definition, dict):
            raise TypeError("task_definition must be a dict")
        if not isinstance(self.environment_config, EnvironmentConfig):
            raise TypeError("environment_config must be an EnvironmentConfig")
        if not isinstance(self.budget, EvaluationBudget):
            raise TypeError("budget must be an EvaluationBudget")
        _text(self.completion_rule_version, "completion_rule_version")
        object.__setattr__(self, "task_definition", _freeze_json(self.task_definition))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "category": self.category.value,
            "difficulty": self.difficulty.value,
            "task_definition": _thaw_json(self.task_definition),
            "environment_config": self.environment_config.to_dict(),
            "budget": self.budget.to_dict(),
            "completion_rule_version": self.completion_rule_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "M14CohortATaskFixture":
        if not isinstance(data, dict):
            raise TypeError("M14CohortATaskFixture data must be a dict")
        try:
            category = M14CohortATaskCategory(data["category"])
            difficulty = M14CohortADifficulty(data["difficulty"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid M14 fixture enum value") from error
        return cls(
            task_id=data["task_id"],
            category=category,
            difficulty=difficulty,
            task_definition=data["task_definition"],
            environment_config=EnvironmentConfig.from_dict(data["environment_config"]),
            budget=EvaluationBudget.from_dict(data["budget"]),
            completion_rule_version=data["completion_rule_version"],
        )


def fixture_suite_hash(fixtures: tuple[M14CohortATaskFixture, ...]) -> str:
    """Hash the ordered public fixture suite; ordering is part of the result."""

    if not isinstance(fixtures, tuple):
        raise TypeError("fixtures must be a tuple")
    if any(not isinstance(fixture, M14CohortATaskFixture) for fixture in fixtures):
        raise TypeError("fixtures must contain M14CohortATaskFixture values")
    if len({fixture.task_id for fixture in fixtures}) != len(fixtures):
        raise ValueError("fixtures must not contain duplicate task_id values")
    return canonical_json_hash([fixture.to_dict() for fixture in fixtures])


@dataclass(frozen=True)
class CohortAResultRecord:
    """Compact public outcome record for one deterministic evaluation episode."""

    task_id: str
    baseline_id: str
    repeat_index: int
    outcome: EvaluationOutcome
    trace_summary: dict[str, Any]
    resource_usage: dict[str, Any]
    configuration_hash: str

    def __post_init__(self) -> None:
        _text(self.task_id, "task_id")
        _text(self.baseline_id, "baseline_id")
        _non_negative_int(self.repeat_index, "repeat_index")
        if not isinstance(self.outcome, EvaluationOutcome):
            raise TypeError("outcome must be an EvaluationOutcome")
        if not isinstance(self.trace_summary, dict):
            raise TypeError("trace_summary must be a dict")
        if not isinstance(self.resource_usage, dict):
            raise TypeError("resource_usage must be a dict")
        _text(self.configuration_hash, "configuration_hash")
        _validate_public_keys(self.trace_summary)
        _validate_public_keys(self.resource_usage)
        object.__setattr__(self, "trace_summary", _freeze_json(self.trace_summary))
        object.__setattr__(self, "resource_usage", _freeze_json(self.resource_usage))

    @property
    def deterministic_signature(self) -> str:
        """Return a stable compact signature over permitted semantic fields."""

        return canonical_json_hash(
            {
                "task_id": self.task_id,
                "baseline_id": self.baseline_id,
                "outcome": self.outcome.to_dict(),
                "trace_summary": _thaw_json(self.trace_summary),
                "resource_usage": _thaw_json(self.resource_usage),
                "configuration_hash": self.configuration_hash,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "baseline_id": self.baseline_id,
            "repeat_index": self.repeat_index,
            "outcome": self.outcome.to_dict(),
            "trace_summary": _thaw_json(self.trace_summary),
            "resource_usage": _thaw_json(self.resource_usage),
            "configuration_hash": self.configuration_hash,
            "deterministic_signature": self.deterministic_signature,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CohortAResultRecord":
        if not isinstance(data, dict):
            raise TypeError("CohortAResultRecord data must be a dict")
        return cls(
            task_id=data["task_id"],
            baseline_id=data["baseline_id"],
            repeat_index=data["repeat_index"],
            outcome=EvaluationOutcome.from_dict(data["outcome"]),
            trace_summary=data["trace_summary"],
            resource_usage=data["resource_usage"],
            configuration_hash=data["configuration_hash"],
        )


@dataclass(frozen=True)
class CohortAMetrics:
    """Descriptive Cohort A aggregates; not an intelligence-quality score."""

    total_runs: int
    outcome_counts: dict[str, int]
    total_steps: int
    total_tool_calls: int
    failure_categories: dict[str, int]
    recovery_attempts: int
    successful_recoveries: int
    resource_counters: dict[str, int]

    def __post_init__(self) -> None:
        for name in ("total_runs", "total_steps", "total_tool_calls", "recovery_attempts", "successful_recoveries"):
            _non_negative_int(getattr(self, name), name)
        if self.successful_recoveries > self.recovery_attempts:
            raise ValueError("successful_recoveries must not exceed recovery_attempts")
        for name in ("outcome_counts", "failure_categories", "resource_counters"):
            value = getattr(self, name)
            if not isinstance(value, dict):
                raise TypeError(f"{name} must be a dict")
            if any(not isinstance(key, str) for key in value):
                raise TypeError(f"{name} keys must be strings")
            if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in value.values()):
                raise ValueError(f"{name} values must be non-negative ints")
            object.__setattr__(self, name, MappingProxyType(dict(value)))

    @property
    def success_rate(self) -> float:
        if not self.total_runs:
            return 0.0
        return self.outcome_counts.get(EvaluationOutcomeType.SUCCESS.value, 0) / self.total_runs

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_runs": self.total_runs,
            "outcome_counts": dict(self.outcome_counts),
            "total_steps": self.total_steps,
            "total_tool_calls": self.total_tool_calls,
            "failure_categories": dict(self.failure_categories),
            "recovery_attempts": self.recovery_attempts,
            "successful_recoveries": self.successful_recoveries,
            "resource_counters": dict(self.resource_counters),
            "success_rate": self.success_rate,
        }


def aggregate_cohort_a_metrics(records: tuple[CohortAResultRecord, ...]) -> CohortAMetrics:
    """Aggregate public result records in their supplied deterministic order."""

    if not isinstance(records, tuple):
        raise TypeError("records must be a tuple")
    if any(not isinstance(record, CohortAResultRecord) for record in records):
        raise TypeError("records must contain CohortAResultRecord values")
    outcomes: dict[str, int] = {}
    failures: dict[str, int] = {}
    counters: dict[str, int] = {}
    steps = tool_calls = recovery_attempts = successful_recoveries = 0
    for record in records:
        outcome_key = record.outcome.outcome_type.value
        outcomes[outcome_key] = outcomes.get(outcome_key, 0) + 1
        usage = record.resource_usage
        steps += int(usage.get("steps", 0))
        tool_calls += int(usage.get("tool_calls", 0))
        for key, value in usage.get("resource_counters", {}).items():
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                counters[key] = counters.get(key, 0) + value
        failure = record.outcome.payload.get("failure_category")
        if isinstance(failure, str):
            failures[failure] = failures.get(failure, 0) + 1
        if record.outcome.payload.get("recovery_attempted") is True:
            recovery_attempts += 1
        if record.outcome.payload.get("recovery_successful") is True:
            successful_recoveries += 1
    return CohortAMetrics(
        total_runs=len(records),
        outcome_counts=outcomes,
        total_steps=steps,
        total_tool_calls=tool_calls,
        failure_categories=failures,
        recovery_attempts=recovery_attempts,
        successful_recoveries=successful_recoveries,
        resource_counters=counters,
    )
