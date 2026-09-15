"""Synthetic fidelity tests for M18 ReAct's public action-observation loop."""

from __future__ import annotations

import unittest

from src.core.task import Goal, Task
from src.core.tool import CapabilityDescriptor
from src.evaluation.contracts import EvaluationCase, EvaluationFeedback, EvaluationFeedbackType
from src.evaluation.execution import AgentStepInput, EvaluationBudget, EvaluationBudgetState
from src.evaluation.m18_react import M18ReActBaseline, M18ReActConditionError, M18ReActTerminationReason, m18_react_artifacts


class FakeReActProvider:
    def __init__(self, outputs): self.outputs, self.requests = list(outputs), []
    def generate(self, request): self.requests.append(request); return self.outputs.pop(0)


def _keys(value):
    if isinstance(value, dict): return set(value) | set().union(*(_keys(item) for item in value.values()))
    if isinstance(value, list): return set().union(*(_keys(item) for item in value)) if value else set()
    return set()


class M18ReActTests(unittest.TestCase):
    def setUp(self):
        self.case = EvaluationCase("m18.react.synthetic", Task(Goal("complete", ("answer",)), {"value": 4, "expected_answer": "private"}, metadata={"difficulty": "private"}))
        self.tools = (CapabilityDescriptor("first", "First", "distractor", {"type": "object"}), CapabilityDescriptor("transform", "Transform", "use public output", {"type": "object"}))
    def step(self, feedback, used=0): return AgentStepInput(self.case, feedback, EvaluationBudgetState(EvaluationBudget(5, 3), steps_used=used))

    def test_multistep_history_is_ordered_public_and_supports_composition(self):
        provider = FakeReActProvider([
            '{"action":"tool_call","tool_name":"first","parameters":{"value":4}}',
            '{"action":"tool_call","tool_name":"transform","parameters":{"value":8}}',
            '{"action":"answer","answer":16}',
        ])
        react = M18ReActBaseline(provider, self.tools)
        react.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
        react.step(self.step(EvaluationFeedback(EvaluationFeedbackType.TOOL_RESPONSE, {"output": 8}), 1))
        final = react.step(self.step(EvaluationFeedback(EvaluationFeedbackType.TOOL_RESPONSE, {"output": 16}), 2))
        self.assertEqual(final.action.to_dict()["payload"], {"answer": 16})
        self.assertEqual(len(react.interaction_history), 2)
        request = provider.requests[2].to_dict()
        self.assertEqual([x["action"]["payload"]["tool_name"] for x in request["interaction_history"]], ["first", "transform"])
        self.assertEqual(request["interaction_history"][1]["feedback"]["payload"], {"output": 16})
        self.assertEqual(react.logical_provider_calls, 3)

    def test_recoverable_and_invalid_feedback_append_public_history_then_allow_next_action(self):
        provider = FakeReActProvider(['{"action":"tool_call","tool_name":"first","parameters":{}}', '{"action":"tool_call","tool_name":"transform","parameters":{"value":4}}', '{"action":"answer","answer":"ok"}'])
        react = M18ReActBaseline(provider, self.tools)
        react.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
        react.step(self.step(EvaluationFeedback(EvaluationFeedbackType.TOOL_FAILURE, {"category":"recoverable_failure", "correct_tool":"private"}), 1))
        react.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INVALID_ACTION, {"reason":"invalid", "correct_action":"private"}), 2))
        self.assertEqual(react.recovery_feedbacks, 1); self.assertEqual(react.invalid_action_feedbacks, 1)
        self.assertEqual(len(react.interaction_history), 2)
        self.assertNotIn("correct_tool", _keys(provider.requests[1].to_dict()))
        self.assertNotIn("correct_action", _keys(provider.requests[2].to_dict()))

    def test_unrecoverable_and_budget_do_not_make_provider_calls(self):
        provider = FakeReActProvider([]); react = M18ReActBaseline(provider, self.tools)
        dead = self.step(EvaluationFeedback(EvaluationFeedbackType.TOOL_FAILURE, {"category":"unrecoverable_failure"}))
        self.assertEqual(react.termination_for(dead), M18ReActTerminationReason.UNRECOVERABLE_ENVIRONMENT_FAILURE)
        self.assertTrue(react.step(dead).request_termination)
        exhausted = self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT), 5)
        self.assertEqual(react.termination_for(exhausted), M18ReActTerminationReason.BUDGET_EXHAUSTED)
        self.assertEqual(react.logical_provider_calls, 0)

    def test_strict_malformed_output_has_one_call_no_retry(self):
        for raw in ('not json', 'text {"action":"answer","answer":"x"}', '{"action":"plan","steps":[]}', '{"action":"answer","answer":"x","thought":"no"}'):
            with self.subTest(raw=raw):
                provider = FakeReActProvider([raw]); react = M18ReActBaseline(provider, self.tools)
                with self.assertRaises(M18ReActConditionError): react.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
                self.assertEqual(react.logical_provider_calls, 1); self.assertEqual(len(provider.requests), 1)

    def test_public_history_is_only_cross_decision_state_and_not_a_plan(self):
        provider = FakeReActProvider(['{"action":"tool_call","tool_name":"transform","parameters":{}}', '{"action":"answer","answer":"ok"}'])
        react = M18ReActBaseline(provider, self.tools)
        react.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT, {"ground_truth":"private"})))
        react.step(self.step(EvaluationFeedback(EvaluationFeedbackType.TOOL_RESPONSE, {"output":"ok"}), 1))
        request = provider.requests[1].to_dict()
        self.assertEqual(len(request["interaction_history"]), 1)
        self.assertNotIn("ground_truth", _keys(request))
        self.assertFalse({"_plan", "_planner", "_replanner", "_runtime_state", "_provider_history", "_scratchpad"} & set(vars(react)))

    def test_artifacts_are_deterministic(self):
        self.assertEqual(m18_react_artifacts(), m18_react_artifacts())
        self.assertTrue(all(len(value) == 64 for value in m18_react_artifacts().to_dict().values()))


if __name__ == "__main__": unittest.main()
