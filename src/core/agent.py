"""Bounded high-level task orchestration for M8."""
from __future__ import annotations
from typing import Any
from src.core.completion import CompletionEvaluator
from src.core.goal_policy import GoalAwarePolicyEngine
from src.core.observation import Observation
from src.core.result import AgentResult, AgentStatus, TerminationReason
from src.core.runtime import RuntimeController, RuntimeState
from src.core.task import Task
from src.core.tool import ToolRegistry, tool_result_to_observation

def _task_observation(task: Task) -> Observation:
    data = task.to_dict()
    return Observation(source="task", content={"task_id": str(task.id), "goal": task.goal.to_dict(), "input": data["input"], "context": data["context"], "constraints": data["constraints"]})

class GoalDirectedAgent:
    def __init__(self, tool_registry: ToolRegistry) -> None:
        if not isinstance(tool_registry, ToolRegistry): raise TypeError("tool_registry must be a ToolRegistry")
        self._tool_registry = tool_registry
    def _result(self, task: Task, status: AgentStatus, reason: TerminationReason, state: RuntimeState, cycles: int, answer: Any = None, evidence: tuple[dict[str, Any], ...] = ()) -> AgentResult:
        return AgentResult(task.id, status, answer, state, reason, cycles, evidence, {})
    def run(self, task: Task, max_cycles: int) -> AgentResult:
        if not isinstance(task, Task): raise TypeError("task must be a Task")
        if isinstance(max_cycles, bool) or not isinstance(max_cycles, int): raise TypeError("max_cycles must be an int, not bool")
        if max_cycles < 0: raise ValueError("max_cycles must not be negative")
        initial = _task_observation(task)
        state = RuntimeController.initialize(observation=initial)
        state = RuntimeController.apply_inference(state, initial)
        if max_cycles == 0: return self._result(task, AgentStatus.INCOMPLETE, TerminationReason.MAX_CYCLES_REACHED, state, 0, evidence=({"type":"limit","reason":"max_cycles_reached"},))
        last_answer = None
        for cycle in range(1, max_cycles + 1):
            policy = GoalAwarePolicyEngine.generate(task, state)
            base = ({"type":"policy","action":policy.action},)
            if policy.action == "produce_answer":
                if set(policy.parameters) != {"answer"}: return self._result(task, AgentStatus.FAILED, TerminationReason.POLICY_FAILURE, state, cycle, evidence=base)
                decision = CompletionEvaluator.evaluate(task, state, policy.parameters["answer"])
                evidence = base + ({"type":"completion","satisfied":decision.is_satisfied},)
                if decision.is_satisfied: return self._result(task, AgentStatus.COMPLETED, TerminationReason.GOAL_SATISFIED, state, cycle, decision.answer, evidence)
                return self._result(task, AgentStatus.INCOMPLETE, TerminationReason.MAX_CYCLES_REACHED, state, cycle, decision.answer, evidence)
            if policy.action == "fail_task":
                if policy.parameters != {"reason":"unsupported_task"}: return self._result(task, AgentStatus.FAILED, TerminationReason.POLICY_FAILURE, state, cycle, evidence=base)
                return self._result(task, AgentStatus.FAILED, TerminationReason.UNSUPPORTED_TASK, state, cycle, evidence=base)
            if policy.action != "call_tool" or set(policy.parameters) != {"tool_name","tool_parameters"} or not isinstance(policy.parameters["tool_name"], str) or not isinstance(policy.parameters["tool_parameters"], dict):
                return self._result(task, AgentStatus.FAILED, TerminationReason.POLICY_FAILURE, state, cycle, evidence=base)
            name = policy.parameters["tool_name"]
            try: tool = self._tool_registry.get(name)
            except LookupError: return self._result(task, AgentStatus.FAILED, TerminationReason.TOOL_FAILURE, state, cycle, evidence=base + ({"type":"tool","tool_name":name,"success":False},))
            result = tool.execute(policy.parameters["tool_parameters"])
            if not result.success: return self._result(task, AgentStatus.FAILED, TerminationReason.TOOL_FAILURE, state, cycle, evidence=base + ({"type":"tool","tool_name":name,"success":False},))
            state = RuntimeController.apply_inference(state, tool_result_to_observation(result))
            last_answer = result.output
            decision = CompletionEvaluator.evaluate(task, state, last_answer)
            evidence = base + ({"type":"tool","tool_name":name,"success":True},{"type":"completion","satisfied":decision.is_satisfied})
            if decision.is_satisfied: return self._result(task, AgentStatus.COMPLETED, TerminationReason.GOAL_SATISFIED, state, cycle, decision.answer, evidence)
        return self._result(task, AgentStatus.INCOMPLETE, TerminationReason.MAX_CYCLES_REACHED, state, max_cycles, last_answer, ({"type":"limit","reason":"max_cycles_reached"},))
