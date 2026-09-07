"""Focused internal tests for the M15 cognitive execution loop controller."""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from src.core.cognitive_execution import CognitiveExecutionLoopController
from src.core.goal_policy import GoalAwarePolicyEngine
from src.core.observation import Observation
from src.core.runtime import RuntimeController
from src.core.task import Goal, Task


class CognitiveExecutionLoopControllerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.task = Task(
            Goal("add values", ("return the expected answer",)),
            {"operation": "add", "operands": [2, 3], "expected_answer": 5},
        )
        self.initial_state = RuntimeController.initialize()

    def test_observation_transition_uses_runtime_controller_and_preserves_input(self) -> None:
        observation = Observation(source="agent_environment", content={"status": "completed", "output": 4})
        before = self.initial_state.to_dict()
        with patch.object(
            RuntimeController,
            "apply_inference",
            wraps=RuntimeController.apply_inference,
        ) as apply_inference:
            transition = CognitiveExecutionLoopController.advance(
                self.task,
                self.initial_state,
                observation,
                observation.content,
            )

        apply_inference.assert_called_once_with(self.initial_state, observation)
        self.assertEqual(self.initial_state.to_dict(), before)
        self.assertIsNot(transition.runtime_state, self.initial_state)
        self.assertEqual(transition.runtime_state.observation, observation)
        self.assertEqual(transition.runtime_state.belief.version, self.initial_state.belief.version + 1)
        self.assertIsNotNone(transition.policy)
        self.assertEqual(transition.policy.action, "call_tool")

    def test_completed_and_failed_feedback_prevent_policy_generation(self) -> None:
        complete = Observation(source="agent_environment", content={"status": "completed", "output": 5})
        failed = Observation(source="agent_environment", content={"status": "failed", "failure_category": "tool_failure"})
        with patch.object(
            GoalAwarePolicyEngine,
            "generate",
            wraps=GoalAwarePolicyEngine.generate,
        ) as generate:
            completed = CognitiveExecutionLoopController.advance(self.task, self.initial_state, complete, complete.content)
            failure = CognitiveExecutionLoopController.advance(self.task, self.initial_state, failed, failed.content)

        self.assertEqual(completed.completed_answer, 5)
        self.assertIsNone(completed.policy)
        self.assertEqual(failure.failure_category, "tool_failure")
        self.assertIsNone(failure.policy)
        generate.assert_not_called()

    def test_nonterminal_feedback_permits_deterministic_repeated_policy(self) -> None:
        observation = Observation(source="agent_environment", content={"status": "completed", "output": 4})
        first = CognitiveExecutionLoopController.advance(self.task, self.initial_state)
        second = CognitiveExecutionLoopController.advance(
            self.task,
            first.runtime_state,
            observation,
            observation.content,
        )
        self.assertEqual(first.policy.to_dict(), second.policy.to_dict())
        self.assertEqual(second.policy.action, "call_tool")

    def test_controller_has_no_tool_provider_or_session_public_api_dependency(self) -> None:
        source = inspect.getsource(CognitiveExecutionLoopController)
        module_source = inspect.getsource(__import__("src.core.cognitive_execution", fromlist=["*"]))
        self.assertNotIn("ToolRegistry", source)
        self.assertNotIn("ActionExecutor", source)
        self.assertNotIn("LLMProvider", module_source)
        self.assertNotIn("TaskInterpreter", module_source)
        self.assertFalse(hasattr(__import__("src.core", fromlist=["*"]), "CognitiveExecutionLoopController"))

    def test_equivalent_transitions_are_deterministic(self) -> None:
        observation = Observation(source="agent_environment", content={"status": "completed", "output": 4})
        one = CognitiveExecutionLoopController.advance(self.task, self.initial_state, observation, observation.content)
        two = CognitiveExecutionLoopController.advance(self.task, self.initial_state, observation, observation.content)
        self.assertEqual(one.policy.to_dict(), two.policy.to_dict())
        self.assertEqual(one.runtime_state.belief.to_dict(), two.runtime_state.belief.to_dict())


if __name__ == "__main__":
    unittest.main()
