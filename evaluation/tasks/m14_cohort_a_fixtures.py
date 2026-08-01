"""Frozen deterministic fixture registrations for M14 Cohort A."""

from __future__ import annotations

from uuid import UUID

from src.core.task import Goal, Task
from src.evaluation.cohort_a import (
    M14CohortADifficulty,
    M14CohortATaskCategory,
    M14CohortATaskFixture,
    fixture_suite_hash,
)
from src.evaluation.contracts import EvaluationActionType, EvaluationCase
from src.evaluation.environment import (
    EnvironmentConfig,
    FailureInjectionRule,
    FailureInjectionType,
)
from src.evaluation.execution import EvaluationBudget


_SUITE_ID = "m14-cohort-a"
_SUITE_VERSION = "1.0.0"
_RULE_VERSION = "m14-cohort-a-rule-v1"


def _case(identifier: str, task: Task, environment_id: str) -> EvaluationCase:
    return EvaluationCase(
        evaluation_id=identifier,
        task=task,
        environment_config={"environment_id": environment_id},
    )


def get_m14_cohort_a_fixtures() -> tuple[M14CohortATaskFixture, ...]:
    """Return the ordered immutable Cohort A fixture suite.

    Returning freshly reconstructed immutable values prevents a caller from
    retaining mutable aliases while preserving canonical serialized content.
    This function registers fixtures only; it never runs an evaluation.
    """

    direct_task = Task(
        id=UUID("00000000-0000-0000-0000-000000000661"),
        goal=Goal("Return the supplied value", ("Return ready",)),
        input={"value": "ready", "expected_answer": "ready"},
    )
    calculator_task = Task(
        id=UUID("00000000-0000-0000-0000-000000000662"),
        goal=Goal("Multiply the operands", ("Return 391",)),
        input={"operation": "multiply", "operands": [17, 23], "expected_answer": 391},
    )
    unsupported_task = Task(
        id=UUID("00000000-0000-0000-0000-000000000663"),
        goal=Goal("Handle an unsupported request safely", ("Fail explicitly",)),
        input={"operation": "unsupported"},
    )
    failure_task = Task(
        id=UUID("00000000-0000-0000-0000-000000000664"),
        goal=Goal("Handle a declared tool fault", ("Fail explicitly",)),
        input={"operation": "multiply", "operands": [17, 23], "expected_answer": 391},
    )

    direct_environment = EnvironmentConfig(
        environment_id="m14-direct-v1",
        tool_responses={},
        completion_context={"expected_answer": "ready"},
    )
    calculator_environment = EnvironmentConfig(
        environment_id="m14-calculator-v1",
        tool_responses={"calculator": {"output": 391}},
        completion_context={"expected_answer": 391},
    )
    unsupported_environment = EnvironmentConfig(
        environment_id="m14-unsupported-v1",
        tool_responses={},
        completion_context={"expected_failure_category": "unsupported_task"},
    )
    failure_environment = EnvironmentConfig(
        environment_id="m14-tool-failure-v1",
        tool_responses={"calculator": {"output": 391}},
        failure_injections=(
            FailureInjectionRule(
                rule_id="calculator-tool-failure",
                trigger_step=1,
                failure_type=FailureInjectionType.TOOL_FAILURE,
                action_type=EvaluationActionType.TOOL_CALL,
                tool_name="calculator",
            ),
        ),
        completion_context={"expected_failure_category": "tool_failure"},
    )
    return (
        M14CohortATaskFixture(
            task_id="m14-direct-ready",
            category=M14CohortATaskCategory.DIRECT_TASK,
            difficulty=M14CohortADifficulty.EASY,
            task_definition={"case": _case("m14-direct-ready", direct_task, "m14-direct-v1").to_dict()},
            environment_config=direct_environment,
            budget=EvaluationBudget(max_steps=1, max_tool_calls=0),
            completion_rule_version=_RULE_VERSION,
        ),
        M14CohortATaskFixture(
            task_id="m14-calculator-multiply",
            category=M14CohortATaskCategory.CONTROLLED_TOOL_TASK,
            difficulty=M14CohortADifficulty.EASY,
            task_definition={"case": _case("m14-calculator-multiply", calculator_task, "m14-calculator-v1").to_dict()},
            environment_config=calculator_environment,
            budget=EvaluationBudget(max_steps=2, max_tool_calls=1),
            completion_rule_version=_RULE_VERSION,
        ),
        M14CohortATaskFixture(
            task_id="m14-unsupported-operation",
            category=M14CohortATaskCategory.DIRECT_TASK,
            difficulty=M14CohortADifficulty.MEDIUM,
            task_definition={"case": _case("m14-unsupported-operation", unsupported_task, "m14-unsupported-v1").to_dict()},
            environment_config=unsupported_environment,
            budget=EvaluationBudget(max_steps=1, max_tool_calls=0),
            completion_rule_version=_RULE_VERSION,
        ),
        M14CohortATaskFixture(
            task_id="m14-declared-tool-failure",
            category=M14CohortATaskCategory.FAILURE_RECOVERY_TASK,
            difficulty=M14CohortADifficulty.MEDIUM,
            task_definition={"case": _case("m14-declared-tool-failure", failure_task, "m14-tool-failure-v1").to_dict()},
            environment_config=failure_environment,
            budget=EvaluationBudget(max_steps=2, max_tool_calls=1),
            completion_rule_version=_RULE_VERSION,
        ),
    )


def get_m14_cohort_a_suite_metadata() -> dict[str, str]:
    """Return stable public suite metadata without generating any results."""

    fixtures = get_m14_cohort_a_fixtures()
    return {
        "suite_id": _SUITE_ID,
        "suite_version": _SUITE_VERSION,
        "suite_hash": fixture_suite_hash(fixtures),
        "completion_rule_version": _RULE_VERSION,
    }
