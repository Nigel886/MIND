"""Run the finite M8 Goal-Directed Agent calculator demonstration."""

from __future__ import annotations

from src.core.agent import GoalDirectedAgent
from src.core.result import AgentStatus
from src.core.task import Goal, Task
from src.core.tool import ToolRegistry
from src.tools.calculator import CalculatorTool


def main() -> None:
    """Print a serialized AgentResult for the deterministic 17 * 23 task."""

    registry = ToolRegistry()
    registry.register(CalculatorTool())
    task = Task(
        goal=Goal(
            "calculate the requested product",
            ("return the expected numeric result",),
        ),
        input={
            "operation": "multiply",
            "operands": [17, 23],
            "expected_answer": 391,
        },
    )
    result = GoalDirectedAgent(registry).run(task, max_cycles=1)
    if result.status is not AgentStatus.COMPLETED:
        raise RuntimeError(
            f"Goal-Directed Agent demo did not complete: {result.termination_reason.value}",
        )
    print(result.to_dict())


if __name__ == "__main__":
    main()
