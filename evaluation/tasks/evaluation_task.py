"""Immutable task and scenario descriptions for controlled evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping

from src.core.task import Task


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("metadata keys must be strings")
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("metadata floats must be finite")
        return value
    raise ValueError("metadata must contain JSON-compatible data")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


@dataclass(frozen=True)
class EvaluationTask:
    """Immutable description of one future evaluation input."""

    name: str
    description: str
    task: Task
    category: str
    expected_behavior: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for value, name in ((self.name, "name"), (self.description, "description"), (self.category, "category"), (self.expected_behavior, "expected_behavior")):
            _text(value, name)
        if not isinstance(self.task, Task):
            raise TypeError("task must be a Task")
        if not isinstance(self.metadata, dict):
            raise TypeError("metadata must be a dict")
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "task": self.task.to_dict(), "category": self.category, "expected_behavior": self.expected_behavior, "metadata": _thaw(self.metadata)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationTask":
        if not isinstance(data, dict):
            raise TypeError("EvaluationTask data must be a dict")
        return cls(data["name"], data["description"], Task.from_dict(data["task"]), data["category"], data["expected_behavior"], data.get("metadata", {}))


@dataclass(frozen=True)
class EvaluationScenario:
    """Immutable expected setup for one evaluation task."""

    name: str
    description: str
    evaluation_task: EvaluationTask
    expected_outcome: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for value, name in ((self.name, "name"), (self.description, "description"), (self.expected_outcome, "expected_outcome")):
            _text(value, name)
        if not isinstance(self.evaluation_task, EvaluationTask):
            raise TypeError("evaluation_task must be an EvaluationTask")
        if not isinstance(self.metadata, dict):
            raise TypeError("metadata must be a dict")
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "evaluation_task": self.evaluation_task.to_dict(), "expected_outcome": self.expected_outcome, "metadata": _thaw(self.metadata)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationScenario":
        if not isinstance(data, dict):
            raise TypeError("EvaluationScenario data must be a dict")
        return cls(data["name"], data["description"], EvaluationTask.from_dict(data["evaluation_task"]), data["expected_outcome"], data.get("metadata", {}))
