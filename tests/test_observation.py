"""Unit tests for the Observation model."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import timezone
from uuid import UUID

from src.core.observation import Observation


class ObservationTest(unittest.TestCase):
    """Tests for the immutable Observation model."""

    def test_observation_creation(self) -> None:
        """Creates an observation with expected field values."""

        observation = Observation(source="user", content={"message": "hello"})

        self.assertEqual(observation.source, "user")
        self.assertEqual(observation.content, {"message": "hello"})
        self.assertIn("Observation(", repr(observation))

    def test_uuid_is_generated_automatically(self) -> None:
        """Generates a UUID for each observation automatically."""

        first = Observation(source="user", content="a")
        second = Observation(source="user", content="b")

        self.assertIsInstance(first.id, UUID)
        self.assertIsInstance(second.id, UUID)
        self.assertNotEqual(first.id, second.id)

    def test_timestamp_is_generated_in_utc(self) -> None:
        """Generates a timezone-aware UTC timestamp automatically."""

        observation = Observation(source="tool", content="result")

        self.assertIsNotNone(observation.timestamp.tzinfo)
        self.assertEqual(observation.timestamp.tzinfo, timezone.utc)

    def test_serialization(self) -> None:
        """Serializes an observation to a dictionary."""

        observation = Observation(source="api", content={"status": "ok"})
        data = observation.to_dict()

        self.assertEqual(data["id"], str(observation.id))
        self.assertEqual(data["timestamp"], observation.timestamp.isoformat())
        self.assertEqual(data["source"], observation.source)
        self.assertEqual(data["content"], observation.content)

    def test_deserialization(self) -> None:
        """Deserializes an observation from a dictionary."""

        original = Observation(source="runtime", content={"step": 1})
        data = original.to_dict()

        restored = Observation.from_dict(data)

        self.assertEqual(restored, original)
        self.assertIsInstance(restored.id, UUID)
        self.assertEqual(restored.timestamp.tzinfo, timezone.utc)

    def test_observation_is_immutable(self) -> None:
        """Prevents mutation after observation creation."""

        observation = Observation(source="user", content="immutable")

        with self.assertRaises(FrozenInstanceError):
            observation.source = "tool"
