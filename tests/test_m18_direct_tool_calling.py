"""Synthetic fidelity tests for the M18 stateless Direct baseline."""

from __future__ import annotations

import unittest

from src.core.task import Goal, Task
from src.core.tool import CapabilityDescriptor
from src.evaluation.contracts import EvaluationCase, EvaluationFeedback, EvaluationFeedbackType
from src.evaluation.execution import AgentStepInput, EvaluationBudget, EvaluationBudgetState
from src.evaluation.m18_direct_tool_calling import (
    M18DirectConditionError,
    M18DirectTerminationReason,
    M18DirectToolCallingBaseline,
    m18_direct_artifacts,
)


class FakeDirectProvider:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return self.outputs.pop(0)


def _keys(value):
    if isinstance(value, dict): return set(value) | set().union(*(_keys(item) for item in value.values()))
    if isinstance(value, list): return set().union(*(_keys(item) for item in value)) if value else set()
    return set()


class M18DirectToolCallingTest(unittest.TestCase):
    def setUp(self) -> None:
        task = Task(
            Goal("complete public task", ("submit output",)),
            {"value": 9, "expected_answer": "private", "nested": {"ground_truth": "private"}},
            metadata={"difficulty": "private", "evaluator_success": True},
        )
        self.case = EvaluationCase("m18.synthetic.001", task)
        self.capabilities = (
            CapabilityDescriptor("first", "First", "distractor", {"type": "object"}),
            CapabilityDescriptor("transform", "Transform", "use public value", {"type": "object", "properties": {"value": {"type": "integer"}}}),
        )

    def step(self, feedback: EvaluationFeedback, used: int = 0) -> AgentStepInput:
        return AgentStepInput(self.case, feedback, EvaluationBudgetState(EvaluationBudget(4, 3), steps_used=used))

    def test_direct_answer_and_non_first_tool_are_decoded(self) -> None:
        provider = FakeDirectProvider(['{"action":"answer","answer":10}', '{"action":"tool_call","tool_name":"transform","parameters":{"value":9}}'])
        direct = M18DirectToolCallingBaseline(provider, self.capabilities)
        self.assertEqual(direct.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT))).action.to_dict()["action_type"], "answer")
        result = direct.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
        self.assertEqual(result.action.to_dict()["payload"], {"tool_name": "transform", "parameters": {"value": 9}})
        self.assertFalse(result.request_termination)

    def test_subsequent_decision_uses_only_current_public_feedback_and_parameter(self) -> None:
        provider = FakeDirectProvider(['{"action":"tool_call","tool_name":"transform","parameters":{"value":9}}', '{"action":"answer","answer":18}'])
        direct = M18DirectToolCallingBaseline(provider, self.capabilities)
        direct.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
        direct.step(self.step(EvaluationFeedback(EvaluationFeedbackType.TOOL_RESPONSE, {"output": 18, "ground_truth": "private"}), used=1))
        first, second = (request.to_dict() for request in provider.requests)
        self.assertEqual(second["current_feedback"], {"feedback_type": "tool_response", "payload": {"output": 18}})
        self.assertNotIn("history", second)
        self.assertNotIn("plan", second)
        self.assertEqual([item["tool_id"] for item in first["capabilities"]], ["first", "transform"])
        self.assertEqual(direct.logical_provider_calls, 2)
        self.assertEqual(direct.tool_calls, 1)

    def test_recoverable_and_invalid_feedback_allow_fresh_provider_decisions(self) -> None:
        provider = FakeDirectProvider(['{"action":"tool_call","tool_name":"transform","parameters":{}}', '{"action":"tool_call","tool_name":"transform","parameters":{"value":9}}'])
        direct = M18DirectToolCallingBaseline(provider, self.capabilities)
        recoverable = EvaluationFeedback(EvaluationFeedbackType.TOOL_FAILURE, {"category": "recoverable_failure", "correct_tool": "private"})
        invalid = EvaluationFeedback(EvaluationFeedbackType.INVALID_ACTION, {"reason": "invalid_arguments", "correct_action": "private"})
        direct.step(self.step(recoverable))
        direct.step(self.step(invalid, used=1))
        self.assertEqual(direct.recovery_feedbacks, 1)
        self.assertEqual(direct.invalid_action_feedbacks, 1)
        self.assertEqual(direct.logical_provider_calls, 2)
        self.assertNotIn("correct_tool", _keys(provider.requests[0].to_dict()))
        self.assertNotIn("correct_action", _keys(provider.requests[1].to_dict()))

    def test_unrecoverable_and_budget_are_termination_compatible_without_a_call(self) -> None:
        provider = FakeDirectProvider([])
        direct = M18DirectToolCallingBaseline(provider, self.capabilities)
        unrecoverable = self.step(EvaluationFeedback(EvaluationFeedbackType.TOOL_FAILURE, {"category": "unrecoverable_failure"}))
        self.assertEqual(direct.termination_for(unrecoverable), M18DirectTerminationReason.UNRECOVERABLE_ENVIRONMENT_FAILURE)
        self.assertTrue(direct.step(unrecoverable).request_termination)
        exhausted = self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT), used=4)
        self.assertEqual(direct.termination_for(exhausted), M18DirectTerminationReason.BUDGET_EXHAUSTED)
        self.assertEqual(direct.logical_provider_calls, 0)

    def test_malformed_output_has_one_call_and_no_repair_or_fallback(self) -> None:
        bad = ('not json', 'text {"action":"answer","answer":"x"}', '{"action":"other"}', '{"action":"answer","answer":"x","rationale":"bad"}', '{"action":"tool_call","tool_name":"transform","parameters":[]}')
        for output in bad:
            with self.subTest(output=output):
                provider = FakeDirectProvider([output])
                direct = M18DirectToolCallingBaseline(provider, self.capabilities)
                with self.assertRaises(M18DirectConditionError): direct.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
                self.assertEqual(direct.logical_provider_calls, 1)
                self.assertEqual(len(provider.requests), 1)

    def test_truth_firewall_and_no_mind_or_react_state(self) -> None:
        provider = FakeDirectProvider(['{"action":"answer","answer":10}'])
        direct = M18DirectToolCallingBaseline(provider, self.capabilities)
        direct.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT, {"difficulty": "private", "visible": True})))
        request = provider.requests[0].to_dict()
        forbidden = {"expected_answer", "ground_truth", "correct_tool", "correct_action", "difficulty", "evaluator_success", "private_judge_metadata"}
        self.assertFalse(forbidden & _keys(request))
        names = set(vars(direct))
        self.assertFalse({"_history", "_plan", "_scratchpad", "_runtime_state", "_belief"} & names)

    def test_artifact_identities_are_deterministic(self) -> None:
        first, second = m18_direct_artifacts(), m18_direct_artifacts()
        self.assertEqual(first, second)
        self.assertTrue(all(len(value) == 64 for value in first.to_dict().values()))


if __name__ == "__main__": unittest.main()
