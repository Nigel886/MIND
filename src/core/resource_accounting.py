"""Immutable M19 resource-accounting values without policy or execution."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping


class ResourceDimension(str, Enum):
    """Required typed M19 resource dimensions."""

    REASONING_STEP = "reasoning_step"
    TOOL_ATTEMPT = "tool_attempt"
    PROVIDER_INTERACTION = "provider_interaction"


def _identity(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _amount(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    if value < 0:
        raise ValueError(f"{name} must not be negative")
    return value


def _freeze(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("cost metadata floats must be finite")
        return value
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("cost metadata keys must be strings")
            output[key] = _freeze(item)
        return MappingProxyType(output)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    raise TypeError("cost metadata must be JSON-compatible")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class ResourceAllocation:
    """Canonical capacity/consumption representation for one dimension."""

    dimension: ResourceDimension
    capacity: int
    consumed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, ResourceDimension):
            raise TypeError("dimension must be a ResourceDimension")
        _amount(self.capacity, "capacity")
        _amount(self.consumed, "consumed")
        if self.consumed > self.capacity:
            raise ValueError("consumed must not exceed capacity")

    @property
    def remaining(self) -> int:
        """Derived remaining capacity; never an independent mutable value."""

        return self.capacity - self.consumed

    @property
    def exhausted(self) -> bool:
        """Whether no further positive unit can be consumed."""

        return self.remaining == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension.value,
            "capacity": self.capacity,
            "consumed": self.consumed,
            "remaining": self.remaining,
            "exhausted": self.exhausted,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResourceAllocation":
        if not isinstance(data, dict):
            raise TypeError("ResourceAllocation data must be a dict")
        try:
            allocation = cls(
                ResourceDimension(data["dimension"]), data["capacity"], data["consumed"],
            )
            if data.get("remaining", allocation.remaining) != allocation.remaining:
                raise ValueError("serialized remaining is inconsistent")
            if data.get("exhausted", allocation.exhausted) != allocation.exhausted:
                raise ValueError("serialized exhausted is inconsistent")
            return allocation
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid ResourceAllocation data") from error


@dataclass(frozen=True)
class ResourceState:
    """Immutable M19 resource projection with pure consumption transitions."""

    allocations: tuple[ResourceAllocation, ...]
    allocation_identity: str
    version: str
    transition_identity: str
    cost_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.allocations, list) or not isinstance(self.allocations, tuple):
            raise TypeError("allocations must be an ordered tuple")
        if any(not isinstance(item, ResourceAllocation) for item in self.allocations):
            raise TypeError("allocations must contain ResourceAllocation values")
        expected = tuple(ResourceDimension)
        dimensions = tuple(item.dimension for item in self.allocations)
        if dimensions != expected:
            raise ValueError("allocations must contain each required dimension in canonical order")
        _identity(self.allocation_identity, "allocation_identity")
        _identity(self.version, "version")
        _identity(self.transition_identity, "transition_identity")
        if not isinstance(self.cost_metadata, Mapping):
            raise TypeError("cost_metadata must be a mapping")
        object.__setattr__(self, "cost_metadata", _freeze(self.cost_metadata))

    def allocation(self, dimension: ResourceDimension) -> ResourceAllocation:
        """Return the immutable allocation for one typed dimension."""

        if not isinstance(dimension, ResourceDimension):
            raise TypeError("dimension must be a ResourceDimension")
        return self.allocations[tuple(ResourceDimension).index(dimension)]

    def consume(
        self,
        dimension: ResourceDimension,
        amount: int,
        transition_identity: str,
    ) -> "ResourceState":
        """Return a new state after one admitted positive resource consumption."""

        if not isinstance(dimension, ResourceDimension):
            raise TypeError("dimension must be a ResourceDimension")
        _amount(amount, "amount")
        if amount == 0:
            raise ValueError("amount must be positive")
        _identity(transition_identity, "transition_identity")
        current = self.allocation(dimension)
        if current.exhausted:
            raise ValueError("resource dimension is exhausted")
        if amount > current.remaining:
            raise ValueError("amount exceeds remaining capacity")
        index = tuple(ResourceDimension).index(dimension)
        updated = replace(current, consumed=current.consumed + amount)
        allocations = self.allocations[:index] + (updated,) + self.allocations[index + 1:]
        return replace(self, allocations=allocations, transition_identity=transition_identity)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allocations": [item.to_dict() for item in self.allocations],
            "allocation_identity": self.allocation_identity,
            "version": self.version,
            "transition_identity": self.transition_identity,
            "cost_metadata": _thaw(self.cost_metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResourceState":
        if not isinstance(data, dict):
            raise TypeError("ResourceState data must be a dict")
        try:
            allocations = data["allocations"]
            if not isinstance(allocations, list):
                raise TypeError("allocations must be a list")
            return cls(
                tuple(ResourceAllocation.from_dict(item) for item in allocations),
                data["allocation_identity"], data["version"], data["transition_identity"],
                data.get("cost_metadata", {}),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid ResourceState data") from error
