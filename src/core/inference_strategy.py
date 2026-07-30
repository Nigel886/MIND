"""Immutable data model for controlled M9 inference strategy descriptors."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping


def _freeze_value(value: Any) -> Any:
    """Recursively copy a JSON-compatible value into immutable containers."""

    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("mapping keys must be strings")
        return MappingProxyType(
            {key: _freeze_value(item) for key, item in value.items()},
        )
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
    """Return fresh ordinary containers from a recursively frozen value."""

    if isinstance(value, Mapping):
        return {key: _thaw_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    return value


def _freeze_mapping(value: Any, name: str) -> Mapping[str, Any]:
    """Validate and freeze one public strategy mapping field."""

    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict")
    return _freeze_value(value)


@dataclass(frozen=True)
class InferenceStrategy:
    """An immutable, serializable descriptor of a controlled inference option."""

    name: str
    description: str
    capabilities: tuple[str, ...]
    configuration: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate fields and remove aliases to caller-owned nested values."""

        if not isinstance(self.name, str):
            raise TypeError("name must be a str")
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if self.name != self.name.strip():
            raise ValueError("name must not have leading or trailing whitespace")

        if not isinstance(self.description, str):
            raise TypeError("description must be a str")
        if not self.description.strip():
            raise ValueError("description must not be empty")

        if not isinstance(self.capabilities, (list, tuple)):
            raise TypeError("capabilities must be a list or tuple of strings")
        capabilities = tuple(self.capabilities)
        if not capabilities:
            raise ValueError("capabilities must not be empty")
        if any(not isinstance(capability, str) for capability in capabilities):
            raise TypeError("capabilities must contain strings")
        if any(not capability.strip() for capability in capabilities):
            raise ValueError("capabilities must not contain empty strings")
        if any(capability != capability.strip() for capability in capabilities):
            raise ValueError(
                "capabilities must not have leading or trailing whitespace",
            )
        if len(set(capabilities)) != len(capabilities):
            raise ValueError("capabilities must not contain duplicates")

        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(
            self,
            "configuration",
            _freeze_mapping(self.configuration, "configuration"),
        )
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to fresh, ordinary JSON-compatible Python containers."""

        return {
            "name": self.name,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "configuration": _thaw_value(self.configuration),
            "metadata": _thaw_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InferenceStrategy":
        """Reconstruct a descriptor without coercing malformed input."""

        if not isinstance(data, dict):
            raise TypeError("InferenceStrategy data must be a dict")
        return cls(
            name=data["name"],
            description=data["description"],
            capabilities=data["capabilities"],
            configuration=data.get("configuration", {}),
            metadata=data.get("metadata", {}),
        )
