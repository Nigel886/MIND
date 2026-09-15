"""Focused contract tests for M17 typed environment outcomes."""

from __future__ import annotations

import inspect
import unittest

from src.core.cognitive_session import CognitiveAgentSession, CognitiveSessionPhase
from src.core.environment_outcome import (
    EnvironmentOutcome,
    EnvironmentOutcomeCategory,
    EnvironmentOutcomeReason,
    outcome_from_registry_admission,
    outcome_from_tool_result,
)
from src.core.observation import Observation
from src.core.policy import Policy
from src.core.policy_context import PolicyDecisionContext
from src.core.runtime import RuntimeController
from src.core.task import Goal, Task
from src.core.tool import ToolRegistry, ToolResult


class _Tool:
    name = "public_tool"
    parameter_schema = {
        "required": ["value"],
        "properties": {"value": {}},
        "additionalProperties": False,
    }

    def execute(self, parameters):
        return ToolResult(self.name, True, parameters["value"], None, parameters)


class _OutcomePolicy:
    def __init__(self) -> None:
        self.contexts: list[PolicyDecisionContext] = []

    def decide(self, context: PolicyDecisionContext) -> Policy:
        self.contexts.append(context)
        if context.latest_observation is None:
            return Policy("call_tool", {"tool_name": "public_tool", "tool_parameters": {"value": 1}}, {})
        return Policy("produce_answer", {"answer": "policy_decided"}, {})


class EnvironmentOutcomeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.task = Task(
            Goal("handle public result", ("return a public result",)),
            {"request": "public", "expected_answer": "private"},
        )

    def test_all_categories_are_immutable_serializable_and_closed(self) -> None:
        outcomes = (
            EnvironmentOutcome(EnvironmentOutcomeCategory.SUCCESS, EnvironmentOutcomeReason.SUCCESSFUL_RESULT, {"output": 1}),
            EnvironmentOutcome(EnvironmentOutcomeCategory.RECOVERABLE_FAILURE, EnvironmentOutcomeReason.TOOL_TRANSIENT_FAILURE, {"tool_name": "public_tool"}),
            EnvironmentOutcome(EnvironmentOutcomeCategory.UNRECOVERABLE_FAILURE, EnvironmentOutcomeReason.TOOL_PERMANENT_FAILURE, {"tool_name": "public_tool"}),
            EnvironmentOutcome(EnvironmentOutcomeCategory.INVALID_ACTION, EnvironmentOutcomeReason.TOOL_NOT_FOUND, {"tool_name": "missing"}),
        )
        for outcome in outcomes:
            with self.subTest(category=outcome.category):
                self.assertEqual(EnvironmentOutcome.from_dict(outcome.to_dict()), outcome)
                with self.assertRaises(TypeError):
                    outcome.payload["changed"] = True
        with self.assertRaises(ValueError):
            EnvironmentOutcome(EnvironmentOutcomeCategory.SUCCESS, EnvironmentOutcomeReason.TOOL_NOT_FOUND)
        with self.assertRaises(TypeError):
            EnvironmentOutcome(EnvironmentOutcomeCategory.SUCCESS, "benchmark_reason")

    def test_outcome_rejects_private_truth_and_raw_exception_data(self) -> None:
        for key in ("expected_answer", "ground_truth", "correct_tool", "evaluator_success", "traceback", "exception"):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    EnvironmentOutcome(
                        EnvironmentOutcomeCategory.RECOVERABLE_FAILURE,
                        EnvironmentOutcomeReason.TOOL_TRANSIENT_FAILURE,
                        {"nested": {key: "private"}},
                    )

    def test_registry_admission_owns_unknown_and_invalid_parameter_actions(self) -> None:
        registry = ToolRegistry(); registry.register(_Tool())
        unknown = outcome_from_registry_admission(registry, "missing", {})
        invalid = outcome_from_registry_admission(registry, "public_tool", {})
        valid = outcome_from_registry_admission(registry, "public_tool", {"value": 1})
        self.assertEqual((unknown.category, unknown.reason), (EnvironmentOutcomeCategory.INVALID_ACTION, EnvironmentOutcomeReason.TOOL_NOT_FOUND))
        self.assertEqual((invalid.category, invalid.reason), (EnvironmentOutcomeCategory.INVALID_ACTION, EnvironmentOutcomeReason.INVALID_ARGUMENTS))
        self.assertIsNone(valid)

    def test_tool_result_mapping_keeps_success_transient_and_permanent_distinct(self) -> None:
        success = ToolResult("public_tool", True, {"value": 1}, None, {"value": 1})
        failed = ToolResult("public_tool", False, None, "unavailable", {"value": 1})
        self.assertEqual(outcome_from_tool_result(success).category, EnvironmentOutcomeCategory.SUCCESS)
        self.assertEqual(
            outcome_from_tool_result(failed, EnvironmentOutcomeReason.TOOL_TRANSIENT_FAILURE).category,
            EnvironmentOutcomeCategory.RECOVERABLE_FAILURE,
        )
        self.assertEqual(
            outcome_from_tool_result(failed, EnvironmentOutcomeReason.TOOL_PERMANENT_FAILURE).category,
            EnvironmentOutcomeCategory.UNRECOVERABLE_FAILURE,
        )

    def test_typed_failure_observation_advances_immutable_state(self) -> None:
        outcome = EnvironmentOutcome(
            EnvironmentOutcomeCategory.RECOVERABLE_FAILURE,
            EnvironmentOutcomeReason.TOOL_TRANSIENT_FAILURE,
            {"tool_name": "public_tool"},
        )
        before = RuntimeController.initialize()
        observation = outcome.to_observation()
        after = RuntimeController.apply_inference(before, observation)
        self.assertIsNot(after, before)
        self.assertEqual(before.belief.version, 0)
        self.assertEqual(after.belief.version, 1)
        self.assertEqual(after.observation, observation)

    def test_outcome_observation_is_policy_safe_and_does_not_select_recovery(self) -> None:
        outcome = EnvironmentOutcome(
            EnvironmentOutcomeCategory.RECOVERABLE_FAILURE,
            EnvironmentOutcomeReason.TOOL_TRANSIENT_FAILURE,
            {"tool_name": "public_tool", "value": 9},
        )
        context = PolicyDecisionContext.from_runtime(
            self.task,
            RuntimeController.initialize(),
            outcome.to_observation(),
        )
        visible = context.latest_observation.content["environment_outcome"]
        self.assertEqual(visible["category"], "recoverable_failure")
        self.assertEqual(visible["reason"], "tool_transient_failure")
        self.assertNotIn("expected_answer", str(context.to_dict()))

        policy = _OutcomePolicy()
        session = CognitiveAgentSession(2, policy_engine=policy)
        session.start(self.task)
        self.assertEqual(session.step().action_request.action, "tool_call")
        session.observe(outcome.to_observation())
        next_step = session.step()
        self.assertEqual(next_step.phase, CognitiveSessionPhase.AWAITING_OBSERVATION)
        self.assertEqual(next_step.action_request.action, "answer")
        self.assertEqual(len(policy.contexts), 2)
        self.assertEqual(policy.contexts[1].latest_observation.content["environment_outcome"]["reason"], "tool_transient_failure")
        self.assertNotIn("ToolRegistry", inspect.getsource(CognitiveAgentSession))

    def test_unrecoverable_and_invalid_outcomes_remain_observable_without_loop_control(self) -> None:
        for category, reason in (
            (EnvironmentOutcomeCategory.UNRECOVERABLE_FAILURE, EnvironmentOutcomeReason.TOOL_EXECUTION_ERROR),
            (EnvironmentOutcomeCategory.INVALID_ACTION, EnvironmentOutcomeReason.INVALID_ARGUMENTS),
        ):
            with self.subTest(category=category):
                observation = EnvironmentOutcome(category, reason, {}).to_observation()
                self.assertEqual(EnvironmentOutcome.from_observation(observation).category, category)


if __name__ == "__main__":
    unittest.main()
