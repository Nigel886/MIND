"""Provider-free end-to-end tests for M17 multi-cycle runtime orchestration."""

from __future__ import annotations

import inspect
import unittest

from src.core.cognitive_execution_runtime import (
    CognitiveExecutionBudget,
    CognitiveExecutionController,
    CognitiveExecutionResult,
    CognitiveExecutionTerminationReason,
)
from src.core.environment_outcome import (
    EnvironmentOutcome,
    EnvironmentOutcomeCategory,
    EnvironmentOutcomeReason,
)
from src.core.policy import Policy
from src.core.task import Goal, Task
from src.core.tool import CapabilityDescriptor


def _success(**payload):
    return EnvironmentOutcome(
        EnvironmentOutcomeCategory.SUCCESS,
        EnvironmentOutcomeReason.SUCCESSFUL_RESULT,
        payload,
    )


class _ScriptedEnvironment:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.actions = []

    def apply(self, action):
        self.actions.append(action.to_dict())
        if not self.outcomes:
            raise RuntimeError("unexpected environment call")
        return self.outcomes.pop(0)


class _TwoToolPolicy:
    def __init__(self):
        self.contexts = []

    def decide(self, context):
        self.contexts.append(context)
        observation = context.latest_observation
        if observation is None:
            return Policy("call_tool", {"tool_name": "tool_a", "tool_parameters": {}}, {})
        payload = observation.content["environment_outcome"]["payload"]
        if "x" in payload:
            return Policy("call_tool", {"tool_name": "tool_b", "tool_parameters": {"input": payload["x"]}}, {})
        return Policy("produce_answer", {"answer": {"submitted": payload["result"]}}, {})


class _RecoverablePolicy:
    def __init__(self): self.contexts = []
    def decide(self, context):
        self.contexts.append(context)
        if context.latest_observation is None:
            return Policy("call_tool", {"tool_name": "primary", "tool_parameters": {}}, {})
        outcome = context.latest_observation.content["environment_outcome"]
        if outcome["category"] == "recoverable_failure":
            return Policy("call_tool", {"tool_name": "alternate", "tool_parameters": {"reason": outcome["reason"]}}, {})
        return Policy("produce_answer", {"answer": "submitted"}, {})


class _InvalidCorrectionPolicy:
    def __init__(self): self.contexts = []
    def decide(self, context):
        self.contexts.append(context)
        if context.latest_observation is None:
            return Policy("call_tool", {"tool_name": "unknown", "tool_parameters": {}}, {})
        if context.latest_observation.content["environment_outcome"]["category"] == "invalid_action":
            return Policy("call_tool", {"tool_name": "valid", "tool_parameters": {}}, {})
        return Policy("produce_answer", {"answer": "submitted"}, {})


class _AlwaysToolPolicy:
    def __init__(self): self.calls = 0
    def decide(self, context):
        self.calls += 1
        return Policy("call_tool", {"tool_name": "loop", "tool_parameters": {}}, {})


class _RaisesPolicy:
    def decide(self, context): raise RuntimeError("private detail")


class CognitiveExecutionRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.task = Task(
            Goal("submit public answer", ("submit an answer",)),
            {"request": "public", "expected_answer": "private"},
        )
        self.capabilities = (
            CapabilityDescriptor("tool_a"),
            CapabilityDescriptor("tool_b"),
        )

    def _controller(self, environment, policy, budget):
        return CognitiveExecutionController(
            environment,
            budget,
            policy_engine=policy,
            capabilities=self.capabilities,
        )

    def test_two_tool_success_progresses_observation_and_policy_derived_parameter(self):
        environment = _ScriptedEnvironment((_success(x=7), _success(result=14)))
        policy = _TwoToolPolicy()
        result = self._controller(environment, policy, CognitiveExecutionBudget(4)).run(self.task)
        self.assertEqual(result.termination_reason, CognitiveExecutionTerminationReason.ANSWER_SUBMITTED)
        self.assertEqual(result.cycles, 3)
        self.assertEqual(result.tool_calls, 2)
        self.assertEqual(environment.actions[1]["parameters"], {"tool_name": "tool_b", "parameters": {"input": 7}})
        self.assertEqual(policy.contexts[1].latest_observation.content["environment_outcome"]["payload"]["x"], 7)
        self.assertEqual([item.tool_id for item in policy.contexts[0].capabilities], ["tool_a", "tool_b"])
        self.assertEqual(policy.contexts[0].capabilities, policy.contexts[2].capabilities)
        self.assertNotIn("expected_answer", str(policy.contexts[0].to_dict()))

    def test_recoverable_failure_reinvokes_policy_without_controller_selecting_recovery(self):
        environment = _ScriptedEnvironment((
            EnvironmentOutcome(EnvironmentOutcomeCategory.RECOVERABLE_FAILURE, EnvironmentOutcomeReason.TOOL_TRANSIENT_FAILURE, {"tool_name": "primary"}),
            _success(value="ok"),
        ))
        policy = _RecoverablePolicy()
        result = self._controller(environment, policy, CognitiveExecutionBudget(4, max_recoverable_failures=2)).run(self.task)
        self.assertEqual(result.termination_reason, CognitiveExecutionTerminationReason.ANSWER_SUBMITTED)
        self.assertEqual(result.recoverable_failures, 1)
        self.assertEqual(environment.actions[1]["parameters"]["tool_name"], "alternate")
        self.assertEqual(policy.contexts[1].latest_observation.content["environment_outcome"]["reason"], "tool_transient_failure")

    def test_invalid_action_correction_is_bounded_and_policy_selected(self):
        environment = _ScriptedEnvironment((
            EnvironmentOutcome(EnvironmentOutcomeCategory.INVALID_ACTION, EnvironmentOutcomeReason.TOOL_NOT_FOUND, {"tool_name": "unknown"}),
            _success(value="ok"),
        ))
        result = self._controller(environment, _InvalidCorrectionPolicy(), CognitiveExecutionBudget(4, max_invalid_actions=2)).run(self.task)
        self.assertEqual(result.termination_reason, CognitiveExecutionTerminationReason.ANSWER_SUBMITTED)
        self.assertEqual(result.invalid_actions, 1)
        self.assertEqual(environment.actions[1]["parameters"]["tool_name"], "valid")

    def test_unrecoverable_failure_is_admitted_then_terminates_without_reinvocation(self):
        environment = _ScriptedEnvironment((
            EnvironmentOutcome(EnvironmentOutcomeCategory.UNRECOVERABLE_FAILURE, EnvironmentOutcomeReason.TOOL_PERMANENT_FAILURE, {"tool_name": "tool_a"}),
        ))
        policy = _AlwaysToolPolicy()
        result = self._controller(environment, policy, CognitiveExecutionBudget(3)).run(self.task)
        self.assertEqual(result.termination_reason, CognitiveExecutionTerminationReason.UNRECOVERABLE_ENVIRONMENT_FAILURE)
        self.assertEqual(result.cycles, 1)
        self.assertEqual(policy.calls, 1)

    def test_cycle_tool_invalid_and_recoverable_budgets_terminate_deterministically(self):
        success_environment = _ScriptedEnvironment((_success(), _success(), _success()))
        self.assertEqual(
            self._controller(success_environment, _AlwaysToolPolicy(), CognitiveExecutionBudget(2)).run(self.task).termination_reason,
            CognitiveExecutionTerminationReason.BUDGET_EXHAUSTED,
        )
        tool_environment = _ScriptedEnvironment((_success(), _success()))
        self.assertEqual(
            self._controller(tool_environment, _AlwaysToolPolicy(), CognitiveExecutionBudget(4, max_tool_calls=1)).run(self.task).tool_calls,
            1,
        )
        invalid_environment = _ScriptedEnvironment((EnvironmentOutcome(EnvironmentOutcomeCategory.INVALID_ACTION, EnvironmentOutcomeReason.TOOL_NOT_FOUND),))
        self.assertEqual(
            self._controller(invalid_environment, _AlwaysToolPolicy(), CognitiveExecutionBudget(3, max_invalid_actions=1)).run(self.task).termination_reason,
            CognitiveExecutionTerminationReason.BUDGET_EXHAUSTED,
        )
        recoverable_environment = _ScriptedEnvironment((EnvironmentOutcome(EnvironmentOutcomeCategory.RECOVERABLE_FAILURE, EnvironmentOutcomeReason.TOOL_TRANSIENT_FAILURE),))
        self.assertEqual(
            self._controller(recoverable_environment, _AlwaysToolPolicy(), CognitiveExecutionBudget(3, max_recoverable_failures=1)).run(self.task).termination_reason,
            CognitiveExecutionTerminationReason.BUDGET_EXHAUSTED,
        )

    def test_policy_and_environment_exceptions_are_bounded_without_private_detail(self):
        policy_result = self._controller(_ScriptedEnvironment(()), _RaisesPolicy(), CognitiveExecutionBudget(1)).run(self.task)
        self.assertEqual(policy_result.termination_reason, CognitiveExecutionTerminationReason.POLICY_FAILURE)
        class BrokenEnvironment:
            def apply(self, action): raise RuntimeError("private stack detail")
        environment_result = self._controller(BrokenEnvironment(), _AlwaysToolPolicy(), CognitiveExecutionBudget(1)).run(self.task)
        self.assertEqual(environment_result.termination_reason, CognitiveExecutionTerminationReason.ENVIRONMENT_FAILURE)
        self.assertNotIn("private", str(environment_result.to_dict()))

    def test_budget_and_result_are_immutable_serializable_and_controller_has_no_provider_or_evaluator(self):
        budget = CognitiveExecutionBudget(2)
        self.assertEqual(CognitiveExecutionBudget.from_dict(budget.to_dict()), budget)
        result = CognitiveExecutionResult(CognitiveExecutionTerminationReason.ANSWER_SUBMITTED, 1, 0, 0, 0, {"answer": [1]})
        self.assertEqual(CognitiveExecutionResult.from_dict(result.to_dict()), result)
        with self.assertRaises(AttributeError): result.answer["answer"].append(2)
        source = inspect.getsource(CognitiveExecutionController)
        self.assertNotIn("CompletionEvaluator", source)
        self.assertNotIn("LLMProvider", source)
        self.assertNotIn("expected_answer", source)


if __name__ == "__main__":
    unittest.main()
