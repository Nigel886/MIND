"""Tests for immutable M14 evaluation execution contracts."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from src.core.task import Goal, Task
from src.evaluation.contracts import (
    EvaluationAction,
    EvaluationActionType,
    EvaluationCase,
    EvaluationFeedback,
    EvaluationFeedbackType,
)
from src.evaluation.execution import (
    AgentStepInput,
    AgentStepResult,
    EnvironmentInteraction,
    EvaluationBudget,
    EvaluationBudgetState,
    EvaluationTimeoutPolicy,
)


class EvaluationExecutionContractsTest(unittest.TestCase):
    """Validate evaluation-side execution values without executing an Agent."""

    def setUp(self) -> None:
        task = Task(Goal("return ready", ("answer is ready",)), {"value": "ready"})
        self.case = EvaluationCase("m14.execution.001", task, {"environment": "local"})
        self.feedback = EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT, {"value": "ready"})
        self.budget = EvaluationBudget(3, 1)

    def test_budget_and_state_are_immutable_and_serializable(self) -> None:
        state = EvaluationBudgetState(self.budget, steps_used=1, tool_calls_used=0)
        self.assertEqual(state.remaining_steps, 2)
        self.assertEqual(state.remaining_tool_calls, 1)
        self.assertEqual(EvaluationBudget.from_dict(self.budget.to_dict()), self.budget)
        self.assertEqual(EvaluationBudgetState.from_dict(state.to_dict()), state)
        with self.assertRaises(FrozenInstanceError):
            state.steps_used = 2

    def test_step_input_and_result_round_trip_deterministically(self) -> None:
        step_input = AgentStepInput(self.case, self.feedback, EvaluationBudgetState(self.budget))
        result = AgentStepResult(EvaluationAction(EvaluationActionType.ANSWER, {"answer": "ready"}), True)
        self.assertEqual(AgentStepInput.from_dict(step_input.to_dict()), step_input)
        self.assertEqual(AgentStepResult.from_dict(result.to_dict()), result)
        self.assertEqual(step_input.to_dict(), step_input.to_dict())

    def test_interaction_round_trip_and_alias_isolation(self) -> None:
        parameters = {"operation": "multiply", "operands": [17, 23]}
        interaction = EnvironmentInteraction(
            EvaluationAction(EvaluationActionType.TOOL_CALL, {"tool_name": "calculator", "parameters": parameters}),
            EvaluationFeedback(EvaluationFeedbackType.TOOL_RESPONSE, {"output": 391}),
        )
        parameters["operands"].append(99)
        self.assertEqual(interaction.to_dict()["action"]["payload"]["parameters"]["operands"], [17, 23])
        self.assertEqual(EnvironmentInteraction.from_dict(interaction.to_dict()), interaction)
        with self.assertRaises(FrozenInstanceError):
            interaction.feedback = self.feedback

    def test_invalid_values_are_rejected(self) -> None:
        with self.assertRaises(TypeError):
            EvaluationBudget(True, 1)
        with self.assertRaises(ValueError):
            EvaluationBudget(-1, 1)
        with self.assertRaises(TypeError):
            EvaluationBudget(1, 1, "hard_stop")
        with self.assertRaises(ValueError):
            EvaluationBudget.from_dict({"max_steps": 1, "max_tool_calls": 1, "timeout_policy": "later"})
        with self.assertRaises(ValueError):
            EvaluationBudgetState(self.budget, steps_used=4)
        with self.assertRaises(TypeError):
            AgentStepInput(self.case, self.feedback, self.budget)
        with self.assertRaises(TypeError):
            AgentStepResult(EvaluationAction(EvaluationActionType.FAIL), 1)
        with self.assertRaises(ValueError):
            AgentStepResult(EvaluationAction(EvaluationActionType.ANSWER), False)
        with self.assertRaises(ValueError):
            AgentStepResult(
                EvaluationAction(
                    EvaluationActionType.TOOL_CALL,
                    {"tool_name": "calculator", "parameters": {}},
                ),
                True,
            )
        with self.assertRaises(TypeError):
            EnvironmentInteraction(EvaluationAction(EvaluationActionType.FAIL), self.case)

    def test_public_timeout_policy_is_deterministic(self) -> None:
        budget = EvaluationBudget(0, 0, EvaluationTimeoutPolicy.HARD_STOP)
        self.assertEqual(budget.to_dict(), {"max_steps": 0, "max_tool_calls": 0, "timeout_policy": "hard_stop"})


if __name__ == "__main__":
    unittest.main()
