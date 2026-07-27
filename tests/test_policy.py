"""Unit tests for the MIND-Lite Policy model and PolicyEngine."""

from __future__ import annotations

import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from src.core.belief import Belief, BeliefRecord
from src.core.policy import Policy, PolicyEngine


class PolicyTest(unittest.TestCase):
    """Tests for the immutable Policy decision model."""

    def test_policy_creation_preserves_field_values(self) -> None:
        """Creates a policy with its approved decision fields."""

        policy = Policy(
            action="respond",
            parameters={"message": "hello"},
            metadata={"belief_version": 3},
        )

        self.assertEqual(policy.action, "respond")
        self.assertEqual(policy.parameters, {"message": "hello"})
        self.assertEqual(policy.metadata, {"belief_version": 3})

    def test_policy_is_immutable(self) -> None:
        """Prevents assignment to Policy attributes."""

        policy = Policy(action="respond", parameters={}, metadata={})

        with self.assertRaises(FrozenInstanceError):
            policy.action = "other"

    def test_policy_serialization_round_trip_preserves_nested_values(self) -> None:
        """Round-trips nested parameters and metadata without mutation."""

        parameters = {
            "request": {"items": ["one", {"two": 2}]},
        }
        metadata = {
            "context": {"versions": [1, 2], "reason": "prototype"},
        }
        parameters_snapshot = deepcopy(parameters)
        metadata_snapshot = deepcopy(metadata)
        policy = Policy(
            action="respond",
            parameters=parameters,
            metadata=metadata,
        )

        data = policy.to_dict()
        data_snapshot = deepcopy(data)
        restored = Policy.from_dict(data)

        self.assertEqual(restored, policy)
        self.assertEqual(restored.to_dict(), data)
        self.assertEqual(parameters, parameters_snapshot)
        self.assertEqual(metadata, metadata_snapshot)
        self.assertEqual(data, data_snapshot)

    def test_policy_has_no_execution_methods(self) -> None:
        """Exposes no action-execution behavior."""

        policy = Policy(action="respond", parameters={}, metadata={})

        self.assertFalse(hasattr(policy, "execute"))
        self.assertFalse(hasattr(policy, "run"))
        self.assertFalse(hasattr(policy, "invoke"))


class PolicyEngineTest(unittest.TestCase):
    """Tests for deterministic stateless prototype policy generation."""

    def _create_belief(self, record_count: int = 1) -> Belief:
        """Create a belief fixture with the requested number of records."""

        state = {
            f"belief:{index}": BeliefRecord(
                identifier=f"belief:{index}",
                probability=0.5 + index / 10,
                confidence=0.8,
                evidence={"nested": {"index": index}},
            )
            for index in range(record_count)
        }
        return Belief(
            state=state,
            confidence={key: record.confidence for key, record in state.items()},
            version=7,
        )

    def test_generate_returns_policy_for_empty_belief(self) -> None:
        """Returns one deterministic Policy when no records are present."""

        belief = self._create_belief(record_count=0)

        policy = PolicyEngine.generate(belief)

        self.assertIsInstance(policy, Policy)
        self.assertEqual(policy.action, "await_observation")
        self.assertEqual(policy.parameters, {})
        self.assertEqual(
            policy.metadata,
            {"belief_version": 7, "belief_record_count": 0},
        )

    def test_generate_returns_policy_for_one_belief_record(self) -> None:
        """Returns one deterministic Policy for a single belief record."""

        belief = self._create_belief()

        policy = PolicyEngine.generate(belief)

        self.assertIsInstance(policy, Policy)
        self.assertEqual(policy.action, "maintain_belief")
        self.assertEqual(policy.metadata["belief_version"], belief.version)
        self.assertEqual(policy.metadata["belief_record_count"], 1)

    def test_generate_returns_one_policy_for_multiple_belief_records(self) -> None:
        """Returns one Policy even when the Belief contains multiple records."""

        belief = self._create_belief(record_count=3)

        policy = PolicyEngine.generate(belief)

        self.assertIsInstance(policy, Policy)
        self.assertEqual(policy.metadata["belief_record_count"], 3)

    def test_generate_is_deterministic_for_equivalent_beliefs(self) -> None:
        """Produces equivalent Policies from equivalent Belief values."""

        first_belief = self._create_belief(record_count=2)
        second_belief = Belief.from_dict(first_belief.to_dict())

        self.assertEqual(
            PolicyEngine.generate(first_belief),
            PolicyEngine.generate(second_belief),
        )

    def test_generate_is_repeatable_and_engine_is_stateless(self) -> None:
        """Retains no hidden state across repeated generation calls."""

        engine = PolicyEngine()
        belief = self._create_belief(record_count=2)

        first_policy = engine.generate(belief)
        second_policy = engine.generate(belief)

        self.assertEqual(first_policy, second_policy)
        self.assertIsNot(first_policy, second_policy)
        self.assertEqual(len(dir(engine)), len(dir(PolicyEngine)))
        self.assertFalse(hasattr(engine, "belief"))
        self.assertFalse(hasattr(engine, "policy"))
        self.assertFalse(hasattr(engine, "runtime_state"))

    def test_generate_preserves_belief_and_nested_records(self) -> None:
        """Leaves the input Belief and its nested records unchanged."""

        belief = self._create_belief(record_count=2)
        belief_snapshot = deepcopy(belief.to_dict())
        record_snapshot = deepcopy(belief.state["belief:0"].to_dict())

        _ = PolicyEngine.generate(belief)

        self.assertEqual(belief.to_dict(), belief_snapshot)
        self.assertEqual(belief.state["belief:0"].to_dict(), record_snapshot)

    def test_generate_does_not_create_observations_or_execute_actions(self) -> None:
        """Produces a decision without constructing observations or executing."""

        belief = self._create_belief()

        with patch(
            "src.core.observation.Observation",
            side_effect=AssertionError("Observation creation is prohibited"),
        ):
            policy = PolicyEngine.generate(belief)

        self.assertIsInstance(policy, Policy)
        self.assertFalse(hasattr(PolicyEngine, "execute"))
        self.assertFalse(hasattr(PolicyEngine, "run"))
        self.assertFalse(hasattr(PolicyEngine, "invoke"))


if __name__ == "__main__":
    unittest.main()
