"""Immutable decision and evidence value models for M9 Meta-Inference."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping


class MetaInferenceDecisionStatus(str, Enum):
    """Selection-only outcomes for a future Meta-Inference engine."""

    SELECTED = "selected"
    UNAVAILABLE = "unavailable"
    REJECTED = "rejected"


def _freeze_value(value: Any) -> Any:
    """Recursively copy JSON-compatible data into immutable containers."""

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
    """Validate and freeze a public JSON-compatible mapping field."""

    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict")
    return _freeze_value(value)


@dataclass(frozen=True)
class DecisionEvidence:
    """Compact, immutable rationale for one Meta-Inference decision."""

    evidence_type: str
    description: str
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate evidence fields and remove caller-owned nested aliases."""

        if not isinstance(self.evidence_type, str):
            raise TypeError("evidence_type must be a str")
        if not self.evidence_type.strip():
            raise ValueError("evidence_type must not be empty")
        if not isinstance(self.description, str):
            raise TypeError("description must be a str")
        if not self.description.strip():
            raise ValueError("description must not be empty")
        object.__setattr__(self, "data", _freeze_mapping(self.data, "data"))

    def to_dict(self) -> dict[str, Any]:
        """Serialize evidence to fresh ordinary Python containers."""

        return {
            "evidence_type": self.evidence_type,
            "description": self.description,
            "data": _thaw_value(self.data),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DecisionEvidence":
        """Reconstruct evidence without coercing malformed input."""

        if not isinstance(data, dict):
            raise TypeError("DecisionEvidence data must be a dict")
        return cls(
            evidence_type=data["evidence_type"],
            description=data["description"],
            data=data.get("data", {}),
        )


@dataclass(frozen=True)
class MetaInferenceDecision:
    """Immutable selection result without selection or execution behavior."""

    status: MetaInferenceDecisionStatus
    selected_strategy: str | None
    evidence: tuple[DecisionEvidence, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate status invariants and protect nested public values."""

        if not isinstance(self.status, MetaInferenceDecisionStatus):
            raise TypeError("status must be a MetaInferenceDecisionStatus")
        if self.status is MetaInferenceDecisionStatus.SELECTED:
            if not isinstance(self.selected_strategy, str):
                raise TypeError("selected decisions require a strategy string")
            if not self.selected_strategy.strip():
                raise ValueError("selected_strategy must not be empty")
        elif self.selected_strategy is not None:
            raise ValueError("unavailable and rejected decisions require no strategy")

        if not isinstance(self.evidence, (list, tuple)):
            raise TypeError("evidence must be a list or tuple of DecisionEvidence")
        evidence = tuple(self.evidence)
        if not evidence:
            raise ValueError("evidence must not be empty")
        if any(not isinstance(item, DecisionEvidence) for item in evidence):
            raise TypeError("evidence must contain DecisionEvidence values")

        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        """Serialize this decision to fresh ordinary Python containers."""

        return {
            "status": self.status.value,
            "selected_strategy": self.selected_strategy,
            "evidence": [item.to_dict() for item in self.evidence],
            "metadata": _thaw_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MetaInferenceDecision":
        """Reconstruct a decision and its independent evidence values."""

        if not isinstance(data, dict):
            raise TypeError("MetaInferenceDecision data must be a dict")
        try:
            status = MetaInferenceDecisionStatus(data["status"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid MetaInferenceDecision status") from error
        evidence_data = data["evidence"]
        if not isinstance(evidence_data, (list, tuple)):
            raise TypeError("evidence must be a list or tuple")
        return cls(
            status=status,
            selected_strategy=data["selected_strategy"],
            evidence=tuple(DecisionEvidence.from_dict(item) for item in evidence_data),
            metadata=data.get("metadata", {}),
        )
