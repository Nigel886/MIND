"""Unit tests for M16 leakage-free projection, environment, and judge contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import inspect
import unittest

from src.core.task import Goal, Task
from src.evaluation.contracts import (
    EvaluationAction,
    EvaluationActionType,
    EvaluationCase,
    EvaluationFeedbackType,
    EvaluationTrace,
)
from src.evaluation.execution import EnvironmentInteraction, EvaluationBudget, EvaluationBudgetState
from src.evaluation.m16_leakage_free import (
    M16ExactCompletionJudge,
    M16PrivateEvaluationEnvironment,
    M16PrivateEnvironmentSpecification,
    M16PrivateTruth,
    M16_COMPLETION_SEMANTICS_VERSION,
    M16CompletionMode,
    m16_completion_mode,
    project_m16_legacy_task,
)


def _metadata(family: str, limit: int) -> dict:
    return {"m16_cohort_a": {
        "task_family": family, "tool_call_limit": limit,
        "requires_planning": False, "requires_multi_tool": False,
        "requires_dependent_multistep": False, "requires_recovery": False,
    }}


def _case(task: Task) -> EvaluationCase:
    return EvaluationCase("m16.case.001", task)


class ProjectionTests(unittest.TestCase):
    def test_direct_and_calculator_projection_add_exact_null_sentinel(self) -> None:
        direct = Task(Goal("return", ("return",)), {"value": {"a": [1]}}, metadata=_metadata("direct_answer", 0))
        calculator = Task(Goal("calculate", ("calculate",)), {"operation": "add", "operands": [2, 3]}, metadata=_metadata("controlled_single_tool", 1))
        projected_direct = project_m16_legacy_task(direct)
        projected_calculator = project_m16_legacy_task(calculator)
        self.assertEqual(projected_direct.input["expected_answer"], None)
        self.assertEqual(projected_calculator.input["expected_answer"], None)
        self.assertNotIn("expected_answer", direct.input)
        self.assertNotIn("expected_answer", calculator.input)
        self.assertIsNot(projected_direct, direct)

    def test_projection_rejects_public_schema_and_metadata_violations(self) -> None:
        invalids = (
            Task(Goal("x", ("x",)), {"value": "x", "extra": 1}, metadata=_metadata("direct_answer", 0)),
            Task(Goal("x", ("x",)), {"value": "x", "expected_answer": "x"}, metadata=_metadata("direct_answer", 0)),
            Task(Goal("x", ("x",)), {"operation": "divide", "operands": [2, 1]}, metadata=_metadata("controlled_single_tool", 1)),
            Task(Goal("x", ("x",)), {"operation": "add", "operands": [1]}, metadata=_metadata("controlled_single_tool", 1)),
            Task(Goal("x", ("x",)), {"operation": "add", "operands": [True, 1]}, metadata=_metadata("controlled_single_tool", 1)),
            Task(Goal("x", ("x",)), {"value": "x"}, metadata=_metadata("direct_answer", 1)),
        )
        for task in invalids:
            with self.subTest(task=task.to_dict()["input"]):
                with self.assertRaises((TypeError, ValueError)):
                    project_m16_legacy_task(task)


class PrivateTruthTests(unittest.TestCase):
    def test_private_truth_is_immutable_private_serializable_only(self) -> None:
        truth = M16PrivateTruth({"nested": [1]}, "m16.exact.v1")
        self.assertEqual(truth, M16PrivateTruth.from_private_dict(truth.to_private_dict()))
        self.assertFalse(hasattr(truth, "to_dict"))
        with self.assertRaises(FrozenInstanceError):
            truth.judge_id = "changed"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            truth.expected_answer["nested"] = ()  # type: ignore[index]

    def test_private_environment_never_emits_completion_context_and_is_deterministic(self) -> None:
        task = Task(Goal("calc", ("calc",)), {"operation": "multiply", "operands": [2, 3]}, metadata=_metadata("controlled_single_tool", 1))
        case = _case(task)
        spec = M16PrivateEnvironmentSpecification("m16.private.env", {"visible": "input"})
        first = M16PrivateEvaluationEnvironment(spec)
        second = M16PrivateEvaluationEnvironment(spec)
        reset = first.reset(case)
        self.assertNotIn("completion_context", reset.payload)
        self.assertEqual(reset, second.reset(case))
        feedback = first.apply(
            EvaluationAction(EvaluationActionType.TOOL_CALL, {"tool_name": "calculator", "parameters": {"operation": "multiply", "operands": [2, 3]}}),
            EvaluationBudgetState(EvaluationBudget(2, 1), steps_used=1),
        )
        self.assertEqual(feedback.feedback_type, EvaluationFeedbackType.TOOL_RESPONSE)
        self.assertEqual(feedback.payload["response"]["output"], 6)
        with self.assertRaises(ValueError):
            M16PrivateEnvironmentSpecification("m16-leak", {"expected_answer": "leak"})


class JudgeTests(unittest.TestCase):
    def test_exact_judge_direct_canonical_json_and_private_payload(self) -> None:
        task = Task(Goal("return", ("return",)), {"value": {"a": 1}}, metadata=_metadata("direct_answer", 0))
        case = _case(task)
        judge = M16ExactCompletionJudge(M16PrivateTruth({"a": 1}, "m16.direct.v1"))
        correct = judge.evaluate(case, (), EvaluationBudgetState(EvaluationBudget(1, 0)), EvaluationAction(EvaluationActionType.ANSWER, {"answer": {"a": 1}}))
        wrong = judge.evaluate(case, (), EvaluationBudgetState(EvaluationBudget(1, 0)), EvaluationAction(EvaluationActionType.ANSWER, {"answer": {"a": 2}}))
        self.assertEqual(correct.outcome_type.value, "success")
        self.assertEqual(wrong.payload, {"failure_category": "incorrect_answer"})
        self.assertNotIn("expected_answer", correct.to_dict())
        self.assertNotIn("expected_answer", wrong.to_dict())
        trace = EvaluationTrace(
            (EvaluationAction(EvaluationActionType.ANSWER, {"answer": {"a": 2}}),),
            (),
            wrong,
        )
        self.assertNotIn("expected_answer", str(trace.to_dict()))
        self.assertNotIn("m16.direct.v1", str(trace.to_dict()))

    def test_exact_judge_calculator_tool_outcome_and_no_provider_dependency(self) -> None:
        task = Task(Goal("calc", ("calc",)), {"operation": "add", "operands": [2, 3]}, metadata=_metadata("controlled_single_tool", 1))
        case = _case(task)
        judge = M16ExactCompletionJudge(M16PrivateTruth(5, "m16.calculator.v1"))
        action = EvaluationAction(EvaluationActionType.TOOL_CALL, {"tool_name": "calculator", "parameters": {"operation": "add", "operands": [2, 3]}})
        feedback = M16PrivateEvaluationEnvironment(M16PrivateEnvironmentSpecification("m16.env")).reset(case)
        environment = M16PrivateEvaluationEnvironment(M16PrivateEnvironmentSpecification("m16.env")); environment.reset(case)
        correct_feedback = environment.apply(action, EvaluationBudgetState(EvaluationBudget(2, 1), steps_used=1))
        correct = judge.evaluate(case, (EnvironmentInteraction(action, correct_feedback),), EvaluationBudgetState(EvaluationBudget(2, 1)), None)
        wrong_action = EvaluationAction(EvaluationActionType.TOOL_CALL, {"tool_name": "calculator", "parameters": {"operation": "multiply", "operands": [2, 3]}})
        wrong_feedback = environment.apply(wrong_action, EvaluationBudgetState(EvaluationBudget(2, 1), steps_used=1))
        wrong = judge.evaluate(case, (EnvironmentInteraction(wrong_action, wrong_feedback),), EvaluationBudgetState(EvaluationBudget(2, 1)), None)
        self.assertEqual(correct.outcome_type.value, "success")
        self.assertEqual(wrong.outcome_type.value, "failure")
        self.assertEqual(M16_COMPLETION_SEMANTICS_VERSION, "m16_completion_v2")
        self.assertEqual(m16_completion_mode(case), M16CompletionMode.EVALUATOR_TOOL_OUTCOME)
        source = inspect.getsource(M16ExactCompletionJudge)
        self.assertNotIn("LLM", source)
        self.assertNotIn("Provider", source)


if __name__ == "__main__":
    unittest.main()
