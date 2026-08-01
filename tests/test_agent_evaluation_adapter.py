"""Tests for the evaluation-only MIND Agent step adapter."""

from __future__ import annotations

import inspect
import unittest

from src.core.agent import GoalDirectedAgent
from src.core.observation import Observation
from src.core.task import Goal, Task
from src.core.tool import ToolRegistry
from src.evaluation.agent_adapter import (
    MINDGoalDirectedEvaluationAdapter,
    _MINDGoalDirectedEvaluationSession,
    _feedback_observation,
)
from src.evaluation.contracts import (
    EvaluationActionType,
    EvaluationCase,
    EvaluationFeedback,
    EvaluationFeedbackType,
)
from src.evaluation.execution import AgentStepInput, EvaluationBudget, EvaluationBudgetState
from src.tools.calculator import CalculatorTool


class AgentEvaluationAdapterTest(unittest.TestCase):
    """Verify public action extraction while keeping MIND state private."""

    def _step_input(self, task: Task, feedback: EvaluationFeedback, identifier: str = "m14.adapter.001") -> AgentStepInput:
        return AgentStepInput(
            EvaluationCase(identifier, task),
            feedback,
            EvaluationBudgetState(EvaluationBudget(3, 1)),
        )

    def test_direct_answer_action_matches_existing_agent_behavior(self) -> None:
        task = Task(Goal("return ready", ("correct",)), {"value": "ready", "expected_answer": "ready"})
        adapter = MINDGoalDirectedEvaluationAdapter()
        result = adapter.step(self._step_input(task, EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))

        registry = ToolRegistry()
        existing = GoalDirectedAgent(registry).run(task, 1)
        self.assertEqual(result.action.action_type, EvaluationActionType.ANSWER)
        self.assertEqual(result.action.to_dict()["payload"], {"answer": existing.answer})
        self.assertTrue(result.request_termination)
        self.assertNotIn("RuntimeState", repr(result))
        self.assertFalse(hasattr(result, "runtime_state"))

    def test_calculator_action_then_feedback_maps_to_private_observation_and_answer(self) -> None:
        task = Task(
            Goal("multiply", ("correct",)),
            {"operation": "multiply", "operands": [17, 23], "expected_answer": 391},
        )
        adapter = MINDGoalDirectedEvaluationAdapter()
        initial = self._step_input(task, EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT))
        action = adapter.step(initial)
        self.assertEqual(action.action.action_type, EvaluationActionType.TOOL_CALL)
        self.assertFalse(action.request_termination)
        self.assertEqual(action.action.to_dict()["payload"], {"tool_name": "calculator", "parameters": {"operation": "multiply", "operands": [17, 23]}})

        feedback = EvaluationFeedback(
            EvaluationFeedbackType.TOOL_RESPONSE,
            {"response": {"output": 391}},
        )
        observation = _feedback_observation(feedback)
        self.assertIsInstance(observation, Observation)
        self.assertEqual(observation.source, "evaluation_environment")
        self.assertEqual(observation.content, feedback.to_dict())
        terminal = adapter.step(self._step_input(task, feedback))
        self.assertEqual(terminal.action.action_type, EvaluationActionType.ANSWER)
        self.assertEqual(terminal.action.to_dict()["payload"], {"answer": 391})
        self.assertTrue(terminal.request_termination)

        registry = ToolRegistry(); registry.register(CalculatorTool())
        self.assertEqual(GoalDirectedAgent(registry).run(task, 1).answer, 391)

    def test_failure_and_case_mismatch_feedback_map_without_fallback(self) -> None:
        task = Task(Goal("multiply", ("correct",)), {"operation": "multiply", "operands": [2, 3], "expected_answer": 6})
        adapter = MINDGoalDirectedEvaluationAdapter()
        adapter.step(self._step_input(task, EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
        failure = adapter.step(self._step_input(task, EvaluationFeedback(EvaluationFeedbackType.TOOL_FAILURE)))
        self.assertEqual(failure.action.action_type, EvaluationActionType.FAIL)
        self.assertEqual(failure.action.to_dict()["payload"], {"reason": "tool_failure"})

        after_terminal = adapter.step(self._step_input(task, EvaluationFeedback(EvaluationFeedbackType.TOOL_RESPONSE, {"response": {"output": 6}})))
        self.assertEqual(after_terminal.action.action_type, EvaluationActionType.INVALID)

        other_adapter = MINDGoalDirectedEvaluationAdapter()
        other_adapter.step(self._step_input(task, EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
        other = other_adapter.step(self._step_input(task, EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT), "m14.adapter.other"))
        self.assertEqual(other.action.action_type, EvaluationActionType.INVALID)

    def test_private_session_lifecycle_and_no_tool_registry_dependency(self) -> None:
        task = Task(Goal("return ready", ("correct",)), {"value": "ready", "expected_answer": "ready"})
        session = _MINDGoalDirectedEvaluationSession.start(task, None)
        result = session.next_decision()
        self.assertEqual(result.action.action_type, EvaluationActionType.ANSWER)
        with self.assertRaises(RuntimeError):
            session.accept_observation(_feedback_observation(EvaluationFeedback(EvaluationFeedbackType.TOOL_RESPONSE, {})))
        source = inspect.getsource(MINDGoalDirectedEvaluationAdapter)
        self.assertNotIn("ToolRegistry", source)

    def test_invalid_lifecycle_inputs_are_explicit(self) -> None:
        task = Task(Goal("return ready", ("correct",)), {"value": "ready", "expected_answer": "ready"})
        adapter = MINDGoalDirectedEvaluationAdapter()
        no_initial = adapter.step(self._step_input(task, EvaluationFeedback(EvaluationFeedbackType.TOOL_RESPONSE, {"response": {"output": "ready"}})))
        self.assertEqual(no_initial.action.action_type, EvaluationActionType.INVALID)
        with self.assertRaises(TypeError):
            adapter.step(task)


if __name__ == "__main__":
    unittest.main()
