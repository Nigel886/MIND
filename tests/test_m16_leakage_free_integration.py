"""Integration tests proving M16 privacy while preserving frozen MIND/M14 behavior."""

from __future__ import annotations

import unittest

from src.core.goal_policy import GoalAwarePolicyEngine
from src.core.runtime import RuntimeController
from src.core.observation import Observation
from src.core.task import Goal, Task
from src.evaluation.contracts import EvaluationCase, EvaluationFeedback, EvaluationFeedbackType
from src.evaluation.direct_tool_calling import (
    DirectActionProviderResponse,
    DirectToolCallingEvaluationAgent,
    FakeDirectActionProvider,
)
from src.evaluation.environment import DeterministicEvaluationEnvironment, EnvironmentConfig
from src.evaluation.execution import AgentStepInput, EvaluationBudget, EvaluationBudgetState
from src.evaluation.m16_leakage_free import (
    M16MINDGoalDirectedEvaluationAdapter,
    M16PrivateTruth,
    project_m16_legacy_task,
)
from src.evaluation.contracts import EvaluationActionType


def _metadata(family: str, limit: int) -> dict:
    return {"m16_cohort_a": {
        "task_family": family, "tool_call_limit": limit,
        "requires_planning": False, "requires_multi_tool": False,
        "requires_dependent_multistep": False, "requires_recovery": False,
    }}


class M16LeakageFreeIntegrationTests(unittest.TestCase):
    def test_projected_task_makes_frozen_policy_executable_without_truth(self) -> None:
        public = Task(Goal("calculate", ("calculate",)), {"operation": "multiply", "operands": [17, 23]}, metadata=_metadata("controlled_single_tool", 1))
        projected = project_m16_legacy_task(public)
        state = RuntimeController.initialize(Observation("m16-test", {}))
        policy = GoalAwarePolicyEngine.generate(projected, state)
        self.assertEqual(policy.action, "call_tool")
        self.assertIsNone(projected.input["expected_answer"])
        self.assertNotIn("expected_answer", public.input)

    def test_mind_adapter_uses_private_projection_and_direct_baseline_gets_public_task(self) -> None:
        public = Task(Goal("return", ("return",)), {"value": "ready"}, metadata=_metadata("direct_answer", 0))
        case = EvaluationCase("m16.integration.001", public)
        state = EvaluationBudgetState(EvaluationBudget(1, 0))
        feedback = EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)
        mind_result = M16MINDGoalDirectedEvaluationAdapter().step(AgentStepInput(case, feedback, state))
        captured = []

        class CapturingProvider:
            def decide(self, request):
                captured.append(request.task)
                return DirectActionProviderResponse(EvaluationActionType.ANSWER, {"answer": "ready"})

        direct_result = DirectToolCallingEvaluationAgent(CapturingProvider(), {}, "fake-v1").step(AgentStepInput(case, feedback, state))
        self.assertEqual(mind_result.action.to_dict()["payload"], {"answer": "ready"})
        self.assertEqual(direct_result.action.to_dict()["payload"], {"answer": "ready"})
        self.assertNotIn("expected_answer", captured[0]["input"])
        self.assertNotIn("expected_answer", public.input)

    def test_m14_environment_historical_completion_context_behavior_is_unchanged(self) -> None:
        case = EvaluationCase("m14.compat", Task(Goal("x", ("x",)), {"value": "x"}))
        feedback = DeterministicEvaluationEnvironment(EnvironmentConfig(
            "m14-compat", {}, completion_context={"expected_answer": "x"}
        )).reset(case)
        self.assertEqual(feedback.payload["completion_context"]["expected_answer"], "x")

    def test_private_truth_is_never_an_adapter_input(self) -> None:
        truth = M16PrivateTruth("secret-answer", "m16.private")
        public = Task(Goal("return", ("return",)), {"value": "ready"}, metadata=_metadata("direct_answer", 0))
        projected = project_m16_legacy_task(public)
        self.assertNotIn(truth.expected_answer, projected.input.values())
        self.assertNotIn("secret-answer", str(projected.to_dict()))


if __name__ == "__main__":
    unittest.main()
