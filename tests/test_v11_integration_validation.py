"""Release-freeze integration validation for the connected MIND-Lite v1.1 path."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.core.cognitive_execution_runtime import (
    CognitiveExecutionBudget,
    CognitiveExecutionController,
    CognitiveExecutionTerminationReason,
)
from src.core.environment_outcome import (
    EnvironmentOutcome,
    EnvironmentOutcomeCategory,
    EnvironmentOutcomeReason,
)
from src.core.policy import Policy
from src.core.runtime import RuntimeController
from src.core.task import Goal, Task
from src.core.tool import CapabilityDescriptor


def _success(payload=None):
    return EnvironmentOutcome(
        EnvironmentOutcomeCategory.SUCCESS,
        EnvironmentOutcomeReason.SUCCESSFUL_RESULT,
        payload or {},
    )


class _Environment:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.actions = []

    def apply(self, action):
        self.actions.append(action.to_dict())
        return self._outcomes.pop(0)


class _TwoToolPolicy:
    def __init__(self): self.contexts = []
    def decide(self, context):
        self.contexts.append(context)
        if context.latest_observation is None:
            return Policy("call_tool", {"tool_name": "extract", "tool_parameters": {}}, {})
        payload = context.latest_observation.content["environment_outcome"]["payload"]
        if "x" in payload:
            return Policy("call_tool", {"tool_name": "transform", "tool_parameters": {"value": payload["x"]}}, {})
        return Policy("produce_answer", {"answer": {"result": payload["result"]}}, {})


class _ThreeStagePolicy:
    def __init__(self): self.contexts = []
    def decide(self, context):
        self.contexts.append(context)
        if context.latest_observation is None:
            return Policy("call_tool", {"tool_name": "a", "tool_parameters": {}}, {})
        payload = context.latest_observation.content["environment_outcome"]["payload"]
        if "a" in payload:
            return Policy("call_tool", {"tool_name": "b", "tool_parameters": {"a": payload["a"]}}, {})
        if "b" in payload:
            return Policy("call_tool", {"tool_name": "c", "tool_parameters": {"b": payload["b"]}}, {})
        return Policy("produce_answer", {"answer": payload["c"]}, {})


class _OutcomePolicy:
    def __init__(self, first_tool="primary"): self.contexts = []; self.first_tool = first_tool
    def decide(self, context):
        self.contexts.append(context)
        if context.latest_observation is None:
            return Policy("call_tool", {"tool_name": self.first_tool, "tool_parameters": {}}, {})
        outcome = context.latest_observation.content["environment_outcome"]
        if outcome["category"] == "recoverable_failure":
            return Policy("call_tool", {"tool_name": "alternate", "tool_parameters": {"seen_reason": outcome["reason"]}}, {})
        if outcome["category"] == "invalid_action":
            return Policy("call_tool", {"tool_name": "corrected", "tool_parameters": {}}, {})
        return Policy("produce_answer", {"answer": "public-submission"}, {})


class _LoopPolicy:
    def __init__(self): self.contexts = []
    def decide(self, context):
        self.contexts.append(context)
        return Policy("call_tool", {"tool_name": "loop", "tool_parameters": {}}, {})


class _AnswerPolicy:
    def __init__(self): self.contexts = []
    def decide(self, context):
        self.contexts.append(context)
        return Policy("produce_answer", {"answer": "public-submission"}, {})


class V11IntegrationValidationTest(unittest.TestCase):
    def setUp(self):
        self.task = Task(
            Goal("submit a public response", ("submit a response",)),
            {
                "request": "public request",
                "expected_answer": "private",
                "ground_truth": "private",
                "correct_tool": "private",
                "correct_action": "private",
                "difficulty": "private",
            },
            metadata={"evaluator_success": True, "private_judge_metadata": {"x": 1}},
        )
        self.capabilities = (
            CapabilityDescriptor("extract"),
            CapabilityDescriptor("transform"),
            CapabilityDescriptor("a"),
            CapabilityDescriptor("b"),
            CapabilityDescriptor("c"),
            CapabilityDescriptor("alternate"),
            CapabilityDescriptor("corrected"),
        )

    def _run(self, environment, policy, budget):
        return CognitiveExecutionController(
            environment,
            budget,
            policy_engine=policy,
            capabilities=self.capabilities,
        ).run(self.task)

    def test_a_dependent_two_tool_composition_and_truth_firewall(self):
        environment = _Environment((_success({"x": 11}), _success({"result": 22})))
        policy = _TwoToolPolicy()
        result = self._run(environment, policy, CognitiveExecutionBudget(4))
        self.assertEqual(result.termination_reason, CognitiveExecutionTerminationReason.ANSWER_SUBMITTED)
        self.assertEqual(environment.actions[1]["parameters"]["parameters"], {"value": 11})
        for context in policy.contexts:
            public = str(context.to_dict())
            for private in ("expected_answer", "ground_truth", "correct_tool", "correct_action", "evaluator_success", "difficulty", "private_judge_metadata"):
                self.assertNotIn(private, public)

    def test_b_three_stage_observation_progression_rebuilds_contexts(self):
        environment = _Environment((_success({"a": 2}), _success({"b": 3}), _success({"c": 5})))
        policy = _ThreeStagePolicy()
        result = self._run(environment, policy, CognitiveExecutionBudget(5))
        self.assertEqual(result.termination_reason, CognitiveExecutionTerminationReason.ANSWER_SUBMITTED)
        self.assertEqual(result.cycles, 4)
        self.assertEqual(len(policy.contexts), 4)
        self.assertEqual(policy.contexts[1].latest_observation.content["environment_outcome"]["payload"]["a"], 2)
        self.assertEqual(policy.contexts[2].latest_observation.content["environment_outcome"]["payload"]["b"], 3)
        self.assertEqual(environment.actions[2]["parameters"]["parameters"], {"b": 3})

    def test_c_recoverable_failure_is_admitted_and_policy_selects_alternate(self):
        environment = _Environment((
            EnvironmentOutcome(EnvironmentOutcomeCategory.RECOVERABLE_FAILURE, EnvironmentOutcomeReason.TOOL_TRANSIENT_FAILURE, {"tool_name": "primary"}),
            _success({"ok": True}),
        ))
        policy = _OutcomePolicy()
        result = self._run(environment, policy, CognitiveExecutionBudget(4, max_recoverable_failures=2))
        self.assertEqual(result.termination_reason, CognitiveExecutionTerminationReason.ANSWER_SUBMITTED)
        self.assertEqual(result.recoverable_failures, 1)
        self.assertEqual(environment.actions[1]["parameters"]["tool_name"], "alternate")
        self.assertEqual(policy.contexts[1].latest_observation.content["environment_outcome"]["reason"], "tool_transient_failure")

    def test_d_invalid_action_correction_is_environment_owned_and_session_registry_free(self):
        environment = _Environment((
            EnvironmentOutcome(EnvironmentOutcomeCategory.INVALID_ACTION, EnvironmentOutcomeReason.TOOL_NOT_FOUND, {"tool_name": "unknown"}),
            _success({"ok": True}),
        ))
        result = self._run(environment, _OutcomePolicy("unknown"), CognitiveExecutionBudget(4, max_invalid_actions=2))
        self.assertEqual(result.termination_reason, CognitiveExecutionTerminationReason.ANSWER_SUBMITTED)
        self.assertEqual(result.invalid_actions, 1)
        self.assertEqual(environment.actions[1]["parameters"]["tool_name"], "corrected")

    def test_e_unrecoverable_failure_progresses_state_and_prevents_later_policy(self):
        environment = _Environment((
            EnvironmentOutcome(EnvironmentOutcomeCategory.UNRECOVERABLE_FAILURE, EnvironmentOutcomeReason.TOOL_PERMANENT_FAILURE, {"tool_name": "primary"}),
        ))
        policy = _LoopPolicy()
        states = []
        original = RuntimeController.apply_inference
        def capture(state, observation):
            states.append((state, state.to_dict()))
            return original(state, observation)
        with patch.object(RuntimeController, "apply_inference", side_effect=capture):
            result = self._run(environment, policy, CognitiveExecutionBudget(3))
        self.assertEqual(result.termination_reason, CognitiveExecutionTerminationReason.UNRECOVERABLE_ENVIRONMENT_FAILURE)
        self.assertEqual(len(policy.contexts), 1)
        self.assertGreaterEqual(len(states), 2)
        for state, serialized in states:
            self.assertEqual(state.to_dict(), serialized)

    def test_f_to_i_all_budget_boundaries_are_deterministic_at_limit_one(self):
        self.assertEqual(
            self._run(_Environment((_success(),)), _LoopPolicy(), CognitiveExecutionBudget(1)).termination_reason,
            CognitiveExecutionTerminationReason.BUDGET_EXHAUSTED,
        )
        self.assertEqual(
            self._run(_Environment((_success(),)), _LoopPolicy(), CognitiveExecutionBudget(3, max_tool_calls=1)).tool_calls,
            1,
        )
        self.assertEqual(
            self._run(_Environment((EnvironmentOutcome(EnvironmentOutcomeCategory.INVALID_ACTION, EnvironmentOutcomeReason.TOOL_NOT_FOUND),)), _LoopPolicy(), CognitiveExecutionBudget(3, max_invalid_actions=1)).termination_reason,
            CognitiveExecutionTerminationReason.BUDGET_EXHAUSTED,
        )
        self.assertEqual(
            self._run(_Environment((EnvironmentOutcome(EnvironmentOutcomeCategory.RECOVERABLE_FAILURE, EnvironmentOutcomeReason.TOOL_TRANSIENT_FAILURE),)), _LoopPolicy(), CognitiveExecutionBudget(3, max_recoverable_failures=1)).termination_reason,
            CognitiveExecutionTerminationReason.BUDGET_EXHAUSTED,
        )

    def test_j_terminal_answer_is_submission_not_evaluator_success_and_capabilities_are_frozen(self):
        environment = _Environment(())
        policy = _AnswerPolicy()
        result = self._run(environment, policy, CognitiveExecutionBudget(1))
        self.assertEqual(result.termination_reason, CognitiveExecutionTerminationReason.ANSWER_SUBMITTED)
        self.assertEqual(environment.actions, [])
        self.assertEqual(result.answer, "public-submission")
        self.assertEqual([item.tool_id for item in policy.contexts[0].capabilities], [item.tool_id for item in self.capabilities])
        with self.assertRaises(AttributeError):
            policy.contexts[0].capabilities[0].tool_id = "changed"


if __name__ == "__main__":
    unittest.main()
