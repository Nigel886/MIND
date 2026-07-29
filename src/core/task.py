"""Immutable Task and Goal value models for MIND-Lite M8."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Sequence
from uuid import UUID, uuid4


def _freeze(value: Any) -> Any:
    """Recursively copy mutable payload values into immutable containers."""

    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("mapping keys must be strings")
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return deepcopy(value)


def _thaw(value: Any) -> Any:
    """Return a fresh, ordinary-container serialization of a frozen value."""

    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return sorted((_thaw(item) for item in value), key=repr)
    return deepcopy(value)


def _freeze_mapping(value: Any, name: str) -> Mapping[str, Any]:
    """Validate and recursively freeze a public mapping field."""

    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict")
    return _freeze(value)


@dataclass(frozen=True)
class Goal:
    """An immutable desired outcome with ordered success criteria."""

    description: str
    success_criteria: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate fields and remove aliases to caller-owned mutable values."""

        if not isinstance(self.description, str):
            raise TypeError("description must be a str")
        if not self.description.strip():
            raise ValueError("description must not be empty")
        if isinstance(self.success_criteria, str) or not isinstance(
            self.success_criteria,
            Sequence,
        ):
            raise TypeError("success_criteria must be a sequence of strings")

        criteria = tuple(self.success_criteria)
        if not criteria:
            raise ValueError("success_criteria must not be empty")
        if any(not isinstance(item, str) for item in criteria):
            raise TypeError("success criteria must be strings")
        if any(not item.strip() for item in criteria):
            raise ValueError("success criteria must not be empty")

        object.__setattr__(self, "success_criteria", criteria)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        """Serialize this Goal to fresh ordinary Python containers."""

        return {
            "description": self.description,
            "success_criteria": list(self.success_criteria),
            "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Goal":
        """Reconstruct a Goal from its serialized representation."""

        if not isinstance(data, dict):
            raise TypeError("Goal data must be a dict")
        return cls(
            description=data["description"],
            success_criteria=data["success_criteria"],
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class Task:
    """An immutable user-level request which owns exactly one Goal."""

    goal: Goal
    input: dict[str, Any]
    context: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        """Validate identity and recursively freeze task payload fields."""

        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")
        if not isinstance(self.goal, Goal):
            raise TypeError("goal must be a Goal")

        object.__setattr__(self, "input", _freeze_mapping(self.input, "input"))
        object.__setattr__(self, "context", _freeze_mapping(self.context, "context"))
        object.__setattr__(self, "constraints", _freeze_mapping(self.constraints, "constraints"))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        """Serialize this Task to fresh ordinary Python containers."""

        return {
            "id": str(self.id),
            "goal": self.goal.to_dict(),
            "input": _thaw(self.input),
            "context": _thaw(self.context),
            "constraints": _thaw(self.constraints),
            "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        """Reconstruct a Task and its nested Goal from serialized data."""

        if not isinstance(data, dict):
            raise TypeError("Task data must be a dict")
        try:
            identifier = UUID(data["id"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid Task id") from error

        return cls(
            id=identifier,
            goal=Goal.from_dict(data["goal"]),
            input=data["input"],
            context=data.get("context", {}),
            constraints=data.get("constraints", {}),
            metadata=data.get("metadata", {}),
        )
