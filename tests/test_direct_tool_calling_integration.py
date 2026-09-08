"""Integration tests using existing evaluator-owned environment and judge contracts."""

from __future__ import annotations

import unittest

from src.core.task import Goal, Task
from src.evaluation.cohort_a_runner import CohortACompletionJudge
from src.evaluation.contracts import (
    EvaluationActionType,
    EvaluationCase,
    EvaluationFeedbackType,
)
from src.evaluation.direct_tool_calling import (
    DirectActionProviderResponse,
    DirectToolCallingEvaluationAgent,
    FakeDirectActionProvider,
    assess_cohort_a_eligibility,
)
from src.evaluation.environment import DeterministicEvaluationEnvironment, EnvironmentConfig
from src.evaluation.execution import (
    AgentStepInput,
    EnvironmentInteraction,
    EvaluationBudget,
    EvaluationBudgetState,
)


def _eligible_task() -> Task:
    return Task(
        Goal("multiply", ("return result",)),
        {"operation": "multiply", "operands": [17, 23]},
        metadata={"m16_cohort_a": {
            "task_family": "controlled_single_tool", "tool_call_limit": 1,
            "requires_planning": False, "requires_multi_tool": False,
            "requires_dependent_multistep": False, "requires_recovery": False,
        }},
    )


class DirectToolCallingIntegrationTests(unittest.TestCase):
    def test_environment_executes_tool_and_judge_owns_success(self) -> None:
        case = EvaluationCase("m16.tool.001", _eligible_task())
        config = EnvironmentConfig(
            environment_id="m16-calculator-v1",
            tool_responses={"calculator": {"output": 391}},
            completion_context={"expected_answer": 391},
        )
        environment = DeterministicEvaluationEnvironment(config)
        agent = DirectToolCallingEvaluationAgent(FakeDirectActionProvider({
            EvaluationFeedbackType.INITIAL_INPUT: DirectActionProviderResponse(
                EvaluationActionType.TOOL_CALL,
                {"tool_name": "calculator", "parameters": {"operation": "multiply", "operands": [17, 23]}},
            ),
            EvaluationFeedbackType.TOOL_RESPONSE: DirectActionProviderResponse(
                EvaluationActionType.ANSWER, {"answer": 391}
            ),
        }), {"calculator": {"type": "object"}}, "fake-v1")
        budget = EvaluationBudget(2, 1)
        initial = environment.reset(case)
        first = agent.step(AgentStepInput(case, initial, EvaluationBudgetState(budget)))
        feedback = environment.apply(first.action, EvaluationBudgetState(budget, steps_used=1))
        second = agent.step(AgentStepInput(case, feedback, EvaluationBudgetState(budget, steps_used=1, tool_calls_used=1)))

        self.assertEqual(first.action.action_type, EvaluationActionType.TOOL_CALL)
        self.assertEqual(feedback.feedback_type, EvaluationFeedbackType.TOOL_RESPONSE)
        self.assertEqual(second.action.action_type, EvaluationActionType.ANSWER)
        outcome = CohortACompletionJudge("m16-rule-v1").evaluate(
            case,
            (EnvironmentInteraction(first.action, feedback),),
            EvaluationBudgetState(budget, steps_used=2, tool_calls_used=1),
            second.action,
            config,
        )
        self.assertEqual(outcome.outcome_type.value, "success")
        self.assertTrue(assess_cohort_a_eligibility(case).eligible)

    def test_budget_remains_evaluator_owned(self) -> None:
        case = EvaluationCase("m16.direct.001", _eligible_task())
        agent = DirectToolCallingEvaluationAgent(FakeDirectActionProvider({
            EvaluationFeedbackType.INITIAL_INPUT: DirectActionProviderResponse(
                EvaluationActionType.TOOL_CALL, {"tool_name": "calculator", "parameters": {}}
            ),
            EvaluationFeedbackType.TOOL_RESPONSE: DirectActionProviderResponse(
                EvaluationActionType.TOOL_CALL, {"tool_name": "calculator", "parameters": {}}
            ),
        }), {"calculator": {}}, "fake-v1")
        budget = EvaluationBudget(2, 1)
        first = agent.step(AgentStepInput(
            case,
            DeterministicEvaluationEnvironment(EnvironmentConfig("m16-budget", {})).reset(case),
            EvaluationBudgetState(budget),
        ))
        self.assertEqual(first.action.action_type, EvaluationActionType.TOOL_CALL)
        self.assertEqual(EvaluationBudgetState(budget, tool_calls_used=1).remaining_tool_calls, 0)
        self.assertTrue(assess_cohort_a_eligibility(case).eligible)


if __name__ == "__main__":
    unittest.main()
