"""Integration tests for the MIND-Lite Decision Layer."""

from __future__ import annotations

import unittest
from copy import deepcopy
from datetime import timezone

import src.core.action as action_module
from src.core.action import ActionExecutor
from src.core.belief import Belief, BeliefRecord
from src.core.observation import Observation
from src.core.policy import Policy, PolicyEngine


class DecisionLayerIntegrationTest(unittest.TestCase):
    """Validates the Belief to Policy to Observation component flow."""

    def _empty_belief(self) -> Belief:
        """Create a deterministic empty Belief fixture."""

        return Belief(state={}, confidence={}, version=2)

    def _non_empty_belief(self) -> Belief:
        """Create a deterministic Belief fixture with nested evidence."""

        record = BeliefRecord(
            identifier="decision:ready",
            probability=0.8,
            confidence=0.9,
            evidence={"nested": {"source": "fixture"}},
        )
        return Belief(
            state={"decision:ready": record},
            confidence={"decision:ready": 0.9},
            version=3,
        )

    def test_empty_belief_flow_returns_await_observation_result(self) -> None:
        """Validates the complete empty-Belief Decision Layer flow."""

        belief = self._empty_belief()

        policy = PolicyEngine.generate(belief)
        observation = ActionExecutor.execute(policy)

        self.assertIsInstance(policy, Policy)
        self.assertEqual(policy.action, "await_observation")
        self.assertIsInstance(observation, Observation)
        self.assertEqual(observation.source, "action_executor")
        self.assertEqual(
            observation.content,
            {
                "action": "await_observation",
                "status": "completed",
                "parameters": policy.parameters,
            },
        )

    def test_non_empty_belief_flow_returns_maintain_belief_result(self) -> None:
        """Validates the complete non-empty-Belief Decision Layer flow."""

        belief = self._non_empty_belief()

        policy = PolicyEngine.generate(belief)
        observation = ActionExecutor.execute(policy)

        self.assertIsInstance(policy, Policy)
        self.assertEqual(policy.action, "maintain_belief")
        self.assertIsInstance(observation, Observation)
        self.assertEqual(observation.source, "action_executor")
        self.assertEqual(observation.content["action"], "maintain_belief")
        self.assertEqual(observation.content["status"], "completed")
        self.assertEqual(observation.content["parameters"], policy.parameters)

    def test_chained_executions_preserve_inputs_and_remain_stateless(self) -> None:
        """Validates preservation, determinism, freshness, and statelessness."""

        first_belief = self._non_empty_belief()
        second_belief = Belief.from_dict(first_belief.to_dict())
        belief_snapshot = deepcopy(first_belief.to_dict())
        record_snapshot = deepcopy(
            first_belief.state["decision:ready"].to_dict(),
        )
        policy_engine = PolicyEngine()
        action_executor = ActionExecutor()

        first_policy = policy_engine.generate(first_belief)
        first_policy_snapshot = deepcopy(first_policy.to_dict())
        first_observation = action_executor.execute(first_policy)
        first_observation_snapshot = deepcopy(first_observation.to_dict())

        second_policy = policy_engine.generate(second_belief)
        second_observation = action_executor.execute(second_policy)

        self.assertEqual(first_policy, second_policy)
        self.assertEqual(first_observation.content, second_observation.content)
        self.assertIsNot(first_observation, second_observation)
        self.assertNotEqual(first_observation.id, second_observation.id)
        self.assertIs(first_observation.timestamp.tzinfo, timezone.utc)
        self.assertIs(second_observation.timestamp.tzinfo, timezone.utc)
        self.assertEqual(first_belief.to_dict(), belief_snapshot)
        self.assertEqual(
            first_belief.state["decision:ready"].to_dict(),
            record_snapshot,
        )
        self.assertEqual(first_policy.to_dict(), first_policy_snapshot)
        self.assertEqual(first_observation.to_dict(), first_observation_snapshot)
        self.assertEqual(len(dir(policy_engine)), len(dir(PolicyEngine)))
        self.assertEqual(len(dir(action_executor)), len(dir(ActionExecutor)))
        self.assertFalse(hasattr(policy_engine, "belief"))
        self.assertFalse(hasattr(action_executor, "policy"))
        self.assertFalse(hasattr(action_executor, "runtime_state"))

    def test_unsupported_action_preserves_policy_and_allows_later_execution(
        self,
    ) -> None:
        """Validates error isolation and successful recovery with a valid Policy."""

        executor = ActionExecutor()
        unsupported_policy = Policy(
            action="unsupported_action",
            parameters={"nested": {"value": 1}},
            metadata={"origin": "test"},
        )
        unsupported_snapshot = deepcopy(unsupported_policy.to_dict())

        with self.assertRaises(ValueError):
            executor.execute(unsupported_policy)

        valid_observation = executor.execute(
            Policy(
                action="await_observation",
                parameters={},
                metadata={},
            ),
        )

        self.assertEqual(unsupported_policy.to_dict(), unsupported_snapshot)
        self.assertIsInstance(valid_observation, Observation)
        self.assertFalse(hasattr(executor, "policy"))
        self.assertFalse(hasattr(executor, "belief"))

    def test_action_execution_preserves_nested_policy_data(self) -> None:
        """Preserves nested Policy parameters and metadata during execution."""

        policy = Policy(
            action="maintain_belief",
            parameters={"nested": {"items": [1, {"two": 2}]}},
            metadata={"nested": {"reason": "validation"}},
        )
        policy_snapshot = deepcopy(policy.to_dict())

        observation = ActionExecutor.execute(policy)

        self.assertEqual(policy.to_dict(), policy_snapshot)
        self.assertEqual(
            observation.content["parameters"],
            policy_snapshot["parameters"],
        )

    def test_decision_layer_preserves_responsibility_boundaries(self) -> None:
        """Verifies observable separation between decision and execution APIs."""

        policy = PolicyEngine.generate(self._empty_belief())

        self.assertIsInstance(policy, Policy)
        self.assertFalse(isinstance(policy, Observation))
        self.assertFalse(hasattr(policy, "execute"))
        self.assertFalse(hasattr(policy, "run"))
        self.assertFalse(hasattr(policy, "invoke"))
        self.assertFalse(hasattr(ActionExecutor, "generate"))
        self.assertFalse(hasattr(ActionExecutor, "infer"))
        self.assertFalse(hasattr(ActionExecutor, "initialize"))
        self.assertFalse(hasattr(ActionExecutor, "update"))
        self.assertFalse(hasattr(action_module, "Belief"))
        self.assertFalse(hasattr(action_module, "Tool"))
        self.assertFalse(hasattr(action_module, "ActionResult"))


if __name__ == "__main__":
    unittest.main()
