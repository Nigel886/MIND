"""Synthetic contract tests for the M18 evaluation-side policy condition."""

from __future__ import annotations

import json
import unittest

from src.core.environment_outcome import EnvironmentOutcome, EnvironmentOutcomeCategory, EnvironmentOutcomeReason
from src.core.observation import Observation
from src.core.policy_context import PolicyDecisionContext
from src.core.runtime import RuntimeController
from src.core.task import Goal, Task
from src.core.tool import CapabilityDescriptor
from src.evaluation.m18_mind_policy_condition import (
    M18MINDPolicyCondition,
    M18PolicyConditionError,
    M18_POLICY_PROMPT,
    decode_m18_policy_response,
    m18_policy_artifacts,
)


class FakePolicyProvider:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return self.responses.pop(0)


def _keys(value):
    if isinstance(value, dict):
        return set(value) | set().union(*(_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_keys(item) for item in value)) if value else set()
    return set()


class M18MINDPolicyConditionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.task = Task(
            Goal("produce public output", ("return an answer",)),
            {
                "value": 7,
                "expected_answer": "private",
                "nested": {"visible": True, "ground_truth": "private"},
            },
            metadata={"difficulty": "private", "evaluator_success": True},
        )
        self.state = RuntimeController.initialize(metadata={"private_judge_metadata": {"secret": True}})
        self.capabilities = (
            CapabilityDescriptor("first_tool", "First", "First public tool", {"type": "object"}),
            CapabilityDescriptor(
                "transform",
                "Transform",
                "Transform a public value",
                {"type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"]},
            ),
        )

    def context(self, observation: Observation | None = None) -> PolicyDecisionContext:
        return PolicyDecisionContext.from_runtime(self.task, self.state, observation, self.capabilities)

    def test_answer_and_general_non_first_tool_decode(self) -> None:
        provider = FakePolicyProvider([
            '{"action":"answer","answer":"done"}',
            '{"action":"tool_call","tool_name":"transform","parameters":{"value":7}}',
        ])
        condition = M18MINDPolicyCondition(provider)
        self.assertEqual(condition.decide(self.context()).to_dict(), {"action": "produce_answer", "parameters": {"answer": "done"}, "metadata": {}})
        self.assertEqual(
            condition.decide(self.context()).to_dict(),
            {"action": "call_tool", "parameters": {"tool_name": "transform", "tool_parameters": {"value": 7}}, "metadata": {}},
        )
        self.assertEqual(condition.logical_provider_calls, 2)

    def test_public_observation_and_derived_parameter_reach_one_request(self) -> None:
        observation = Observation(source="agent_environment", content={"value": 11, "ground_truth": "private"})
        provider = FakePolicyProvider(['{"action":"tool_call","tool_name":"transform","parameters":{"value":11}}'])
        condition = M18MINDPolicyCondition(provider)
        policy = condition.decide(self.context(observation))
        request = provider.requests[0].to_dict()
        self.assertEqual(request["public_context"]["latest_observation"]["content"], {"value": 11})
        self.assertEqual(request["public_context"]["capabilities"][1]["tool_id"], "transform")
        self.assertEqual(policy.parameters["tool_parameters"], {"value": 11})
        self.assertEqual(request["prompt"], M18_POLICY_PROMPT)

    def test_recovery_and_invalid_action_outcomes_are_publicly_visible(self) -> None:
        for category, reason in (
            (EnvironmentOutcomeCategory.RECOVERABLE_FAILURE, EnvironmentOutcomeReason.TOOL_TRANSIENT_FAILURE),
            (EnvironmentOutcomeCategory.INVALID_ACTION, EnvironmentOutcomeReason.INVALID_ARGUMENTS),
        ):
            with self.subTest(category=category):
                observation = EnvironmentOutcome(category, reason, {"tool_name": "transform"}).to_observation()
                provider = FakePolicyProvider(['{"action":"answer","answer":"next"}'])
                M18MINDPolicyCondition(provider).decide(self.context(observation))
                outcome = provider.requests[0].to_dict()["public_context"]["latest_observation"]["content"]["environment_outcome"]
                self.assertEqual(outcome["category"], category.value)
                self.assertEqual(outcome["reason"], reason.value)

    def test_truth_firewall_applies_at_provider_boundary(self) -> None:
        provider = FakePolicyProvider(['{"action":"answer","answer":"ok"}'])
        M18MINDPolicyCondition(provider).decide(
            self.context(Observation(source="agent_environment", content={"correct_tool": "transform", "visible": "yes"})),
        )
        request = provider.requests[0].to_dict()
        forbidden = {"expected_answer", "ground_truth", "difficulty", "correct_tool", "correct_action", "evaluator_success", "private_judge_metadata"}
        self.assertFalse(forbidden & _keys(request))
        self.assertEqual(request["public_context"]["latest_observation"]["content"], {"visible": "yes"})

    def test_malformed_responses_are_rejected_with_one_call_and_no_fallback(self) -> None:
        malformed = (
            "not json",
            'prose {"action":"answer","answer":"x"}',
            '{"action":"unknown","answer":"x"}',
            '{"action":"answer"}',
            '{"action":"answer","answer":"x","plan":"hidden"}',
            '{"action":"tool_call","tool_name":"transform","parameters":[]}',
            '{"action":"answer","answer":"x","rationale":"no"}',
        )
        for raw in malformed:
            with self.subTest(raw=raw):
                provider = FakePolicyProvider([raw])
                condition = M18MINDPolicyCondition(provider)
                with self.assertRaises(M18PolicyConditionError):
                    condition.decide(self.context())
                self.assertEqual(condition.logical_provider_calls, 1)
                self.assertEqual(len(provider.requests), 1)

    def test_repeated_invocations_are_stateless_and_context_bound(self) -> None:
        provider = FakePolicyProvider(['{"action":"answer","answer":"first"}', '{"action":"answer","answer":"second"}'])
        condition = M18MINDPolicyCondition(provider)
        condition.decide(self.context(Observation(source="agent_environment", content={"value": "A"})))
        condition.decide(self.context(Observation(source="agent_environment", content={"value": "B"})))
        first, second = (item.to_dict() for item in provider.requests)
        self.assertEqual(first["public_context"]["latest_observation"]["content"], {"value": "A"})
        self.assertEqual(second["public_context"]["latest_observation"]["content"], {"value": "B"})
        self.assertNotIn("history", second)
        self.assertNotIn("plan", second)
        self.assertEqual(condition.logical_provider_calls, 2)

    def test_decoder_rejects_duplicate_and_non_json_values(self) -> None:
        for raw in ('{"action":"answer","answer":"x","answer":"y"}', '{"action":"answer","answer":NaN}'):
            with self.subTest(raw=raw), self.assertRaises(M18PolicyConditionError):
                decode_m18_policy_response(raw)

    def test_artifacts_are_deterministic_and_do_not_bind_a_provider(self) -> None:
        first, second = m18_policy_artifacts(), m18_policy_artifacts()
        self.assertEqual(first, second)
        values = first.to_dict()
        self.assertTrue(all(len(value) == 64 for key, value in values.items() if key.endswith("_hash")))
        self.assertNotIn("provider_configuration", values)


if __name__ == "__main__":
    unittest.main()
