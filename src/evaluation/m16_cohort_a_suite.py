"""Immutable formal M16 Cohort A held-out suite contracts and validation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from src.core.task import Task
from src.evaluation.cohort_a import canonical_json_hash
from src.evaluation.contracts import EvaluationCase
from src.evaluation.direct_tool_calling import assess_cohort_a_eligibility
from src.evaluation.m16_leakage_free import (
    M16PrivateEnvironmentSpecification,
    M16PrivateTruth,
)


M16_PROTOCOL_VERSION = "1.1.0"
M16_COHORT_A_SUITE_VERSION = "1.0.0"
M16_COHORT_A_GENERATOR_VERSION = "m16-cohort-a-generator-v1"


class M16CohortATaskFamily(str, Enum):
    """The two and only two M16 formal Cohort A public task families."""

    DIRECT_ANSWER = "direct_answer"
    CALCULATOR = "calculator"


class M16CohortADifficulty(str, Enum):
    """Frozen descriptive strata determined before execution."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


def _text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    if value != value.strip():
        raise ValueError(f"{name} must not have leading or trailing whitespace")


def _public_task_fingerprint(task: Task) -> str:
    """Hash agent-visible semantics without case identity or private truth."""

    data = task.to_dict()
    data.pop("id")
    return canonical_json_hash(data)


@dataclass(frozen=True)
class M16HeldOutCaseEnvelope:
    """One formal private envelope around an Agent-visible M16 case."""

    evaluation_case: EvaluationCase
    private_truth: M16PrivateTruth
    task_family: M16CohortATaskFamily
    difficulty: M16CohortADifficulty
    held_out: bool
    suite_version: str
    case_version: str
    environment_specification: M16PrivateEnvironmentSpecification
    judge_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.evaluation_case, EvaluationCase):
            raise TypeError("evaluation_case must be an EvaluationCase")
        if not isinstance(self.private_truth, M16PrivateTruth):
            raise TypeError("private_truth must be M16PrivateTruth")
        if not isinstance(self.task_family, M16CohortATaskFamily):
            raise TypeError("task_family must be an M16CohortATaskFamily")
        if not isinstance(self.difficulty, M16CohortADifficulty):
            raise TypeError("difficulty must be an M16CohortADifficulty")
        if self.held_out is not True:
            raise ValueError("formal M16 cases must have held_out=True")
        _text(self.suite_version, "suite_version")
        _text(self.case_version, "case_version")
        _text(self.judge_id, "judge_id")
        if self.private_truth.judge_id != self.judge_id:
            raise ValueError("private truth judge_id must match case judge_id")
        if self.environment_specification.environment_id != self.evaluation_case.environment_config.get("environment_id"):
            raise ValueError("public and private environment identifiers must match")
        _validate_formal_case(self)

    @property
    def evaluation_id(self) -> str:
        return self.evaluation_case.evaluation_id

    def to_private_dict(self) -> dict[str, Any]:
        """Serialize complete formal definition only for private suite storage/hash."""

        return {
            "evaluation_id": self.evaluation_id,
            "public_task": self.evaluation_case.task.to_dict(),
            "public_environment": deepcopy(dict(self.evaluation_case.environment_config)),
            "private_truth": self.private_truth.to_private_dict(),
            "task_family": self.task_family.value,
            "difficulty": self.difficulty.value,
            "held_out": self.held_out,
            "suite_version": self.suite_version,
            "case_version": self.case_version,
            "environment_specification": self.environment_specification.to_private_dict(),
            "judge_id": self.judge_id,
        }


