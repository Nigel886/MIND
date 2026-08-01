"""Immutable M13 task-interpretation value models without provider behavior."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping


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
    """Validate and freeze a JSON-compatible mapping field."""

    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict")
    return _freeze_value(value)


def _normalize_capabilities(value: Any, name: str) -> tuple[str, ...]:
    """Validate an ordered capability sequence without changing its order."""

    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise TypeError(f"{name} must be a list or tuple of strings")
    capabilities = tuple(value)
    if any(not isinstance(item, str) for item in capabilities):
        raise TypeError(f"{name} must contain strings")
    if any(not item.strip() for item in capabilities):
        raise ValueError(f"{name} must not contain empty strings")
    if any(item != item.strip() for item in capabilities):
        raise ValueError(f"{name} must not have leading or trailing whitespace")
    if len(set(capabilities)) != len(capabilities):
        raise ValueError(f"{name} must not contain duplicates")
    return capabilities


@dataclass(frozen=True)
class TaskInterpretationProposal:
    """Untrusted, serializable LLM interpretation data without execution authority."""

    intent: str
    required_capabilities: tuple[str, ...] = ()
    constraints: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate fields and detach nested caller-owned values."""

        if not isinstance(self.intent, str):
            raise TypeError("intent must be a str")
        if not self.intent.strip():
            raise ValueError("intent must not be empty")
        if self.intent != self.intent.strip():
            raise ValueError("intent must not have leading or trailing whitespace")

        object.__setattr__(
            self,
            "required_capabilities",
            _normalize_capabilities(self.required_capabilities, "required_capabilities"),
        )
        object.__setattr__(self, "constraints", _freeze_mapping(self.constraints, "constraints"))
        object.__setattr__(self, "evidence", _freeze_mapping(self.evidence, "evidence"))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to fresh ordinary JSON-compatible containers."""

        return {
            "intent": self.intent,
            "required_capabilities": list(self.required_capabilities),
            "constraints": _thaw_value(self.constraints),
            "evidence": _thaw_value(self.evidence),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskInterpretationProposal":
        """Reconstruct an untrusted proposal without coercing malformed input."""

        if not isinstance(data, dict):
            raise TypeError("TaskInterpretationProposal data must be a dict")
        return cls(
            intent=data["intent"],
            required_capabilities=data.get("required_capabilities", ()),
            constraints=data.get("constraints", {}),
            evidence=data.get("evidence", {}),
        )


@dataclass(frozen=True)
class ValidatedRequirement:
    """Trusted, serializable requirement data produced by future validation only."""

    required_capabilities: tuple[str, ...] = ()
    constraints: dict[str, Any] = field(default_factory=dict)
    validation_evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate fields and detach nested caller-owned values."""

        object.__setattr__(
            self,
            "required_capabilities",
            _normalize_capabilities(self.required_capabilities, "required_capabilities"),
        )
        object.__setattr__(self, "constraints", _freeze_mapping(self.constraints, "constraints"))
        object.__setattr__(
            self,
            "validation_evidence",
            _freeze_mapping(self.validation_evidence, "validation_evidence"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to fresh ordinary JSON-compatible containers."""

        return {
            "required_capabilities": list(self.required_capabilities),
            "constraints": _thaw_value(self.constraints),
            "validation_evidence": _thaw_value(self.validation_evidence),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidatedRequirement":
        """Reconstruct a requirement without performing capability validation."""

        if not isinstance(data, dict):
            raise TypeError("ValidatedRequirement data must be a dict")
        return cls(
            required_capabilities=data.get("required_capabilities", ()),
            constraints=data.get("constraints", {}),
            validation_evidence=data.get("validation_evidence", {}),
        )


@dataclass(frozen=True)
class CapabilitySnapshot:
    """Immutable capability context detached from a mutable strategy registry."""

    strategy_capabilities: tuple[tuple[str, tuple[str, ...]], ...]
    vocabulary: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        """Validate ordered strategy capability data and derive its vocabulary."""

        if not isinstance(self.strategy_capabilities, (list, tuple)):
            raise TypeError("strategy_capabilities must be a list or tuple")

        strategies: list[tuple[str, tuple[str, ...]]] = []
        names: list[str] = []
        vocabulary: list[str] = []
        for item in self.strategy_capabilities:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise TypeError("strategy_capabilities entries must be name/capabilities pairs")
            name, capabilities = item
            if not isinstance(name, str):
                raise TypeError("strategy names must be strings")
            if not name.strip() or name != name.strip():
                raise ValueError("strategy names must not be empty or padded")
            normalized_capabilities = _normalize_capabilities(capabilities, "strategy capabilities")
            names.append(name)
            strategies.append((name, normalized_capabilities))
            for capability in normalized_capabilities:
                if capability not in vocabulary:
                    vocabulary.append(capability)

        if len(set(names)) != len(names):
            raise ValueError("strategy_capabilities must not contain duplicate strategy names")
        object.__setattr__(self, "strategy_capabilities", tuple(strategies))
        object.__setattr__(self, "vocabulary", tuple(vocabulary))

    def to_dict(self) -> dict[str, Any]:
        """Serialize ordered strategy capability data without registry references."""

        return {
            "strategy_capabilities": [
                {"name": name, "capabilities": list(capabilities)}
                for name, capabilities in self.strategy_capabilities
            ],
            "vocabulary": list(self.vocabulary),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilitySnapshot":
        """Reconstruct a snapshot and verify any supplied vocabulary."""

        if not isinstance(data, dict):
            raise TypeError("CapabilitySnapshot data must be a dict")
        entries = data["strategy_capabilities"]
        if not isinstance(entries, (list, tuple)):
            raise TypeError("strategy_capabilities must be a list or tuple")
        pairs: list[tuple[Any, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise TypeError("strategy_capabilities entries must be dicts")
            pairs.append((entry["name"], entry["capabilities"]))
        snapshot = cls(strategy_capabilities=tuple(pairs))
        if "vocabulary" in data:
            supplied = _normalize_capabilities(data["vocabulary"], "vocabulary")
            if supplied != snapshot.vocabulary:
                raise ValueError("vocabulary must match strategy_capabilities")
        return snapshot
