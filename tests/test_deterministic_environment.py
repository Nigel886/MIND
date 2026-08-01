"""Tests for the M14 deterministic evaluation environment."""

from __future__ import annotations

import inspect
import unittest
from dataclasses import FrozenInstanceError

from src.core.task import Goal, Task
from src.evaluation.contracts import (
    EvaluationAction,
    EvaluationActionType,
    EvaluationCase,
    EvaluationFeedbackType,
)
from src.evaluation.environment import (
    DeterministicEvaluationEnvironment,
    EnvironmentConfig,
    EnvironmentSnapshot,
    FailureInjectionRule,
    FailureInjectionType,
)
from src.evaluation.execution import EvaluationBudget, EvaluationBudgetState


class DeterministicEnvironmentTest(unittest.TestCase):
    """Verify local deterministic public action-to-feedback behavior."""

    def setUp(self) -> None:
        self.case = EvaluationCase(
            "m14.environment.001",
            Task(Goal("calculate", ("correct",)), {"operation": "multiply"}),
        )
        self.budget = EvaluationBudgetState(EvaluationBudget(3, 2))
        self.action = EvaluationAction(
            EvaluationActionType.TOOL_CALL,
            {"tool_name": "calculator", "parameters": {"operation": "multiply", "operands": [17, 23]}},
        )

    def test_reset_and_simulated_tool_response_are_deterministic(self) -> None:
        config = EnvironmentConfig(
            "local.math.v1",
            {"calculator": {"output": 391}},
            initial_payload={"task": "calculate"},
            completion_context={"expected_answer": 391},
        )
        environment = DeterministicEvaluationEnvironment(config)
        initial = environment.reset(self.case)
        feedback = environment.apply(self.action, self.budget)

        self.assertEqual(initial.feedback_type, EvaluationFeedbackType.INITIAL_INPUT)
        self.assertEqual(initial.payload["completion_context"], {"expected_answer": 391})
        self.assertEqual(feedback.feedback_type, EvaluationFeedbackType.TOOL_RESPONSE)
        self.assertEqual(feedback.to_dict()["payload"]["response"], {"output": 391})
        self.assertEqual(environment.snapshot().action_count, 1)

        replay = DeterministicEvaluationEnvironment(config)
        self.assertEqual(replay.reset(self.case), initial)
        self.assertEqual(replay.apply(self.action, self.budget), feedback)

    def test_hard_budget_has_priority_and_does_not_consume_failure(self) -> None:
        rule = FailureInjectionRule("timeout-on-first", 1, FailureInjectionType.TIMEOUT)
        environment = DeterministicEvaluationEnvironment(EnvironmentConfig("budget.v1", {"calculator": {}}, (rule,)))
        environment.reset(self.case)
        exhausted = EvaluationBudgetState(EvaluationBudget(0, 1))

        feedback = environment.apply(self.action, exhausted)
        self.assertEqual(feedback.feedback_type, EvaluationFeedbackType.BUDGET)
        self.assertEqual(environment.snapshot().consumed_failures, ())

    def test_injected_failures_match_once_in_priority_order(self) -> None:
        rules = (
            FailureInjectionRule("logical-timeout", 1, FailureInjectionType.TIMEOUT),
            FailureInjectionRule("tool-failure", 2, FailureInjectionType.TOOL_FAILURE, tool_name="calculator"),
        )
        environment = DeterministicEvaluationEnvironment(EnvironmentConfig("failures.v1", {"calculator": {}}, rules))
        environment.reset(self.case)
        first = environment.apply(self.action, self.budget)
        second = environment.apply(self.action, self.budget)

        self.assertEqual(first.feedback_type, EvaluationFeedbackType.TIMEOUT)
        self.assertEqual(second.feedback_type, EvaluationFeedbackType.TOOL_FAILURE)
        self.assertEqual(environment.snapshot().consumed_failures, ("logical-timeout", "tool-failure"))

    def test_invalid_actions_and_injected_invalid_action_are_explicit(self) -> None:
        environment = DeterministicEvaluationEnvironment(EnvironmentConfig("invalid.v1", {"calculator": {}}))
        environment.reset(self.case)
        answer = EvaluationAction(EvaluationActionType.ANSWER, {"answer": 391})
        self.assertEqual(environment.apply(answer, self.budget).feedback_type, EvaluationFeedbackType.INVALID_ACTION)

        injected = DeterministicEvaluationEnvironment(
            EnvironmentConfig(
                "injected-invalid.v1",
                {"calculator": {}},
                (FailureInjectionRule("reject", 1, FailureInjectionType.INVALID_ACTION, action_type=EvaluationActionType.TOOL_CALL),),
            )
        )
        injected.reset(self.case)
        self.assertEqual(injected.apply(self.action, self.budget).feedback_type, EvaluationFeedbackType.INVALID_ACTION)

    def test_models_round_trip_are_immutable_and_no_tool_registry_dependency(self) -> None:
        config = EnvironmentConfig(
            "roundtrip.v1",
            {"calculator": {"nested": [1]}},
            (FailureInjectionRule("budget", 1, FailureInjectionType.BUDGET_EXHAUSTION, metadata={"kind": "limit"}),),
            public_tool_state={"available": ["calculator"]},
            scenario_seed=7,
        )
        restored = EnvironmentConfig.from_dict(config.to_dict())
        self.assertEqual(restored, config)
        with self.assertRaises(FrozenInstanceError):
            config.environment_id = "other"

        snapshot = EnvironmentSnapshot("roundtrip.v1", 0, (), {"available": ["calculator"]})
        self.assertEqual(EnvironmentSnapshot.from_dict(snapshot.to_dict()), snapshot)
        source = inspect.getsource(DeterministicEvaluationEnvironment)
        self.assertNotIn("ToolRegistry", source)

    def test_invalid_configuration_and_lifecycle_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            FailureInjectionRule(" rule ", 1, FailureInjectionType.TIMEOUT)
        with self.assertRaises(ValueError):
            FailureInjectionRule("bad", 0, FailureInjectionType.TIMEOUT)
        first = FailureInjectionRule("first", 1, FailureInjectionType.TIMEOUT)
        second = FailureInjectionRule("second", 1, FailureInjectionType.BUDGET_EXHAUSTION)
        with self.assertRaises(ValueError):
            EnvironmentConfig("overlap.v1", {}, (first, second))
        environment = DeterministicEvaluationEnvironment(EnvironmentConfig("lifecycle.v1", {}))
        with self.assertRaises(RuntimeError):
            environment.apply(self.action, self.budget)


if __name__ == "__main__":
    unittest.main()
