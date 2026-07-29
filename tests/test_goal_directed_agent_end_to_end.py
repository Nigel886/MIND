"""End-to-end validation for the bounded M8 Goal-Directed Agent."""

from __future__ import annotations

from copy import deepcopy
import unittest

from src.core.agent import GoalDirectedAgent
from src.core.result import AgentResult, AgentStatus, TerminationReason
from src.core.task import Goal, Task
from src.core.tool import ToolRegistry, ToolResult
from src.tools.calculator import CalculatorTool


class _FailingCalculator:
    """A controlled public Tool seam for the Agent failure boundary."""

    name = "calculator"

    def execute(self, parameters: dict[str, object]) -> ToolResult:
        return ToolResult(
            tool_name=self.name,
            success=False,
            output=None,
            error="controlled failure",
            parameters=parameters,
        )


class GoalDirectedAgentEndToEndTest(unittest.TestCase):
    """Validate public M8 behavior across the complete task-level flow."""

    def setUp(self) -> None:
        self.goal = Goal(
            "return the requested deterministic result",
            ("candidate answer equals expected answer",),
        )

    def _agent_with_calculator(self) -> GoalDirectedAgent:
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        return GoalDirectedAgent(registry)

    def _direct_task(self, value: str, expected_answer: str) -> Task:
        return Task(self.goal, {"value": value, "expected_answer": expected_answer})

    def _calculator_task(self, expected_answer: int) -> Task:
        return Task(
            self.goal,
            {
                "operation": "multiply",
                "operands": [17, 23],
                "expected_answer": expected_answer,
            },
        )

    def test_direct_completion_is_deterministic_and_does_not_need_a_tool(self) -> None:
        task = self._direct_task("ready", "ready")
        task_snapshot = task.to_dict()
        goal_snapshot = self.goal.to_dict()
        agent = GoalDirectedAgent(ToolRegistry())

        first = agent.run(task, max_cycles=2)
        second = agent.run(task, max_cycles=2)

        for result in (first, second):
            self.assertEqual(result.status, AgentStatus.COMPLETED)
            self.assertEqual(result.termination_reason, TerminationReason.GOAL_SATISFIED)
            self.assertEqual(result.answer, "ready")
            self.assertEqual(result.cycles_completed, 1)
            self.assertIsNotNone(result.final_state)
            self.assertNotEqual(result.answer, result.final_state)
            self.assertEqual(result.evidence[0]["type"], "policy")
            self.assertEqual(result.evidence[0]["action"], "produce_answer")
            self.assertEqual(result.evidence[1], {"type": "completion", "satisfied": True})

        self.assertEqual(first.to_dict()["answer"], second.to_dict()["answer"])
        self.assertEqual(first.status, second.status)
        self.assertEqual(first.termination_reason, second.termination_reason)
        self.assertEqual(first.cycles_completed, second.cycles_completed)
        self.assertEqual(task.to_dict(), task_snapshot)
        self.assertEqual(self.goal.to_dict(), goal_snapshot)

    def test_calculator_completion_integrates_tool_observation_and_belief(self) -> None:
        source_input = {
            "operation": "multiply",
            "operands": [17, 23],
            "expected_answer": 391,
        }
        task = Task(self.goal, source_input)
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        agent = GoalDirectedAgent(registry)
        source_input["operands"].append(99)
        task_snapshot = task.to_dict()

        result = agent.run(task, max_cycles=2)

        self.assertEqual(result.status, AgentStatus.COMPLETED)
        self.assertEqual(result.termination_reason, TerminationReason.GOAL_SATISFIED)
        self.assertEqual(result.answer, 391)
        self.assertEqual(result.cycles_completed, 1)
        self.assertEqual(result.final_state.observation.source, "tool:calculator")
        observation_content = result.final_state.observation.content
        self.assertTrue(observation_content["success"])
        self.assertEqual(observation_content["output"], 391)
        self.assertEqual(
            observation_content["parameters"],
            {"operation": "multiply", "operands": [17, 23]},
        )
        self.assertNotIn("expected_answer", observation_content["parameters"])
        record = result.final_state.belief.state["observation:tool:calculator"]
        self.assertEqual(record.evidence[-1]["source"], "tool:calculator")
        self.assertEqual(record.evidence[-1]["content"]["output"], 391)
        self.assertEqual(task.to_dict(), task_snapshot)
        self.assertEqual(registry.list_names(), ("calculator",))
        self.assertFalse(hasattr(result, "trajectory"))
        self.assertTrue(all("output" not in evidence for evidence in result.evidence))

    def test_incomplete_and_failure_outcomes_do_not_contaminate_later_runs(self) -> None:
        agent = self._agent_with_calculator()

        mismatch = agent.run(self._direct_task("not-ready", "ready"), max_cycles=3)
        tool_incomplete = agent.run(self._calculator_task(400), max_cycles=2)
        unsupported_input = {
            "id": "payload-id",
            "timestamp": "payload-time",
            "status": "payload-status",
            "termination_reason": "payload-reason",
            "error": "payload-error",
        }
        unsupported = agent.run(Task(self.goal, unsupported_input), max_cycles=1)
        direct_success = agent.run(self._direct_task("ready", "ready"), max_cycles=2)
        calculator_success = agent.run(self._calculator_task(391), max_cycles=2)

        self.assertEqual(mismatch.status, AgentStatus.INCOMPLETE)
        self.assertEqual(mismatch.termination_reason, TerminationReason.MAX_CYCLES_REACHED)
        self.assertEqual(mismatch.answer, "not-ready")
        self.assertEqual(mismatch.cycles_completed, 1)
        self.assertIsNotNone(mismatch.final_state)

        self.assertEqual(tool_incomplete.status, AgentStatus.INCOMPLETE)
        self.assertEqual(tool_incomplete.termination_reason, TerminationReason.MAX_CYCLES_REACHED)
        self.assertEqual(tool_incomplete.answer, 391)
        self.assertEqual(tool_incomplete.cycles_completed, 2)
        self.assertEqual(
            len(tool_incomplete.final_state.belief.state["observation:tool:calculator"].evidence),
            2,
        )

        self.assertEqual(unsupported.status, AgentStatus.FAILED)
        self.assertEqual(unsupported.termination_reason, TerminationReason.UNSUPPORTED_TASK)
        self.assertIsNone(unsupported.answer)
        self.assertEqual(unsupported.cycles_completed, 1)
        self.assertIsNotNone(unsupported.final_state)
        self.assertEqual(
            unsupported.final_state.observation.content["input"],
            unsupported_input,
        )

        self.assertEqual(direct_success.answer, "ready")
        self.assertEqual(calculator_success.answer, 391)
        self.assertEqual(calculator_success.status, AgentStatus.COMPLETED)
        self.assertIsNot(tool_incomplete.final_state, calculator_success.final_state)
        self.assertIsNot(tool_incomplete.evidence, calculator_success.evidence)

    def test_controlled_tool_failure_is_explicit_and_has_no_global_effect(self) -> None:
        failing_registry = ToolRegistry()
        failing_registry.register(_FailingCalculator())
        failure = GoalDirectedAgent(failing_registry).run(self._calculator_task(391), max_cycles=1)

        self.assertEqual(failure.status, AgentStatus.FAILED)
        self.assertEqual(failure.termination_reason, TerminationReason.TOOL_FAILURE)
        self.assertIsNone(failure.answer)
        self.assertEqual(failure.cycles_completed, 1)
        self.assertTrue(all("controlled failure" not in str(item) for item in failure.evidence))
        self.assertFalse(hasattr(failure, "trajectory"))

        success = self._agent_with_calculator().run(self._calculator_task(391), max_cycles=1)
        self.assertEqual(success.status, AgentStatus.COMPLETED)
        self.assertEqual(success.answer, 391)

    def test_zero_cycles_initializes_runtime_without_consuming_a_policy(self) -> None:
        result = GoalDirectedAgent(ToolRegistry()).run(self._direct_task("ready", "ready"), 0)

        self.assertEqual(result.status, AgentStatus.INCOMPLETE)
        self.assertEqual(result.termination_reason, TerminationReason.MAX_CYCLES_REACHED)
        self.assertEqual(result.cycles_completed, 0)
        self.assertIsNone(result.answer)
        self.assertIsNotNone(result.final_state)
        self.assertEqual(result.final_state.observation.source, "task")
        self.assertEqual(result.final_state.belief.version, 1)
        self.assertEqual(result.evidence, ({"type": "limit", "reason": "max_cycles_reached"},))

    def test_real_calculator_result_round_trips_without_aliases(self) -> None:
        task = self._calculator_task(391)
        result = self._agent_with_calculator().run(task, max_cycles=1)
        serialized = result.to_dict()
        restored = AgentResult.from_dict(serialized)
        original_snapshot = deepcopy(result.to_dict())

        self.assertEqual(restored, result)
        self.assertEqual(restored.task_id, task.id)
        self.assertEqual(restored.status, AgentStatus.COMPLETED)
        self.assertEqual(restored.termination_reason, TerminationReason.GOAL_SATISFIED)
        self.assertEqual(restored.answer, 391)
        self.assertEqual(restored.cycles_completed, 1)
        serialized["evidence"][0]["action"] = "mutated"
        serialized["final_state"]["observation"]["content"]["output"] = "mutated"
        self.assertEqual(result.to_dict(), original_snapshot)
        self.assertEqual(restored.answer, 391)

    def test_equivalent_calculator_runs_have_the_same_public_semantics(self) -> None:
        first = self._agent_with_calculator().run(self._calculator_task(391), max_cycles=1)
        second = self._agent_with_calculator().run(self._calculator_task(391), max_cycles=1)

        self.assertEqual(self._calculator_semantics(first), self._calculator_semantics(second))
        self.assertNotEqual(first.task_id, second.task_id)
        self.assertNotEqual(first.final_state.observation.id, second.final_state.observation.id)

    @staticmethod
    def _calculator_semantics(result: AgentResult) -> dict[str, object]:
        """Project only documented generated fields away from a real result."""

        task_evidence = result.final_state.belief.state["observation:task"].evidence[-1]
        tool_evidence = result.final_state.belief.state[
            "observation:tool:calculator"
        ].evidence[-1]
        return {
            "status": result.status.value,
            "termination_reason": result.termination_reason.value,
            "answer": result.to_dict()["answer"],
            "cycles_completed": result.cycles_completed,
            "evidence": result.to_dict()["evidence"],
            "final_observation": {
                "source": result.final_state.observation.source,
                "content": result.final_state.observation.to_dict()["content"],
            },
            "belief": {
                "version": result.final_state.belief.version,
                "task": {
                    "source": task_evidence["source"],
                    "goal": task_evidence["content"]["goal"],
                    "input": task_evidence["content"]["input"],
                    "context": task_evidence["content"]["context"],
                    "constraints": task_evidence["content"]["constraints"],
                },
                "tool": {
                    "source": tool_evidence["source"],
                    "content": tool_evidence["content"],
                },
            },
        }


if __name__ == "__main__":
    unittest.main()
