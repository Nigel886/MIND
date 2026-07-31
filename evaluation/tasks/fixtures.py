"""Frozen, non-executing M10 evaluation scenario fixtures."""

from __future__ import annotations

from uuid import UUID

from evaluation.tasks.evaluation_task import EvaluationScenario, EvaluationTask
from evaluation.tasks.scenarios import SCENARIO_ORDER
from src.core.task import Goal, Task


def _scenario(
    name: str,
    description: str,
    category: str,
    expected_behavior: str,
    expected_outcome: str,
    task_input: dict[str, object],
    task_id: str,
    task_metadata: dict[str, object] | None = None,
    scenario_metadata: dict[str, object] | None = None,
) -> EvaluationScenario:
    """Build one fresh immutable fixture from only frozen static data."""

    task = Task(
        goal=Goal(description, ("preserve the specified deterministic outcome",)),
        input=task_input,
        metadata={} if task_metadata is None else task_metadata,
        id=UUID(task_id),
    )
    return EvaluationScenario(
        name=name,
        description=description,
        evaluation_task=EvaluationTask(
            name=name,
            description=description,
            task=task,
            category=category,
            expected_behavior=expected_behavior,
        ),
        expected_outcome=expected_outcome,
        metadata={} if scenario_metadata is None else scenario_metadata,
    )


def get_default_evaluation_scenarios() -> tuple[EvaluationScenario, ...]:
    """Return fresh ordered M10 fixtures without executing any component."""

    scenarios = (
        _scenario(
            "direct_success",
            "Verify deterministic direct-answer completion.",
            "direct_success",
            "completed",
            "completed",
            {"value": "ready", "expected_answer": "ready"},
            "10000000-0000-0000-0000-000000000001",
        ),
        _scenario(
            "calculator_success",
            "Verify deterministic calculator-tool completion.",
            "calculator_success",
            "completed",
            "completed",
            {"operation": "multiply", "operands": [17, 23], "expected_answer": 391},
            "10000000-0000-0000-0000-000000000002",
        ),
        _scenario(
            "unique_strategy_match",
            "Verify the unique Meta-Inference selection path.",
            "meta_inference",
            "SELECTED",
            "SELECTED",
            {"value": "ready", "expected_answer": "ready"},
            "10000000-0000-0000-0000-000000000003",
            {"required_inference_capabilities": ["incremental"]},
        ),
        _scenario(
            "unavailable_strategy",
            "Verify the unavailable Meta-Inference selection path.",
            "meta_inference",
            "UNAVAILABLE",
            "UNAVAILABLE",
            {"value": "ready", "expected_answer": "ready"},
            "10000000-0000-0000-0000-000000000004",
            {"required_inference_capabilities": ["unavailable"]},
        ),
        _scenario(
            "ambiguous_strategy",
            "Verify the ambiguous Meta-Inference selection path.",
            "meta_inference",
            "REJECTED",
            "REJECTED",
            {"value": "ready", "expected_answer": "ready"},
            "10000000-0000-0000-0000-000000000005",
            {"required_inference_capabilities": ["ambiguous"]},
        ),
        _scenario(
            "m8_compatibility_direct_success",
            "Verify preserved M8 direct-answer behavior.",
            "m8_compatibility",
            "completed",
            "completed",
            {"value": "ready", "expected_answer": "ready"},
            "10000000-0000-0000-0000-000000000006",
        ),
        _scenario(
            "m8_compatibility_calculator_success",
            "Verify preserved M8 calculator behavior.",
            "m8_compatibility",
            "completed",
            "completed",
            {"operation": "multiply", "operands": [17, 23], "expected_answer": 391},
            "10000000-0000-0000-0000-000000000007",
        ),
        _scenario(
            "m8_compatibility_unsupported_task",
            "Verify preserved M8 unsupported-task failure behavior.",
            "m8_compatibility",
            "unsupported_task",
            "unsupported_task",
            {},
            "10000000-0000-0000-0000-000000000008",
        ),
        _scenario(
            "m8_compatibility_tool_failure",
            "Verify preserved M8 missing-calculator failure behavior.",
            "m8_compatibility",
            "tool_failure",
            "tool_failure",
            {"operation": "add", "operands": [1, 2], "expected_answer": 3},
            "10000000-0000-0000-0000-000000000009",
            scenario_metadata={"tool_configuration": "without_calculator"},
        ),
        _scenario(
            "m8_compatibility_bounded_execution",
            "Verify preserved M8 zero-cycle bounded execution behavior.",
            "m8_compatibility",
            "max_cycles_reached",
            "max_cycles_reached",
            {"value": "wrong", "expected_answer": "right"},
            "10000000-0000-0000-0000-000000000010",
            scenario_metadata={"max_cycles": 0},
        ),
    )
    if tuple(scenario.name for scenario in scenarios) != SCENARIO_ORDER:
        raise RuntimeError("fixture order must match SCENARIO_ORDER")
    return scenarios
