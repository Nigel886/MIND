"""Unit tests for the prototype inference engine."""

from __future__ import annotations

import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError

from src.core.belief import Belief, BeliefRecord
from src.core.inference import InferenceEngine
from src.core.observation import Observation


class InferenceEngineTest(unittest.TestCase):
    """Tests for the stateless prototype inference engine."""

    def _create_observation(self) -> Observation:
        """Create a reusable observation fixture.

        Returns:
            An immutable observation instance.
        """

        return Observation(
            source="user",
            content={"message": "hello inference"},
        )

    def _create_belief(self) -> Belief:
        """Create a reusable belief fixture.

        Returns:
            An immutable belief instance.
        """

        record = BeliefRecord(
            identifier="existing",
            probability=0.75,
            confidence=0.85,
            evidence={"source": "memory"},
        )
        return Belief(
            state={"existing": record},
            confidence={"existing": 0.85},
            version=2,
        )

    def test_infer_returns_new_immutable_belief(self) -> None:
        """Returns a new immutable belief instance."""

        observation = self._create_observation()
        belief = self._create_belief()

        updated_belief = InferenceEngine.infer(observation, belief)

        self.assertIsInstance(updated_belief, Belief)
        self.assertIsNot(updated_belief, belief)
        self.assertEqual(updated_belief.version, 3)

        with self.assertRaises(FrozenInstanceError):
            updated_belief.version = 99

    def test_infer_does_not_mutate_previous_belief(self) -> None:
        """Preserves the previous belief object and its value state."""

        observation = self._create_observation()
        belief = self._create_belief()
        belief_snapshot = deepcopy(belief.to_dict())

        updated_belief = InferenceEngine.infer(observation, belief)

        self.assertEqual(belief.to_dict(), belief_snapshot)
        self.assertEqual(belief.version, 2)
        self.assertEqual(len(belief.state), 1)
        self.assertGreater(len(updated_belief.state), len(belief.state))

    def test_infer_does_not_mutate_observation(self) -> None:
        """Preserves the observation object and its value state."""

        observation = self._create_observation()
        belief = self._create_belief()
        observation_snapshot = deepcopy(observation.to_dict())

        _ = InferenceEngine.infer(observation, belief)

        self.assertEqual(observation.to_dict(), observation_snapshot)
        self.assertEqual(observation.source, "user")
        self.assertEqual(
            observation.content,
            {"message": "hello inference"},
        )

    def test_infer_exhibits_deterministic_prototype_behaviour(self) -> None:
        """Produces equivalent belief values for identical inputs."""

        observation = self._create_observation()
        belief = self._create_belief()

        first = InferenceEngine.infer(observation, belief)
        second = InferenceEngine.infer(observation, belief)

        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertIsNot(first, second)

    def test_infer_adds_observation_derived_belief_record(self) -> None:
        """Adds a deterministic belief record derived from the observation."""

        observation = self._create_observation()
        belief = self._create_belief()

        updated_belief = InferenceEngine.infer(observation, belief)

        identifier = "observation:user"
        self.assertIn(identifier, updated_belief.state)
        self.assertEqual(updated_belief.confidence[identifier], 1.0)
        self.assertEqual(
            updated_belief.state[identifier].evidence,
            observation.to_dict(),
        )

    def test_inference_engine_has_only_frozen_public_api(self) -> None:
        """Exposes only infer() as the public operation."""

        self.assertTrue(hasattr(InferenceEngine, "infer"))
        self.assertFalse(hasattr(InferenceEngine, "initialize"))
        self.assertFalse(hasattr(InferenceEngine, "update"))
        self.assertFalse(hasattr(InferenceEngine, "step"))
        self.assertFalse(hasattr(InferenceEngine, "run"))
        self.assertFalse(hasattr(InferenceEngine, "reset"))

    def test_inference_engine_remains_stateless(self) -> None:
        """Stores no internal state before or after inference."""

        engine = InferenceEngine()
        observation = self._create_observation()
        belief = self._create_belief()

        _ = engine.infer(observation, belief)

        self.assertFalse(hasattr(engine, "observation"))
        self.assertFalse(hasattr(engine, "belief"))
        self.assertFalse(hasattr(engine, "runtime_state"))
        self.assertFalse(hasattr(engine, "state"))
