"""Deterministic provider-free validation for M13 task-interpretation proposals."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias

from src.core.task_interpretation import (
    CapabilitySnapshot,
    TaskInterpretationProposal,
    ValidatedRequirement,
)


class ValidationFailureCategory(str, Enum):
    """Explicit deterministic outcomes for proposal validation failures."""

    INVALID_PROPOSAL = "invalid_proposal"
    UNSUPPORTED_CAPABILITY = "unsupported_capability"
    INVALID_CONSTRAINT = "invalid_constraint"


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
    """Validate and freeze one compact JSON-compatible evidence mapping."""

    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict")
    return _freeze_value(value)


@dataclass(frozen=True)
class ValidationFailure:
    """Immutable, explicit validation failure without fallback behavior."""

    category: ValidationFailureCategory
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate failure data and protect nested caller-owned evidence."""

        if not isinstance(self.category, ValidationFailureCategory):
            raise TypeError("category must be a ValidationFailureCategory")
        object.__setattr__(self, "evidence", _freeze_mapping(self.evidence, "evidence"))

    def to_dict(self) -> dict[str, Any]:
        """Serialize failure data to fresh ordinary containers."""

        return {"category": self.category.value, "evidence": _thaw_value(self.evidence)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationFailure":
        """Reconstruct explicit failure data without coercing malformed input."""

        if not isinstance(data, dict):
            raise TypeError("ValidationFailure data must be a dict")
        try:
            category = ValidationFailureCategory(data["category"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid ValidationFailure category") from error
        return cls(category=category, evidence=data.get("evidence", {}))


ValidationResult: TypeAlias = ValidatedRequirement | ValidationFailure


def validate_proposal(
    proposal: TaskInterpretationProposal,
    snapshot: CapabilitySnapshot,
) -> ValidationResult:
    """Project one untrusted proposal into a requirement or explicit failure."""

    if not isinstance(proposal, TaskInterpretationProposal):
        raise TypeError("proposal must be a TaskInterpretationProposal")
    if not isinstance(snapshot, CapabilitySnapshot):
        raise TypeError("snapshot must be a CapabilitySnapshot")

    for capability in proposal.required_capabilities:
        if capability not in snapshot.vocabulary:
            return ValidationFailure(
                ValidationFailureCategory.UNSUPPORTED_CAPABILITY,
                {"capability": capability, "outcome": "invalid"},
            )

    try:
        normalized_constraints = proposal.to_dict()["constraints"]
        return ValidatedRequirement(
            required_capabilities=proposal.required_capabilities,
            constraints=normalized_constraints,
            validation_evidence={
                "outcome": "valid",
                "validated_capabilities": list(proposal.required_capabilities),
            },
        )
    except (TypeError, ValueError):
        return ValidationFailure(
            ValidationFailureCategory.INVALID_CONSTRAINT,
            {"outcome": "invalid"},
        )
