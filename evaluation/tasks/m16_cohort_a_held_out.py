"""Deterministically generated formal M16 Cohort A held-out registrations.

This module registers immutable cases only. Importing or calling its public
function does not run an Agent, provider, environment episode, or benchmark.
"""

from __future__ import annotations

from uuid import UUID

from src.core.task import Goal, Task
from src.evaluation.contracts import EvaluationCase
from src.evaluation.m16_cohort_a_suite import (
    M16CohortADifficulty,
    M16HeldOutCaseEnvelope,
    M16CohortAHeldOutSuite,
    M16CohortATaskFamily,
    M16_COHORT_A_SUITE_VERSION,
    M16_PROTOCOL_VERSION,
)
from src.evaluation.m16_leakage_free import (
    M16PrivateEnvironmentSpecification,
    M16PrivateTruth,
)


_JUDGE_ID = "m16-exact-judge-v1"
_CASE_VERSION = "1.0.0"
_ENVIRONMENT_ID = "m16-private-calculator-v1"


def _eligibility(family: M16CohortATaskFamily) -> dict[str, object]:
    return {
        "m16_cohort_a": {
            "task_family": (
                "direct_answer"
                if family is M16CohortATaskFamily.DIRECT_ANSWER
                else "controlled_single_tool"
            ),
            "tool_call_limit": 0 if family is M16CohortATaskFamily.DIRECT_ANSWER else 1,
            "requires_planning": False,
            "requires_multi_tool": False,
            "requires_dependent_multistep": False,
            "requires_recovery": False,
        }
    }


def _identifier(family: M16CohortATaskFamily, difficulty: M16CohortADifficulty, index: int) -> str:
    return f"m16.cohort_a.{family.value}.{difficulty.value}.{index:02d}"


def _uuid(index: int) -> UUID:
    return UUID(f"00000000-0000-0000-0000-{index:012d}")


def _direct_value(difficulty: M16CohortADifficulty, index: int):
    if difficulty is M16CohortADifficulty.EASY:
        values = (0, 1, -1, True, False, None, "alpha", "beta", 7, -7, "", 42, "delta", 99, -99, "omega")
        return values[index - 1]
    if difficulty is M16CohortADifficulty.MEDIUM:
        return {
            "case": index,
            "items": [index, f"medium-{index}"],
            "enabled": index % 2 == 0,
        }
    return {
        "case": index,
        "payload": [
            {"numbers": [index, -index], "labels": [f"hard-{index}", "m16"]},
            {"flags": {"even": index % 2 == 0, "positive": True}},
        ],
    }


def _calculator_values(difficulty: M16CohortADifficulty, index: int) -> tuple[str, list[int]]:
    operation = "add" if index % 2 else "multiply"
    if difficulty is M16CohortADifficulty.EASY:
        return operation, [(index - 1) // 4, (index - 1) % 4]
    if difficulty is M16CohortADifficulty.MEDIUM:
        left = 10 + index * 17
        right = 100 + index * 23
        return operation, ([-left, right] if index % 2 else [left, -right])
    left = 1_000 + index * 1_003
    right = 10_000 + index * 2_009
    return operation, ([-left, -right] if index % 2 else [left, -right])


def _direct_case(difficulty: M16CohortADifficulty, index: int, serial: int) -> M16HeldOutCaseEnvelope:
    family = M16CohortATaskFamily.DIRECT_ANSWER
    value = _direct_value(difficulty, index)
    identifier = _identifier(family, difficulty, index)
    task = Task(
        id=_uuid(serial),
        goal=Goal("Return the supplied public value", ("Produce the requested result",)),
        input={"value": value},
        metadata=_eligibility(family),
    )
    return M16HeldOutCaseEnvelope(
        evaluation_case=EvaluationCase(identifier, task, {"environment_id": _ENVIRONMENT_ID}),
        private_truth=M16PrivateTruth(value, _JUDGE_ID),
        task_family=family,
        difficulty=difficulty,
        held_out=True,
        suite_version=M16_COHORT_A_SUITE_VERSION,
        case_version=_CASE_VERSION,
        environment_specification=M16PrivateEnvironmentSpecification(_ENVIRONMENT_ID),
        judge_id=_JUDGE_ID,
    )


def _calculator_case(difficulty: M16CohortADifficulty, index: int, serial: int) -> M16HeldOutCaseEnvelope:
    family = M16CohortATaskFamily.CALCULATOR
    operation, operands = _calculator_values(difficulty, index)
    identifier = _identifier(family, difficulty, index)
    expected = operands[0] + operands[1] if operation == "add" else operands[0] * operands[1]
    task = Task(
        id=_uuid(serial),
        goal=Goal("Use the public calculator operation", ("Produce the requested result",)),
        input={"operation": operation, "operands": operands},
        metadata=_eligibility(family),
    )
    return M16HeldOutCaseEnvelope(
        evaluation_case=EvaluationCase(identifier, task, {"environment_id": _ENVIRONMENT_ID}),
        private_truth=M16PrivateTruth(expected, _JUDGE_ID),
        task_family=family,
        difficulty=difficulty,
        held_out=True,
        suite_version=M16_COHORT_A_SUITE_VERSION,
        case_version=_CASE_VERSION,
        environment_specification=M16PrivateEnvironmentSpecification(_ENVIRONMENT_ID),
        judge_id=_JUDGE_ID,
    )


def get_m16_cohort_a_held_out_suite() -> M16CohortAHeldOutSuite:
    """Return the complete ordered 96-case formal suite without executing it."""

    cases: list[M16HeldOutCaseEnvelope] = []
    serial = 1
    for family in M16CohortATaskFamily:
        for difficulty in M16CohortADifficulty:
            for index in range(1, 17):
                case = (
                    _direct_case(difficulty, index, serial)
                    if family is M16CohortATaskFamily.DIRECT_ANSWER
                    else _calculator_case(difficulty, index, serial)
                )
                cases.append(case)
                serial += 1
    return M16CohortAHeldOutSuite(tuple(sorted(cases, key=lambda item: item.evaluation_id)))
