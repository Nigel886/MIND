"""Tests for M15 controlled observation-aware cognitive sessions."""

from __future__ import annotations

import inspect
import unittest

from src.core.agent import GoalDirectedAgent
from src.core.cognitive_session import (
    CognitiveActionRequest,
    CognitiveAgentSession,
    CognitiveSessionPhase,
    CognitiveSessionStepResult,
    CognitiveSessionTerminationReason,
)
from src.core.inference_registry import InferenceStrategyRegistry
from src.core.meta_engine import MetaInferenceEngine
from src.core.observation import Observation
from src.core.task import Goal, Task
from src.core.tool import ToolRegistry
from src.integration.meta_inference_adapter import IntegrationSelected
from src.core.meta_inference import DecisionEvidence, MetaInferenceDecision, MetaInferenceDecisionStatus
from src.tools.calculator import CalculatorTool


class CognitiveAgentSessionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.goal = Goal("complete task", ("return expected answer",))

    def _tool_task(self, expected: int = 5) -> Task:
        return Task(
            self.goal,
            {"operation": "add", "operands": [2, 3], "expected_answer": expected},
        )

    @staticmethod
    def _feedback(content: dict) -> Observation:
        return Observation(source="agent_environment", content=content)

    def test_lifecycle_rejects_step_before_start_and_duplicate_start(self) -> None:
        session = CognitiveAgentSession(2)
        with self.assertRaises(RuntimeError):
            session.step()
        with self.assertRaises(RuntimeError):
            session.observe(self._feedback({"status": "completed", "output": 5}))
        session.start(self._tool_task())
        with self.assertRaises(RuntimeError):
            session.start(self._tool_task())

    def test_first_step_projects_tool_request_without_execution(self) -> None:
        session = CognitiveAgentSession(2)
        session.start(self._tool_task())

        result = session.step()

        self.assertIsInstance(result, CognitiveSessionStepResult)
        self.assertEqual(result.phase, CognitiveSessionPhase.AWAITING_OBSERVATION)
        self.assertEqual(result.action_request.to_dict(), {
            "action": "tool_call",
            "parameters": {"tool_name": "calculator", "parameters": {"operation": "add", "operands": [2, 3]}},
        })
        self.assertEqual(session.cycles_completed, 1)
        self.assertFalse(hasattr(session, "runtime_state"))
        self.assertFalse(hasattr(session, "belief"))
        self.assertNotIn("ToolRegistry", inspect.getsource(CognitiveAgentSession))

    def test_multiple_cycles_use_observation_and_stop_at_max_cycles(self) -> None:
        session = CognitiveAgentSession(2)
        session.start(self._tool_task(expected=10))
        first = session.step()
        session.observe(self._feedback({"status": "completed", "output": 5}))
        second = session.step()
        session.observe(self._feedback({"status": "completed", "output": 5}))
        terminal = session.step()

        self.assertEqual(first.action_request.action, "tool_call")
        self.assertEqual(second.action_request.action, "tool_call")
        self.assertEqual(session.cycles_completed, 2)
        self.assertEqual(terminal.termination_reason, CognitiveSessionTerminationReason.MAX_CYCLES_REACHED)

    def test_feedback_completion_terminates_on_later_step(self) -> None:
        session = CognitiveAgentSession(3)
        session.start(self._tool_task())
        session.step()
        session.observe(self._feedback({"status": "completed", "output": 5}))

        terminal = session.step()

        self.assertEqual(terminal.phase, CognitiveSessionPhase.TERMINATED)
        self.assertEqual(terminal.termination_reason, CognitiveSessionTerminationReason.COMPLETED)
        self.assertEqual(terminal.answer, 5)

    def test_answer_policy_crosses_same_external_feedback_boundary(self) -> None:
        task = Task(self.goal, {"value": "ready", "expected_answer": "ready"})
        session = CognitiveAgentSession(1)
        session.start(task)
        action = session.step()
        self.assertEqual(action.action_request.to_dict(), {"action": "answer", "parameters": {"answer": "ready"}})
        session.observe(self._feedback({"status": "completed", "output": "ready"}))
        self.assertEqual(session.step().termination_reason, CognitiveSessionTerminationReason.COMPLETED)

    def test_failure_timeout_user_stop_and_terminal_lifecycle_errors(self) -> None:
        failed = CognitiveAgentSession(2); failed.start(self._tool_task()); failed.step()
        failed.observe(self._feedback({"status": "failed", "failure_category": "tool_failure"}))
        self.assertEqual(failed.step().termination_reason, CognitiveSessionTerminationReason.FAILED)

        timeout = CognitiveAgentSession(2); timeout.start(self._tool_task())
        self.assertEqual(timeout.terminate(CognitiveSessionTerminationReason.TIMEOUT).termination_reason, CognitiveSessionTerminationReason.TIMEOUT)
        self.assertEqual(timeout.terminate(CognitiveSessionTerminationReason.USER_STOPPED).termination_reason, CognitiveSessionTerminationReason.TIMEOUT)
        with self.assertRaises(RuntimeError): timeout.step()
        with self.assertRaises(RuntimeError): timeout.observe(self._feedback({}))

        stopped = CognitiveAgentSession(2); stopped.start(self._tool_task())
        self.assertEqual(stopped.terminate(CognitiveSessionTerminationReason.USER_STOPPED).termination_reason, CognitiveSessionTerminationReason.USER_STOPPED)

    def test_invalid_observations_and_transition_order_are_rejected(self) -> None:
        session = CognitiveAgentSession(2); session.start(self._tool_task())
        with self.assertRaises(RuntimeError):
            session.observe(self._feedback({}))
        session.step()
        with self.assertRaises(RuntimeError):
            session.step()
        with self.assertRaises(ValueError):
            session.observe(Observation(source="tool:calculator", content={}))
        with self.assertRaises(ValueError):
            session.observe(self._feedback({"chain_of_thought": "secret"}))
        with self.assertRaises(TypeError):
            session.observe(self._feedback({"output": object()}))

    def test_public_contracts_are_immutable_and_serializable(self) -> None:
        request = CognitiveActionRequest("tool_call", {"tool_name": "calculator", "parameters": {"operands": [1, 2]}})
        serialized = request.to_dict()
        serialized["parameters"]["parameters"]["operands"].append(3)
        self.assertEqual(request.to_dict()["parameters"]["parameters"]["operands"], [1, 2])
        self.assertEqual(CognitiveActionRequest.from_dict(request.to_dict()), request)

        session = CognitiveAgentSession(1); session.start(self._tool_task()); result = session.step()
        self.assertEqual(CognitiveSessionStepResult.from_dict(result.to_dict()), result)
        with self.assertRaises(TypeError):
            result.action_request.parameters["tool_name"] = "other"
        self.assertNotIn("RuntimeState", repr(result))
        self.assertNotIn("Belief", repr(result))

    def test_meta_inference_engine_and_integration_context_paths(self) -> None:
        engine = MetaInferenceEngine(InferenceStrategyRegistry())
        task = Task(self.goal, {"value": "ready", "expected_answer": "ready"}, metadata={"required_inference_capabilities": ("calculator",)})
        session = CognitiveAgentSession(1, meta_inference_engine=engine)
        session.start(task)
        self.assertEqual(session.step().termination_reason, CognitiveSessionTerminationReason.FAILED)
        with self.assertRaises(RuntimeError): session.step()

        decision = MetaInferenceDecision(
            MetaInferenceDecisionStatus.SELECTED,
            "calculator_strategy",
            (DecisionEvidence("capability_match", "selected", {}),),
        )
        context = IntegrationSelected(decision, {})
        context_session = CognitiveAgentSession(1)
        context_session.start(Task(self.goal, {"value": "ready", "expected_answer": "ready"}), validated_context=context)
        self.assertEqual(context_session.step().action_request.action, "answer")
        with self.assertRaises(ValueError):
            CognitiveAgentSession(1, meta_inference_engine=engine).start(task, validated_context=context)

    def test_equivalent_fresh_sessions_are_deterministic_and_agent_run_is_unchanged(self) -> None:
        task = self._tool_task()
        first = CognitiveAgentSession(2); first.start(task); first_action = first.step().to_dict()
        second = CognitiveAgentSession(2); second.start(task); second_action = second.step().to_dict()
        self.assertEqual(first_action, second_action)

        registry = ToolRegistry(); registry.register(CalculatorTool())
        result = GoalDirectedAgent(registry).run(task, 1)
        self.assertEqual(result.answer, 5)
        self.assertEqual(result.cycles_completed, 1)

    def test_constructor_validation(self) -> None:
        with self.assertRaises(TypeError): CognitiveAgentSession(True)
        with self.assertRaises(ValueError): CognitiveAgentSession(-1)
        zero = CognitiveAgentSession(0); zero.start(self._tool_task())
        self.assertEqual(zero.step().termination_reason, CognitiveSessionTerminationReason.MAX_CYCLES_REACHED)


if __name__ == "__main__":
    unittest.main()
