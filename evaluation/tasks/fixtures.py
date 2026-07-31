"""Frozen, non-executing M10 evaluation scenario fixtures."""

from __future__ import annotations

from uuid import UUID

from evaluation.tasks.evaluation_task import EvaluationScenario, EvaluationTask
from evaluation.tasks.scenarios import SCENARIO_ORDER
from src.core.meta_inference import MetaInferenceDecisionStatus
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


M12_SCENARIO_ORDER = (
    "m12_unique_capability_match",
    "m12_unavailable_capability",
    "m12_ambiguous_capability_match",
    "m12_evidence_consistency",
    "m12_m8_direct_task",
    "m12_m8_calculator_task",
    "m12_m8_unsupported_task",
    "m12_m8_controlled_failure",
)


def _m12_scenario(
    name: str,
    description: str,
    category: str,
    expected_behavior: str,
    expected_outcome: str,
    task_input: dict[str, object],
    task_id: str,
    *,
    task_metadata: dict[str, object] | None = None,
    scenario_metadata: dict[str, object] | None = None,
) -> EvaluationScenario:
    """Build one fresh M12 fixture from frozen, local-only values."""

    metadata = {
        "protocol_version": "M12-v1",
        "baseline_scope": ["A", "B", "C"],
    }
    if scenario_metadata is not None:
        metadata.update(scenario_metadata)
    return _scenario(
        name,
        description,
        category,
        expected_behavior,
        expected_outcome,
        task_input,
        task_id,
        task_metadata,
        metadata,
    )


def get_m12_validation_scenarios() -> tuple[EvaluationScenario, ...]:
    """Return fresh ordered, non-executing M12 validation fixtures.

    The returned values specify only frozen inputs and expected semantics for
    later validation stages. They do not construct a registry, execute an
    Agent, select a strategy, calculate metrics, or run an experiment.
    """

    selected = MetaInferenceDecisionStatus.SELECTED.value
    unavailable = MetaInferenceDecisionStatus.UNAVAILABLE.value
    rejected = MetaInferenceDecisionStatus.REJECTED.value
    calculator_descriptor = {
        "name": "calculator_strategy",
        "capabilities": ["calculator"],
    }
    ambiguous_descriptors = [
        {"name": "calculator_strategy_a", "capabilities": ["calculator"]},
        {"name": "calculator_strategy_b", "capabilities": ["calculator"]},
    ]

    scenarios = (
        _m12_scenario(
            "m12_unique_capability_match",
            "One calculator-capable strategy must be selected.",
            "meta_inference_selection",
            selected,
            selected,
            {"operation": "multiply", "operands": [17, 23], "expected_answer": 391},
            "12000000-0000-0000-0000-000000000001",
            task_metadata={"required_inference_capabilities": ["calculator"]},
            scenario_metadata={
                "expected_selected_strategy": "calculator_strategy",
                "registry_descriptors": [calculator_descriptor],
            },
        ),
        _m12_scenario(
            "m12_unavailable_capability",
            "An unsupported capability must be marked unavailable.",
            "meta_inference_selection",
            unavailable,
            unavailable,
            {"value": "ready", "expected_answer": "ready"},
            "12000000-0000-0000-0000-000000000002",
            task_metadata={"required_inference_capabilities": ["unknown"]},
            scenario_metadata={"registry_descriptors": [calculator_descriptor]},
        ),
        _m12_scenario(
            "m12_ambiguous_capability_match",
            "Two matching strategies must be rejected as ambiguous.",
            "meta_inference_selection",
            rejected,
            rejected,
            {"value": "ready", "expected_answer": "ready"},
            "12000000-0000-0000-0000-000000000003",
            task_metadata={"required_inference_capabilities": ["calculator"]},
            scenario_metadata={"registry_descriptors": ambiguous_descriptors},
        ),
        _m12_scenario(
            "m12_evidence_consistency",
            "Repeated equivalent selection must have equivalent evidence semantics.",
            "meta_inference_evidence",
            selected,
            selected,
            {"value": "ready", "expected_answer": "ready"},
            "12000000-0000-0000-0000-000000000004",
            task_metadata={"required_inference_capabilities": ["calculator"]},
            scenario_metadata={
                "expected_selected_strategy": "calculator_strategy",
                "registry_descriptors": [calculator_descriptor],
                "comparison_fields": ["status", "selected_strategy", "evidence"],
                "ignore_fields": ["uuid", "timestamp"],
            },
        ),
        _m12_scenario(
            "m12_m8_direct_task",
            "M8 direct-task completion remains a compatibility reference.",
            "m8_compatibility",
            "completed",
            "completed",
            {"value": "ready", "expected_answer": "ready"},
            "12000000-0000-0000-0000-000000000005",
            scenario_metadata={"comparison_scope": "agent_outcome"},
        ),
        _m12_scenario(
            "m12_m8_calculator_task",
            "M8 calculator completion remains a compatibility reference.",
            "m8_compatibility",
            "completed",
            "completed",
            {"operation": "multiply", "operands": [17, 23], "expected_answer": 391},
            "12000000-0000-0000-0000-000000000006",
            task_metadata={"required_inference_capabilities": ["calculator"]},
            scenario_metadata={
                "comparison_scope": "agent_outcome",
                "registry_descriptors": [calculator_descriptor],
            },
        ),
        _m12_scenario(
            "m12_m8_unsupported_task",
            "M8 unsupported-task failure remains a compatibility reference.",
            "m8_compatibility",
            "unsupported_task",
            "unsupported_task",
            {"unsupported": True},
            "12000000-0000-0000-0000-000000000007",
            scenario_metadata={"comparison_scope": "failure_semantics"},
        ),
        _m12_scenario(
            "m12_m8_controlled_failure",
            "M8 missing-calculator failure remains a compatibility reference.",
            "m8_compatibility",
            "tool_failure",
            "tool_failure",
            {"operation": "add", "operands": [1, 2], "expected_answer": 3},
            "12000000-0000-0000-0000-000000000008",
            scenario_metadata={
                "comparison_scope": "failure_semantics",
                "tool_configuration": "without_calculator",
            },
        ),
    )
    if tuple(scenario.name for scenario in scenarios) != M12_SCENARIO_ORDER:
        raise RuntimeError("M12 fixture order must match M12_SCENARIO_ORDER")
    return scenarios