def _validate_formal_case(case: M16HeldOutCaseEnvelope) -> None:
    task = case.evaluation_case.task
    eligibility = assess_cohort_a_eligibility(case.evaluation_case)
    if not eligibility.eligible:
        raise ValueError(f"formal case is ineligible: {eligibility.reason}")
    if "expected_answer" in task.input:
        raise ValueError("public formal Task must not contain expected_answer")
    if "expected_answer" in task.metadata:
        raise ValueError("public formal Task metadata must not contain expected_answer")
    if case.task_family is M16CohortATaskFamily.DIRECT_ANSWER:
        if set(task.input) != {"value"}:
            raise ValueError("direct formal Task input must contain exactly value")
        if task.metadata["m16_cohort_a"]["task_family"] != "direct_answer":
            raise ValueError("direct formal Task has mismatched eligibility family")
        if canonical_json_hash(task.input["value"]) != canonical_json_hash(case.private_truth.expected_answer):
            raise ValueError("direct private truth must equal the canonical public value")
    else:
        if set(task.input) != {"operation", "operands"}:
            raise ValueError("calculator formal Task input must contain operation and operands only")
        if task.metadata["m16_cohort_a"]["task_family"] != "controlled_single_tool":
            raise ValueError("calculator formal Task has mismatched eligibility family")
        operation = task.input["operation"]
        operands = task.input["operands"]
        if operation not in {"add", "multiply"}:
            raise ValueError("calculator operation must be add or multiply")
        if not isinstance(operands, tuple) or len(operands) != 2:
            raise ValueError("calculator operands must contain exactly two values")
        if any(isinstance(value, bool) or not isinstance(value, int) for value in operands):
            raise ValueError("calculator operands must be ints, not bool")
        expected = operands[0] + operands[1] if operation == "add" else operands[0] * operands[1]
        if case.private_truth.expected_answer != expected:
            raise ValueError("calculator private truth must match the frozen public operation")


@dataclass(frozen=True)
class M16CohortAHeldOutSuite:
    """Ordered complete private suite with stable full and membership hashes."""

    cases: tuple[M16HeldOutCaseEnvelope, ...]
    protocol_version: str = M16_PROTOCOL_VERSION
    suite_version: str = M16_COHORT_A_SUITE_VERSION
    generator_version: str = M16_COHORT_A_GENERATOR_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.cases, tuple):
            raise TypeError("cases must be a tuple")
        if any(not isinstance(case, M16HeldOutCaseEnvelope) for case in self.cases):
            raise TypeError("cases must contain M16HeldOutCaseEnvelope values")
        for name in ("protocol_version", "suite_version", "generator_version"):
            _text(getattr(self, name), name)
        if self.protocol_version != M16_PROTOCOL_VERSION:
            raise ValueError("protocol_version must be frozen at 1.1.0")
        if self.suite_version != M16_COHORT_A_SUITE_VERSION:
            raise ValueError("suite_version must be frozen at 1.0.0")
        if len(self.cases) != 96:
            raise ValueError("formal M16 Cohort A suite must contain exactly 96 cases")
        identifiers = [case.evaluation_id for case in self.cases]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("formal M16 suite must not contain duplicate evaluation IDs")
        if identifiers != sorted(identifiers):
            raise ValueError("formal M16 suite cases must use deterministic sorted ordering")
        fingerprints = [
            (case.task_family.value, _public_task_fingerprint(case.evaluation_case.task))
            for case in self.cases
        ]
        if len(set(fingerprints)) != len(fingerprints):
            raise ValueError("formal M16 suite must not contain duplicate public tasks within a family")
        complete = [canonical_json_hash(case.to_private_dict()) for case in self.cases]
        if len(set(complete)) != len(complete):
            raise ValueError("formal M16 suite must not contain duplicate complete cases")
        for family in M16CohortATaskFamily:
            for difficulty in M16CohortADifficulty:
                count = sum(
                    case.task_family is family and case.difficulty is difficulty
                    for case in self.cases
                )
                if count != 16:
                    raise ValueError("each family/difficulty cell must contain exactly 16 cases")

    @property
    def suite_hash(self) -> str:
        return canonical_json_hash(self.to_private_dict())

    @property
    def held_out_split_hash(self) -> str:
        return canonical_json_hash([case.evaluation_id for case in self.cases])

    def to_private_dict(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "suite_version": self.suite_version,
            "generator_version": self.generator_version,
            "held_out_split": [case.evaluation_id for case in self.cases],
            "cases": [case.to_private_dict() for case in self.cases],
        }


def m16_cohort_a_suite_manifest(suite: M16CohortAHeldOutSuite) -> dict[str, Any]:
    """Return public-safe suite identity data without case truth."""

    if not isinstance(suite, M16CohortAHeldOutSuite):
        raise TypeError("suite must be an M16CohortAHeldOutSuite")
    return {
        "protocol_version": suite.protocol_version,
        "suite_version": suite.suite_version,
        "generator_version": suite.generator_version,
        "case_count": len(suite.cases),
        "suite_hash": suite.suite_hash,
        "held_out_split_hash": suite.held_out_split_hash,
    }
