"""Observation model for immutable runtime observations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Observation:
    """Represents a single immutable observation from the environment.

    Attributes:
        id: Unique observation identifier.
        timestamp: UTC creation time for the observation.
        source: Origin of the observation.
        content: Raw observation payload.
    """

    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    source: str = ""
    content: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the observation to a JSON-compatible dictionary.

        Returns:
            A dictionary representation of the observation.
        """

        data = asdict(self)
        data["id"] = str(self.id)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Observation":
        """Deserialize an observation from a dictionary.

        Args:
            data: Serialized observation data.

        Returns:
            A reconstructed observation instance.
        """

        timestamp = datetime.fromisoformat(data["timestamp"])
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        return cls(
            id=UUID(data["id"]),
            timestamp=timestamp,
            source=data["source"],
            content=data["content"],
        )

    def __repr__(self) -> str:
        """Return a readable representation for debugging and inspection.

        Returns:
            A string representation of the observation.
        """

        return (
            "Observation("
            f"id=UUID('{self.id}'), "
            f"timestamp={self.timestamp.isoformat()!r}, "
            f"source={self.source!r}, "
            f"content={self.content!r}"
            ")"
        )
