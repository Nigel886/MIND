"""Contract tests for the M17 observation-conditioned policy boundary."""

from __future__ import annotations

import unittest

from src.core.cognitive_session import CognitiveAgentSession
from src.core.goal_policy import GoalAwarePolicyEngine
from src.core.observation import Observation
from src.core.policy import Policy
from src.core.policy_context import (
    PolicyDecisionContext,
    PolicyObservationView,
    PolicyRuntimeView,
    PolicyTaskContext,
)
from src.core.runtime import RuntimeController
from src.core.task import Goal, Task
from src.core.tool import CapabilityDescriptor


def _keys(value):
    if isinstance(value, dict):
        return set(value) | set().union(*(_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_keys(item) for item in value)) if value else set()
    return set()


class ObservationPolicy:
    """A deterministic local policy used only to prove the public contract."""

    def __init__(self) -> None:
        self.contexts: list[PolicyDecisionContext] = []
        self.tool_calls = 0

    def decide(self, context: PolicyDecisionContext) -> Policy:
        self.contexts.append(context)
        if context.latest_observation is None:
            return Policy(
                "call_tool",
                {"tool_name": "public_echo", "tool_parameters": {"value": "initial"}},
                {},
            )
        value = context.latest_observation.content["value"]
        if value == "answer":
            return Policy("produce_answer", {"answer": value}, {})
        return Policy(
            "call_tool",
            {"tool_name": "public_echo", "tool_parameters": {"value": value}},
            {},
        )


class ObservationConditionedPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.goal = Goal("return public output", ("produce a public response",))
        self.task = Task(
            self.goal,
            {
                "request": "echo",
                "nested": {"visible": 1, "expected_answer": "secret"},
                "expected_answer": "secret",
                "correct_tool": "calculator",
            },
            metadata={"evaluator_success": True},
        )
        self.state = RuntimeController.initialize(
            metadata={"private_judge_metadata": {"secret": True}},
        )
        self.capabilities = (
            CapabilityDescriptor("public_echo", "Echo", "Return public input", {"type": "object"}),
            CapabilityDescriptor("other_tool"),
        )

    def _context(self, observation: Observation | None = None) -> PolicyDecisionContext:
        return PolicyDecisionContext.from_runtime(
            self.task,
            self.state,
            observation,
            self.capabilities,
        )

    def test_context_is_immutable_and_projects_only_public_task_and_state(self) -> None:
        context = self._context()
        self.assertIsInstance(context.task, PolicyTaskContext)
        self.assertIsInstance(context.runtime, PolicyRuntimeView)
        self.assertFalse(hasattr(context, "runtime_state"))
        self.assertEqual(context.task.public_input["request"], "echo")
        self.assertNotIn("expected_answer", _keys(context.to_dict()))
        self.assertNotIn("correct_tool", _keys(context.to_dict()))
        self.assertNotIn("evaluator_success", _keys(context.to_dict()))
        self.assertNotIn("private_judge_metadata", _keys(context.to_dict()))
        self.assertEqual(context.runtime.to_dict(), {"belief_version": 0, "belief_record_count": 0})
        with self.assertRaises(TypeError):
            context.task.public_input["request"] = "changed"
        with self.assertRaises(AttributeError):
            context.runtime.belief_version = 3
        self.assertEqual(self.task.to_dict()["input"]["request"], "echo")
        self.assertEqual(self.state.metadata["private_judge_metadata"]["secret"], True)

    def test_latest_public_observation_is_sanitized_and_optional(self) -> None:
        self.assertIsNone(self._context().latest_observation)
        observation = Observation(
            source="agent_environment",
            content={"value": "ok", "nested": {"ground_truth": "secret", "visible": True}},
        )
        context = self._context(observation)
        self.assertIsInstance(context.latest_observation, PolicyObservationView)
        self.assertEqual(context.latest_observation.content["value"], "ok")
        self.assertNotIn("ground_truth", _keys(context.to_dict()))
        with self.assertRaises(TypeError):
            context.latest_observation.content["value"] = "changed"
        self.assertEqual(observation.content["value"], "ok")
        with self.assertRaises(ValueError):
            self._context(Observation(source="task", content={"value": "not public feedback"}))

    def test_capabilities_are_ordered_immutable_and_have_no_truth_labels(self) -> None:
        context = self._context()
        self.assertEqual([item.tool_id for item in context.capabilities], ["public_echo", "other_tool"])
        self.assertIsInstance(context.capabilities, tuple)
        with self.assertRaises(AttributeError):
            context.capabilities[0].tool_id = "changed"
        self.assertNotIn("correct_tool", _keys(context.to_dict()))
        self.assertNotIn("correct_action", _keys(context.to_dict()))

    def test_same_public_context_with_different_observations_produces_different_actions(self) -> None:
        policy = ObservationPolicy()
        one = self._context(Observation(source="agent_environment", content={"value": "one"}))
        two = self._context(Observation(source="agent_environment", content={"value": "answer"}))
        self.assertEqual(policy.decide(one).parameters["tool_parameters"], {"value": "one"})
        self.assertEqual(policy.decide(two).to_dict(), {
            "action": "produce_answer", "parameters": {"answer": "answer"}, "metadata": {},
        })

    def test_session_opt_in_policy_uses_observation_and_non_calculator_capability(self) -> None:
        policy = ObservationPolicy()
        session = CognitiveAgentSession(
            2,
            policy_engine=policy,
            capabilities=self.capabilities,
        )
        session.start(self.task)
        first = session.step()
        self.assertEqual(first.action_request.to_dict(), {
            "action": "tool_call", "parameters": {"tool_name": "public_echo", "parameters": {"value": "initial"}},
        })
        session.observe(Observation(source="agent_environment", content={"value": "answer"}))
        second = session.step()
        self.assertEqual(second.action_request.to_dict(), {
            "action": "answer", "parameters": {"answer": "answer"},
        })
        self.assertEqual(policy.tool_calls, 0)
        self.assertEqual(len(policy.contexts), 2)
        self.assertIsNone(policy.contexts[0].latest_observation)
        self.assertEqual(policy.contexts[1].latest_observation.content["value"], "answer")

    def test_goal_aware_context_adapter_preserves_direct_and_calculator_semantics(self) -> None:
        direct = Task(self.goal, {"value": "ready", "expected_answer": "ready"})
        calculator = Task(self.goal, {"operation": "multiply", "operands": [2, 3], "expected_answer": 6})
        state = RuntimeController.initialize()
        self.assertEqual(
            GoalAwarePolicyEngine.decide(PolicyDecisionContext.from_runtime(direct, state)).to_dict(),
            GoalAwarePolicyEngine.generate(direct, state).to_dict(),
        )
        self.assertEqual(
            GoalAwarePolicyEngine.decide(PolicyDecisionContext.from_runtime(calculator, state)).to_dict(),
            GoalAwarePolicyEngine.generate(calculator, state).to_dict(),
        )


if __name__ == "__main__":
    unittest.main()
