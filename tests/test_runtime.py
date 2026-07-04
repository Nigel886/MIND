"""Unit tests for the runtime state module and runtime controller."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from src.core.belief import Belief, BeliefRecord
from src.core.observation import Observation
from src.core.runtime import RuntimeState, RuntimeController


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


class RuntimeControllerTest(unittest.TestCase):
    """Tests for the RuntimeController component."""

    def test_initialize_creates_default_runtime_state(self) -> None:
        """Creates a default runtime state when no arguments are provided."""

        controller = RuntimeController()
        runtime_state = controller.initialize()

        self.assertIsInstance(runtime_state, RuntimeState)
        self.assertIsInstance(runtime_state.observation, Observation)
        self.assertIsInstance(runtime_state.belief, Belief)
        self.assertEqual(runtime_state.metadata, {})

    def test_initialize_uses_provided_observation(self) -> None:
        """Uses the provided observation when given."""

        controller = RuntimeController()
        observation = Observation(source="user", content="test")
        runtime_state = controller.initialize(observation=observation)

        self.assertEqual(runtime_state.observation, observation)

    def test_initialize_uses_provided_belief(self) -> None:
        """Uses the provided belief when given."""

        controller = RuntimeController()
        belief = Belief(state={}, confidence={}, version=1)
        runtime_state = controller.initialize(belief=belief)

        self.assertEqual(runtime_state.belief, belief)

    def test_initialize_uses_provided_metadata(self) -> None:
        """Uses the provided metadata when given."""

        controller = RuntimeController()
        metadata = {"test": "value"}
        runtime_state = controller.initialize(metadata=metadata)

        self.assertEqual(runtime_state.metadata, metadata)

    def test_initialize_creates_new_instance_each_time(self) -> None:
        """Returns a new RuntimeState instance on each call."""

        controller = RuntimeController()
        first = controller.initialize()
        second = controller.initialize()

        self.assertIsNot(first, second)

    def test_runtime_controller_is_stateless(self) -> None:
        """Verifies RuntimeController stores no internal state."""

        controller = RuntimeController()
        controller.initialize()

        self.assertFalse(hasattr(controller, "runtime_state"))
        self.assertFalse(hasattr(controller, "observation"))
        self.assertFalse(hasattr(controller, "belief"))

    def test_runtime_controller_has_minimal_public_api(self) -> None:
        """Exposes only initialize() and update() and no lifecycle methods."""

        controller = RuntimeController()

        self.assertTrue(hasattr(controller, "initialize"))
        self.assertTrue(hasattr(controller, "update"))
        self.assertFalse(hasattr(controller, "step"))
        self.assertFalse(hasattr(controller, "run"))
        self.assertFalse(hasattr(controller, "stop"))
        self.assertFalse(hasattr(controller, "reset"))

    def test_update_preserves_original_state(self) -> None:
        """Verifies original RuntimeState remains unchanged after update."""

        controller = RuntimeController()
        original = controller.initialize()

        new_observation = Observation(source="test", content="new")
        updated = controller.update(original, observation=new_observation)

        self.assertIsNot(original, updated)
        self.assertNotEqual(original.observation, updated.observation)
        self.assertEqual(original.belief, updated.belief)
        self.assertEqual(original.metadata, updated.metadata)

    def test_update_replaces_only_specified_components(self) -> None:
        """Updates only the components explicitly provided by the caller."""

        controller = RuntimeController()
        original = controller.initialize(
            metadata={"phase": "initial"},
        )

        new_belief = Belief(state={}, confidence={}, version=999)
        updated = controller.update(original, belief=new_belief)

        self.assertEqual(updated.observation, original.observation)
        self.assertEqual(updated.belief, new_belief)
        self.assertEqual(updated.metadata, original.metadata)
        self.assertIsNot(original, updated)

    def test_update_replaces_multiple_components(self) -> None:
        """Supports updating multiple components in a single call."""

        controller = RuntimeController()
        original = controller.initialize()

        new_observation = Observation(source="test", content="multi")
        new_belief = Belief(state={}, confidence={}, version=123)
        new_metadata = {"phase": "updated"}

        updated = controller.update(
            original,
            observation=new_observation,
            belief=new_belief,
            metadata=new_metadata,
        )

        self.assertEqual(updated.observation, new_observation)
        self.assertEqual(updated.belief, new_belief)
        self.assertEqual(updated.metadata, new_metadata)
        self.assertIsNot(original, updated)

    def test_update_returns_new_instance(self) -> None:
        """Always returns a new RuntimeState instance even with no changes."""

        controller = RuntimeController()
        original = controller.initialize()

        updated = controller.update(original)

        self.assertIsNot(original, updated)
        self.assertEqual(original.observation, updated.observation)
        self.assertEqual(original.belief, updated.belief)
        self.assertEqual(original.metadata, updated.metadata)

    def test_update_preserves_metadata_immutability(self) -> None:
        """Ensures metadata dictionary is copied when preserved."""

        controller = RuntimeController()
        original = controller.initialize(metadata={"key": "value"})

        updated = controller.update(original)

        self.assertEqual(original.metadata, updated.metadata)
        self.assertIsNot(original.metadata, updated.metadata)


class RuntimeCoreIntegrationTest(unittest.TestCase):
    """Integration tests for the complete Runtime Core."""

    def test_complete_runtime_workflow(self) -> None:
        """Verifies a complete Runtime Core workflow from initialization through multiple updates."""

        controller = RuntimeController()

        # Step 1: Initialize the runtime
        initial_state = controller.initialize()
        self.assertIsInstance(initial_state, RuntimeState)
        self.assertIsInstance(initial_state.observation, Observation)
        self.assertIsInstance(initial_state.belief, Belief)

        # Step 2: Update observation
        obs1 = Observation(source="user", content="first input")
        state1 = controller.update(initial_state, observation=obs1)
        self.assertIsNot(initial_state, state1)
        self.assertEqual(state1.observation, obs1)
        self.assertEqual(state1.belief, initial_state.belief)
        self.assertEqual(state1.metadata, initial_state.metadata)

        # Verify initial state is unmodified
        self.assertIsNot(initial_state.observation, obs1)

        # Step 3: Update belief
        belief1 = Belief(
            state={},
            confidence={},
            version=1,
        )
        state2 = controller.update(state1, belief=belief1)
        self.assertIsNot(state1, state2)
        self.assertEqual(state2.observation, obs1)
        self.assertEqual(state2.belief, belief1)

        # Step 4: Update metadata
        metadata1 = {"phase": "running", "iteration": 1}
        state3 = controller.update(state2, metadata=metadata1)
        self.assertIsNot(state2, state3)
        self.assertEqual(state3.metadata, metadata1)

        # Step 5: Update all components together
        obs2 = Observation(source="system", content="response")
        belief2 = Belief(
            state={},
            confidence={},
            version=2,
        )
        metadata2 = {"phase": "complete", "iteration": 2}

        state4 = controller.update(
            state3,
            observation=obs2,
            belief=belief2,
            metadata=metadata2,
        )
        self.assertIsNot(state3, state4)
        self.assertEqual(state4.observation, obs2)
        self.assertEqual(state4.belief, belief2)
        self.assertEqual(state4.metadata, metadata2)

    def test_runtime_state_immutability_through_workflow(self) -> None:
        """Ensures RuntimeState remains immutable throughout the entire workflow."""

        from dataclasses import FrozenInstanceError

        controller = RuntimeController()
        state = controller.initialize()

        # Attempt to modify the state directly (should fail)
        with self.assertRaises(FrozenInstanceError):
            state.metadata = {"modified": True}

        with self.assertRaises(FrozenInstanceError):
            state.observation = Observation(source="hacked", content="bad")

        with self.assertRaises(FrozenInstanceError):
            state.belief = Belief(state={}, confidence={}, version=999)

        # Update through controller creates new instance
        new_state = controller.update(
            state,
            metadata={"updated": True},
        )

        self.assertIsNot(state, new_state)
        self.assertEqual(state.metadata, {})  # Original unchanged
        self.assertEqual(new_state.metadata, {"updated": True})  # New has change

    def test_runtime_controller_statelessness(self) -> None:
        """Ensures RuntimeController never stores internal state."""

        controller = RuntimeController()

        # Check that no instance attributes are stored
        self.assertEqual(len(dir(controller)), len(dir(RuntimeController)))
        self.assertFalse(hasattr(controller, "runtime_state"))
        self.assertFalse(hasattr(controller, "observation"))
        self.assertFalse(hasattr(controller, "belief"))
        self.assertFalse(hasattr(controller, "metadata"))
        self.assertFalse(hasattr(controller, "state"))
        self.assertFalse(hasattr(controller, "current_state"))

        # Multiple operations don't leave any state behind
        state1 = controller.initialize()
        state2 = controller.update(state1)
        state3 = controller.update(state2)

        # No state stored in controller
        self.assertFalse(hasattr(controller, "state1"))
        self.assertFalse(hasattr(controller, "state2"))
        self.assertFalse(hasattr(controller, "state3"))

    def test_runtime_round_trip_serialization(self) -> None:
        """Verifies complete RuntimeState round-trip serialization."""

        controller = RuntimeController()
        original = controller.initialize(
            metadata={"test": "value", "number": 42},
        )

        # Serialize
        data = original.to_dict()
        self.assertIsInstance(data, dict)
        self.assertIn("observation", data)
        self.assertIn("belief", data)
        self.assertIn("metadata", data)

        # Deserialize
        restored = RuntimeState.from_dict(data)

        # Verify they are equivalent but different instances
        self.assertEqual(restored.observation, original.observation)
        self.assertEqual(restored.belief, original.belief)
        self.assertEqual(restored.metadata, original.metadata)
        self.assertIsNot(restored, original)
