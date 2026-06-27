"""RuntimeState model for the MIND-Lite runtime subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.core.belief import Belief
from src.core.observation import Observation


def _serialize_metadata_value(value: Any) -> Any:
    """Recursively serialize runtime metadata values.

    Metadata is treated as an opaque container during the prototype
    stage. This helper preserves that design by avoiding schema
    validation while still supporting serialization of common nested
    values.

    Args:
        value: Runtime metadata value to serialize.

    Returns:
        A serialized representation of the metadata value.
    """

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            key: _serialize_metadata_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_serialize_metadata_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_metadata_value(item) for item in value]
    return value


@dataclass(frozen=True)
class RuntimeState:
    """Represents the immutable runtime state for the prototype.

    RuntimeState is a passive data container. It stores the current
    observation, the current belief, and opaque runtime metadata. It
    intentionally exposes no convenience APIs for orchestration or
    lifecycle management.

    Attributes:
        observation: Current immutable observation.
        belief: Current immutable belief state.
        metadata: Opaque runtime metadata container for the prototype.
    """

    observation: Observation
    belief: Belief
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the runtime state to a dictionary.

        Nested serialization is delegated to the Observation and Belief
        models to keep the serialization strategy consistent across the
        core runtime models.

        Returns:
            A dictionary representation of the runtime state.
        """

        return {
            "observation": self.observation.to_dict(),
            "belief": self.belief.to_dict(),
            "metadata": _serialize_metadata_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeState":
        """Deserialize a runtime state from a dictionary.

        Nested reconstruction is delegated to the Observation and Belief
        models to keep the reconstruction strategy consistent across the
        core runtime models.

        Args:
            data: Serialized runtime state data.

        Returns:
            A reconstructed runtime state instance.
        """

        return cls(
            observation=Observation.from_dict(data["observation"]),
            belief=Belief.from_dict(data["belief"]),
            metadata=dict(data["metadata"]),
        )
