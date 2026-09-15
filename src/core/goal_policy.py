"""Deterministic task-level policy generation for M8."""
from __future__ import annotations
from copy import deepcopy
from typing import Any
from src.core.policy import Policy
from src.core.policy_context import PolicyDecisionContext
from src.core.runtime import RuntimeState
from src.core.task import Task

class GoalAwarePolicyEngine:
    """Selects one task-level decision without execution or completion logic."""
    @staticmethod
    def generate(task: Task, runtime_state: RuntimeState) -> Policy:
        if not isinstance(task, Task): raise TypeError("task must be a Task")
        if not isinstance(runtime_state, RuntimeState): raise TypeError("runtime_state must be a RuntimeState")
        data = task.to_dict()["input"]
        keys = set(data)
        if keys == {"value", "expected_answer"}:
            return Policy("produce_answer", {"answer": deepcopy(data["value"])}, {})
        if keys == {"operation", "operands", "expected_answer"} and data["operation"] in ("add", "multiply") and isinstance(data["operands"], list):
            return Policy("call_tool", {"tool_name": "calculator", "tool_parameters": {"operation": data["operation"], "operands": deepcopy(data["operands"])}}, {})
        return Policy("fail_task", {"reason": "unsupported_task"}, {})

    @staticmethod
    def decide(context: PolicyDecisionContext) -> Policy:
        """Implement the additive generalized policy boundary.

        This compatibility method intentionally uses only the sanitized context
        and leaves :meth:`generate` unchanged for existing M8 callers.
        """

        if not isinstance(context, PolicyDecisionContext):
            raise TypeError("context must be a PolicyDecisionContext")
        data = context.task.public_input
        keys = set(data)
        if keys == {"value"}:
            return Policy("produce_answer", {"answer": deepcopy(data["value"])}, {})
        if (
            keys == {"operation", "operands"}
            and data["operation"] in ("add", "multiply")
            and isinstance(data["operands"], tuple)
        ):
            return Policy(
                "call_tool",
                {
                    "tool_name": "calculator",
                    "tool_parameters": {
                        "operation": data["operation"],
                        "operands": deepcopy(list(data["operands"])),
                    },
                },
                {},
            )
        return Policy("fail_task", {"reason": "unsupported_task"}, {})
