"""Unit tests for the runtime state module."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from src.core.belief import Belief, BeliefRecord
from src.core.observation import Observation
from src.core.runtime import RuntimeState


class RuntimeStateTest(unittest.TestCase):
    """Tests for the RuntimeState model."""

    def _create_observation(self) -> Observation:
        """Create a reusable observation fixture.

        Returns:
            An immutable observation instance.
        """

        return Observation(
            source="user",
            content={"message": "hello"},
        )

    def _create_belief(self) -> Belief:
        """Create a reusable belief fixture.

        Returns:
            An immutable belief instance.
        """

        record = BeliefRecord(
            identifier="NeedResponse",
            probability=0.92,
            confidence=0.88,
            evidence={"source": "user"},
        )
        return Belief(
            state={"NeedResponse": record},
            confidence={"NeedResponse": 0.88},
            version=2,
        )

    def test_runtime_state_creation(self) -> None:
        """Creates a runtime state with observation, belief, and metadata."""

        runtime_state = RuntimeState(
            observation=self._create_observation(),
            belief=self._create_belief(),
            metadata={"phase": "prototype"},
        )

        self.assertEqual(runtime_state.observation.source, "user")
        self.assertEqual(runtime_state.belief.version, 2)
        self.assertEqual(runtime_state.metadata, {"phase": "prototype"})

    def test_runtime_state_is_immutable(self) -> None:
        """Prevents attribute mutation after creation."""

        runtime_state = RuntimeState(
            observation=self._create_observation(),
            belief=self._create_belief(),
        )

        with self.assertRaises(FrozenInstanceError):
            runtime_state.metadata = {"changed": True}

    def test_runtime_state_has_minimal_public_api(self) -> None:
        """Exposes only data and serialization interfaces."""

        self.assertFalse(hasattr(RuntimeState, "initialize"))
        self.assertFalse(hasattr(RuntimeState, "step"))
        self.assertFalse(hasattr(RuntimeState, "run"))
        self.assertFalse(hasattr(RuntimeState, "stop"))
        self.assertFalse(hasattr(RuntimeState, "reset"))
        self.assertTrue(hasattr(RuntimeState, "to_dict"))
        self.assertTrue(hasattr(RuntimeState, "from_dict"))

    def test_runtime_state_serialization_delegates_nested_models(self) -> None:
        """Serializes nested observation and belief through their APIs."""

        observation = self._create_observation()
        belief = self._create_belief()
        runtime_state = RuntimeState(
            observation=observation,
            belief=belief,
            metadata={"note": "opaque"},
        )

        data = runtime_state.to_dict()

        self.assertEqual(data["observation"], observation.to_dict())
        self.assertEqual(data["belief"], belief.to_dict())
        self.assertEqual(data["metadata"], {"note": "opaque"})

    def test_runtime_state_deserialization_delegates_nested_models(self) -> None:
        """Reconstructs nested observation and belief through their APIs."""

        observation = self._create_observation()
        belief = self._create_belief()
        data = {
            "observation": observation.to_dict(),
            "belief": belief.to_dict(),
            "metadata": {"stage": "m3-01"},
        }

        runtime_state = RuntimeState.from_dict(data)

        self.assertEqual(runtime_state.observation, observation)
        self.assertEqual(runtime_state.belief, belief)
        self.assertEqual(runtime_state.metadata, {"stage": "m3-01"})

    def test_runtime_state_preserves_opaque_metadata(self) -> None:
        """Preserves metadata without semantic validation."""

        metadata = {
            "custom": {"unknown": [1, 2, 3]},
            "timestamp": datetime(2026, 6, 27, tzinfo=timezone.utc),
        }
        runtime_state = RuntimeState(
            observation=self._create_observation(),
            belief=self._create_belief(),
            metadata=metadata,
        )

        data = runtime_state.to_dict()

        self.assertEqual(data["metadata"]["custom"], {"unknown": [1, 2, 3]})
        self.assertEqual(
            data["metadata"]["timestamp"],
            "2026-06-27T00:00:00+00:00",
        )

    def test_runtime_state_round_trip(self) -> None:
        """Serializes and deserializes the runtime state losslessly."""

        runtime_state = RuntimeState(
            observation=self._create_observation(),
            belief=self._create_belief(),
            metadata={"status": "active", "count": 1},
        )

        restored = RuntimeState.from_dict(runtime_state.to_dict())

        self.assertEqual(restored, runtime_state)
