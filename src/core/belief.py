"""Belief models for the MIND-Lite runtime state."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _serialize_value(value: Any) -> Any:
    """Recursively serialize values to JSON-compatible structures.

    Args:
        value: Value to serialize.

    Returns:
        A serialized representation of the given value.
    """

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            key: _serialize_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    return value


@dataclass(frozen=True)
class BeliefRecord:
    """Represents a single atomic probabilistic belief record.

    This record-level structure follows the RFC definition for an
    individual belief and is colocated with ``Belief`` to keep the
    MIND-Lite prototype compact.

    Attributes:
        identifier: Symbolic identifier for the belief record.
        probability: Posterior probability for the belief.
        confidence: Estimated reliability of the belief.
        evidence: Supporting evidence associated with the belief.
        timestamp: Latest update time for the belief record.
    """

    identifier: str
    probability: float
    confidence: float
    evidence: Any = None
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the belief record to a dictionary.

        Returns:
            A JSON-compatible dictionary representation.
        """

        return _serialize_value(asdict(self))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BeliefRecord":
        """Deserialize a belief record from a dictionary.

        Args:
            data: Serialized belief record data.

        Returns:
            A reconstructed belief record instance.
        """

        timestamp = datetime.fromisoformat(data["timestamp"])
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        return cls(
            identifier=data["identifier"],
            probability=data["probability"],
            confidence=data["confidence"],
            evidence=data.get("evidence"),
            timestamp=timestamp,
        )


@dataclass(frozen=True)
class Belief:
    """Represents the complete immutable runtime belief state.

    The public API is intentionally minimal: this class only provides
    data representation and serialization interfaces. All inference and
    belief evolution logic belongs to the Inference Engine in a future
    milestone.

    Attributes:
        state: Mapping of belief record identifiers to belief records.
        confidence: Confidence scores for the current belief state.
        version: Version number of the belief state.
    """

    state: dict[str, BeliefRecord] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    version: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize the belief state to a dictionary.

        Returns:
            A JSON-compatible dictionary representation of the belief.
        """

        return _serialize_value(asdict(self))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Belief":
        """Deserialize a belief state from a dictionary.

        Args:
            data: Serialized belief data.

        Returns:
            A reconstructed belief instance.
        """

        state = {
            key: BeliefRecord.from_dict(record_data)
            for key, record_data in data["state"].items()
        }
        confidence = dict(data["confidence"])
        version = data["version"]

        return cls(
            state=state,
            confidence=confidence,
            version=version,
        )
