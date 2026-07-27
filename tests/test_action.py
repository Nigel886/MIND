"""Unit tests for the MIND-Lite prototype ActionExecutor."""

from __future__ import annotations

import unittest
from copy import deepcopy
from datetime import timezone

import src.core.action as action_module
from src.core.action import ActionExecutor
from src.core.observation import Observation
from src.core.policy import Policy


class ActionExecutorTest(unittest.TestCase):
    """Tests for deterministic, stateless prototype action execution."""

    def _create_policy(
        self,
        action: str = "await_observation",
        parameters: dict[str, object] | None = None,
    ) -> Policy:
        """Create a reusable immutable Policy fixture."""

        return Policy(
            action=action,
            parameters={} if parameters is None else parameters,
            metadata={"belief_version": 3},
        )

    def test_execute_await_observation_returns_structured_observation(self) -> None:
        """Executes await_observation as one completed result observation."""

        policy = self._create_policy(
            parameters={"topic": "external evidence"},
        )

        observation = ActionExecutor.execute(policy)

        self.assertIsInstance(observation, Observation)
        self.assertEqual(observation.source, "action_executor")
        self.assertEqual(
            observation.content,
            {
                "action": "await_observation",
                "status": "completed",
                "parameters": {"topic": "external evidence"},
            },
        )

    def test_execute_maintain_belief_returns_structured_observation(self) -> None:
        """Executes maintain_belief without accessing a Belief object."""

        policy = self._create_policy(
            action="maintain_belief",
            parameters={"reason": "stable"},
        )

        observation = ActionExecutor.execute(policy)

        self.assertIsInstance(observation, Observation)
        self.assertEqual(observation.source, "action_executor")
        self.assertEqual(observation.content["action"], "maintain_belief")
        self.assertEqual(observation.content["status"], "completed")
        self.assertEqual(observation.content["parameters"], {"reason": "stable"})

    def test_execute_preserves_policy_and_nested_parameters(self) -> None:
        """Preserves unusual nested parameter data without rewriting it."""

        parameters = {
            "nested": {"items": [None, {"unknown": "preserved"}]},
        }
        policy = self._create_policy(parameters=parameters)
        policy_snapshot = deepcopy(policy.to_dict())
        parameters_snapshot = deepcopy(parameters)

        observation = ActionExecutor.execute(policy)

        self.assertEqual(policy.to_dict(), policy_snapshot)
        self.assertEqual(parameters, parameters_snapshot)
        self.assertEqual(observation.content["parameters"], parameters_snapshot)

    def test_execute_repeated_calls_are_stateless_and_create_distinct_observations(
        self,
    ) -> None:
        """Creates fresh observations without retaining state across calls."""

        executor = ActionExecutor()
        policy = self._create_policy()
        policy_snapshot = deepcopy(policy.to_dict())

        first = executor.execute(policy)
        second = executor.execute(policy)

        self.assertIsNot(first, second)
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.content, second.content)
        self.assertEqual(policy.to_dict(), policy_snapshot)
        self.assertEqual(len(dir(executor)), len(dir(ActionExecutor)))
        self.assertFalse(hasattr(executor, "policy"))
        self.assertFalse(hasattr(executor, "belief"))
        self.assertFalse(hasattr(executor, "runtime_state"))
        self.assertIs(first.timestamp.tzinfo, timezone.utc)
        self.assertIs(second.timestamp.tzinfo, timezone.utc)

    def test_execute_rejects_unsupported_action(self) -> None:
        """Fails explicitly instead of returning a fallback observation."""

        policy = self._create_policy(action="unsupported_action")

        with self.assertRaises(ValueError):
            ActionExecutor.execute(policy)

    def test_action_executor_exposes_no_generation_or_runtime_behavior(self) -> None:
        """Exposes execution only and introduces no other runtime abstraction."""

        self.assertTrue(hasattr(ActionExecutor, "execute"))
        self.assertFalse(hasattr(ActionExecutor, "generate"))
        self.assertFalse(hasattr(ActionExecutor, "infer"))
        self.assertFalse(hasattr(ActionExecutor, "run"))
        self.assertFalse(hasattr(ActionExecutor, "step"))
        self.assertFalse(hasattr(ActionExecutor, "initialize"))
        self.assertFalse(hasattr(ActionExecutor, "update"))
        self.assertFalse(hasattr(action_module, "Belief"))
        self.assertFalse(hasattr(action_module, "Tool"))
        self.assertFalse(hasattr(action_module, "ActionResult"))


if __name__ == "__main__":
    unittest.main()
