"""Immutable M19 deliberation and epistemic state projections.

These value objects carry validated input state for a future meta-control
policy.  They intentionally contain no resource accounting, policy, execution,
or runtime-transition behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any


class SignalAvailability(str, Enum):
    """Whether an epistemic signal is available for policy use."""

    AVAILABLE = "available"
    UNKNOWN = "unknown"


class SignalSource(str, Enum):
    """The formal provenance class of an available signal."""

    RUNTIME_DERIVED = "runtime_derived"
    MODEL_ESTIMATE = "model_estimate"


class RecoveryEventCategory(str, Enum):
    """Closed admitted failure/recovery categories from the M19 formalism."""

    UNAVAILABLE_ACTION_OR_TOOL = "unavailable_action_or_tool"
    INVALID_ACTION = "invalid_action"
    RECOVERABLE_FAILURE = "recoverable_failure"
    UNRECOVERABLE_FAILURE = "unrecoverable_failure"
    POLICY_FAILURE = "policy_failure"
    RECOVERY_ATTEMPT = "recovery_attempt"
    RECOVERY_SUCCESS = "recovery_success"


def _require_identity(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


def _require_version(value: object, name: str) -> str:
    return _require_identity(value, name)


@dataclass(frozen=True)
class EpistemicSignal:
    """One validated available or explicitly unknown epistemic signal."""

    availability: SignalAvailability
    value: float | None = None
    source: SignalSource | None = None
    scale_id: str | None = None
    version: str | None = None
    normalized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.availability, SignalAvailability):
            raise TypeError("availability must be a SignalAvailability")
        if not isinstance(self.normalized, bool):
            raise TypeError("normalized must be a bool")
        if self.availability is SignalAvailability.UNKNOWN:
            if any(item is not None for item in (self.value, self.source, self.scale_id, self.version)):
                raise ValueError("unknown signals must not carry a value or provenance")
            if self.normalized:
                raise ValueError("unknown signals must not declare normalization")
            return
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise TypeError("available signal value must be a finite number")
        if not isfinite(float(self.value)):
            raise ValueError("available signal value must be finite")
        if not isinstance(self.source, SignalSource):
            raise TypeError("available signals require a SignalSource")
        _require_identity(self.scale_id, "scale_id")
        _require_version(self.version, "version")
        if self.normalized and not 0.0 <= float(self.value) <= 1.0:
            raise ValueError("normalized signal value must be in [0, 1]")
        object.__setattr__(self, "value", float(self.value))

    @classmethod
    def unknown(cls) -> "EpistemicSignal":
        """Create the formal typed unavailable signal representation."""

        return cls(SignalAvailability.UNKNOWN)

    def to_dict(self) -> dict[str, Any]:
        return {
            "availability": self.availability.value,
            "value": self.value,
            "source": None if self.source is None else self.source.value,
            "scale_id": self.scale_id,
            "version": self.version,
            "normalized": self.normalized,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EpistemicSignal":
        if not isinstance(data, dict):
            raise TypeError("EpistemicSignal data must be a dict")
        try:
            source = data.get("source")
            return cls(
                SignalAvailability(data["availability"]),
                data.get("value"),
                None if source is None else SignalSource(source),
                data.get("scale_id"),
                data.get("version"),
                data.get("normalized", False),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid EpistemicSignal data") from error


def _require_non_negative(signal: EpistemicSignal, name: str) -> None:
    if signal.availability is SignalAvailability.AVAILABLE and signal.value < 0:
        raise ValueError(f"{name} must be non-negative when available")


@dataclass(frozen=True)
class EpistemicState:
    """Immutable M19 epistemic projection without decision behavior."""

    uncertainty: EpistemicSignal
    expected_information_gain: EpistemicSignal
    belief_stability: EpistemicSignal
    expected_task_value: EpistemicSignal
    expected_action_value: EpistemicSignal
    version: str
    transition_identity: str

    def __post_init__(self) -> None:
        for name in (
            "uncertainty",
            "expected_information_gain",
            "belief_stability",
            "expected_task_value",
            "expected_action_value",
        ):
            if not isinstance(getattr(self, name), EpistemicSignal):
                raise TypeError(f"{name} must be an EpistemicSignal")
        _require_non_negative(self.uncertainty, "uncertainty")
        _require_non_negative(self.expected_information_gain, "expected_information_gain")
        _require_non_negative(self.belief_stability, "belief_stability")
        _require_version(self.version, "version")
        _require_identity(self.transition_identity, "transition_identity")

    def to_dict(self) -> dict[str, Any]:
        return {
            "uncertainty": self.uncertainty.to_dict(),
            "expected_information_gain": self.expected_information_gain.to_dict(),
            "belief_stability": self.belief_stability.to_dict(),
            "expected_task_value": self.expected_task_value.to_dict(),
            "expected_action_value": self.expected_action_value.to_dict(),
            "version": self.version,
            "transition_identity": self.transition_identity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EpistemicState":
        if not isinstance(data, dict):
            raise TypeError("EpistemicState data must be a dict")
        try:
            return cls(
                EpistemicSignal.from_dict(data["uncertainty"]),
                EpistemicSignal.from_dict(data["expected_information_gain"]),
                EpistemicSignal.from_dict(data["belief_stability"]),
                EpistemicSignal.from_dict(data["expected_task_value"]),
                EpistemicSignal.from_dict(data["expected_action_value"]),
                data["version"],
                data["transition_identity"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid EpistemicState data") from error


@dataclass(frozen=True)
class RecoveryEvent:
    """One compact, ordered, admitted failure or recovery event."""

    category: RecoveryEventCategory
    transition_identity: str

    def __post_init__(self) -> None:
        if not isinstance(self.category, RecoveryEventCategory):
            raise TypeError("category must be a RecoveryEventCategory")
        _require_identity(self.transition_identity, "transition_identity")

    def to_dict(self) -> dict[str, str]:
        return {"category": self.category.value, "transition_identity": self.transition_identity}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecoveryEvent":
        if not isinstance(data, dict):
            raise TypeError("RecoveryEvent data must be a dict")
        try:
            return cls(RecoveryEventCategory(data["category"]), data["transition_identity"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid RecoveryEvent data") from error


@dataclass(frozen=True)
class FailureRecoveryProjection:
    """Immutable ordered compact recovery/failure projection for future policy."""

    events: tuple[RecoveryEvent, ...]
    version: str
    transition_identity: str

    def __post_init__(self) -> None:
        if isinstance(self.events, list) or not isinstance(self.events, tuple):
            raise TypeError("events must be an ordered tuple")
        if any(not isinstance(event, RecoveryEvent) for event in self.events):
            raise TypeError("events must contain RecoveryEvent values")
        _require_version(self.version, "version")
        _require_identity(self.transition_identity, "transition_identity")

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": [event.to_dict() for event in self.events],
            "version": self.version,
            "transition_identity": self.transition_identity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FailureRecoveryProjection":
        if not isinstance(data, dict):
            raise TypeError("FailureRecoveryProjection data must be a dict")
        try:
            events = data["events"]
            if not isinstance(events, list):
                raise TypeError("events must be a list")
            return cls(
                tuple(RecoveryEvent.from_dict(item) for item in events),
                data["version"],
                data["transition_identity"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid FailureRecoveryProjection data") from error


@dataclass(frozen=True)
class DeliberationState:
    """Small immutable M19 policy-input projection excluding resource accounting."""

    runtime_projection_identity: str
    epistemic_state: EpistemicState
    failure_recovery: FailureRecoveryProjection
    version: str
    transition_identity: str

    def __post_init__(self) -> None:
        _require_identity(self.runtime_projection_identity, "runtime_projection_identity")
        if not isinstance(self.epistemic_state, EpistemicState):
            raise TypeError("epistemic_state must be an EpistemicState")
        if not isinstance(self.failure_recovery, FailureRecoveryProjection):
            raise TypeError("failure_recovery must be a FailureRecoveryProjection")
        _require_version(self.version, "version")
        _require_identity(self.transition_identity, "transition_identity")

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_projection_identity": self.runtime_projection_identity,
            "epistemic_state": self.epistemic_state.to_dict(),
            "failure_recovery": self.failure_recovery.to_dict(),
            "version": self.version,
            "transition_identity": self.transition_identity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeliberationState":
        if not isinstance(data, dict):
            raise TypeError("DeliberationState data must be a dict")
        try:
            return cls(
                data["runtime_projection_identity"],
                EpistemicState.from_dict(data["epistemic_state"]),
                FailureRecoveryProjection.from_dict(data["failure_recovery"]),
                data["version"],
                data["transition_identity"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid DeliberationState data") from error
