"""Provider-independent, network-free LLM interpretation boundary models."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping, Protocol, TypeAlias, runtime_checkable

from src.core.task import Task


class ProviderFailureCategory(str, Enum):
    """Explicit provider outcomes that are separate from validation failures."""

    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    MALFORMED_RESPONSE = "malformed_response"
    INVALID_OUTPUT_FORMAT = "invalid_output_format"


def _freeze_value(value: Any) -> Any:
    """Recursively copy JSON-compatible data into immutable containers."""

    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("mapping keys must be strings")
        return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("float values must be finite")
        return value
    raise ValueError("values must be JSON-compatible data")


def _thaw_value(value: Any) -> Any:
    """Return fresh ordinary containers from recursively frozen data."""

    if isinstance(value, Mapping):
        return {key: _thaw_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    return deepcopy(value)


def _freeze_mapping(value: Any, name: str) -> Mapping[str, Any]:
    """Validate and freeze one public JSON-compatible mapping field."""

    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict")
    return _freeze_value(value)


@dataclass(frozen=True)
class ProviderResponse:
    """Untrusted, serializable raw provider payload with no execution authority."""

    payload: dict[str, Any]

    def __post_init__(self) -> None:
        """Validate and detach nested caller-owned provider data."""

        object.__setattr__(self, "payload", _freeze_mapping(self.payload, "payload"))

    def to_dict(self) -> dict[str, Any]:
        """Serialize this raw payload to fresh ordinary containers."""

        return {"payload": _thaw_value(self.payload)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderResponse":
        """Reconstruct an untrusted response without interpreting its payload."""

        if not isinstance(data, dict):
            raise TypeError("ProviderResponse data must be a dict")
        return cls(payload=data["payload"])


@dataclass(frozen=True)
class ProviderFailure:
    """Immutable explicit provider failure without fallback behavior."""

    category: ProviderFailureCategory
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate failure data and detach nested caller-owned evidence."""

        if not isinstance(self.category, ProviderFailureCategory):
            raise TypeError("category must be a ProviderFailureCategory")
        object.__setattr__(self, "evidence", _freeze_mapping(self.evidence, "evidence"))

    def to_dict(self) -> dict[str, Any]:
        """Serialize provider failure data to fresh ordinary containers."""

        return {"category": self.category.value, "evidence": _thaw_value(self.evidence)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderFailure":
        """Reconstruct a provider failure without coercing malformed input."""

        if not isinstance(data, dict):
            raise TypeError("ProviderFailure data must be a dict")
        try:
            category = ProviderFailureCategory(data["category"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid ProviderFailure category") from error
        return cls(category=category, evidence=data.get("evidence", {}))


ProviderResult: TypeAlias = ProviderResponse | ProviderFailure


@runtime_checkable
class LLMProvider(Protocol):
    """Provider boundary returning raw untrusted data or explicit failure."""

    def interpret(self, task: Task) -> ProviderResult:
        """Return one bounded provider result without interpretation or execution."""


@dataclass(frozen=True)
class FakeLLMProvider:
    """Stateless deterministic provider fixture with a fixed configured result."""

    result: ProviderResult

    def __post_init__(self) -> None:
        """Restrict the fake to the public provider result union."""

        if not isinstance(self.result, (ProviderResponse, ProviderFailure)):
            raise TypeError("result must be a ProviderResponse or ProviderFailure")

    def interpret(self, task: Task) -> ProviderResult:
        """Return the configured immutable result without network or retained task state."""

        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        return self.result
