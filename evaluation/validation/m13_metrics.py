"""Pure M13 architecture-semantic metric structures with no performance claims."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable

from evaluation.tasks.m13_fixtures import M13Baseline, M13EvaluationScenario
from evaluation.validation.m13_harness import M13EvaluationRecord


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _checked_records(value: Iterable[M13EvaluationRecord]) -> tuple[M13EvaluationRecord, ...]:
    if isinstance(value, (str, bytes)):
        raise TypeError("records must be an iterable of M13EvaluationRecord")
    records = tuple(value)
    if any(not isinstance(item, M13EvaluationRecord) for item in records):
        raise TypeError("records must contain M13EvaluationRecord values")
    return records


def _checked_scenarios(value: Iterable[M13EvaluationScenario]) -> dict[str, M13EvaluationScenario]:
    if isinstance(value, (str, bytes)):
        raise TypeError("scenarios must be an iterable of M13EvaluationScenario")
    scenarios = tuple(value)
    if any(not isinstance(item, M13EvaluationScenario) for item in scenarios):
        raise TypeError("scenarios must contain M13EvaluationScenario values")
    result = {item.scenario_id: item for item in scenarios}
    if len(result) != len(scenarios):
        raise ValueError("scenarios must not contain duplicate identifiers")
    return result


@dataclass(frozen=True)
class M13EvaluationMetrics:
    """The seven frozen M13 semantic rates and no quality/performance fields."""

    proposal_validity: float
    validation_correctness: float
    validation_rejection_correctness: float
    decision_consistency: float
    evidence_consistency: float
    deterministic_repeatability: float
    failure_boundary_preservation: float

    def __post_init__(self) -> None:
        values = (
            self.proposal_validity, self.validation_correctness,
            self.validation_rejection_correctness, self.decision_consistency,
            self.evidence_consistency, self.deterministic_repeatability,
            self.failure_boundary_preservation,
        )
        if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in values):
            raise TypeError("metric values must be numbers, not bools")
        if any(not isfinite(item) or item < 0 or item > 1 for item in values):
            raise ValueError("metric values must be finite values from 0.0 through 1.0")

    def to_dict(self) -> dict[str, float]:
        return {
            "proposal_validity": self.proposal_validity,
            "validation_correctness": self.validation_correctness,
            "validation_rejection_correctness": self.validation_rejection_correctness,
            "decision_consistency": self.decision_consistency,
            "evidence_consistency": self.evidence_consistency,
            "deterministic_repeatability": self.deterministic_repeatability,
            "failure_boundary_preservation": self.failure_boundary_preservation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> "M13EvaluationMetrics":
        if not isinstance(data, dict):
            raise TypeError("M13EvaluationMetrics data must be a dict")
        return cls(**data)


def calculate_m13_metrics(
    records: Iterable[M13EvaluationRecord],
    scenarios: Iterable[M13EvaluationScenario],
) -> M13EvaluationMetrics:
    """Aggregate only frozen semantic expectations from compact records."""

    checked = _checked_records(records)
    scenario_by_id = _checked_scenarios(scenarios)
    if any(record.scenario_id not in scenario_by_id for record in checked):
        raise ValueError("every record must reference a supplied scenario")

    def expected(record: M13EvaluationRecord) -> bool:
        scenario = scenario_by_id[record.scenario_id]
        selected = record.to_dict()["deterministic_signature"].get("selected_strategy")
        return (
            record.semantic_outcome == scenario.expected_outcome
            and record.failure_category == scenario.expected_failure_category
            and selected == scenario.expected_selected_strategy
        )

    interpreted = tuple(
        record for record in checked
        if record.baseline is not M13Baseline.M12_DETERMINISTIC
        and not (record.failure_category or "").startswith(("provider:", "interpreter:"))
    )
    validation = tuple(
        record for record in interpreted
        if not (record.failure_category or "").startswith("validation:")
    )
    rejection = tuple(
        record for record in checked
        if (record.failure_category or "").startswith("validation:")
    )
    failures = tuple(record for record in checked if record.failure_category is not None)

    groups: dict[tuple[str, M13Baseline], list[M13EvaluationRecord]] = {}
    for record in checked:
        groups.setdefault((record.scenario_id, record.baseline), []).append(record)
    repeat_groups = tuple(group for group in groups.values() if len(group) > 1)

    pairs: list[tuple[M13EvaluationRecord, M13EvaluationRecord]] = []
    for scenario_id in scenario_by_id:
        first = groups.get((scenario_id, M13Baseline.M12_DETERMINISTIC), [])
        third = groups.get((scenario_id, M13Baseline.FULL_PIPELINE), [])
        if first and third:
            pairs.extend((left, right) for left in first for right in third)

    return M13EvaluationMetrics(
        proposal_validity=_rate(sum(expected(record) for record in interpreted), len(interpreted)),
        validation_correctness=_rate(sum(expected(record) for record in validation), len(validation)),
        validation_rejection_correctness=_rate(sum(expected(record) for record in rejection), len(rejection)),
        decision_consistency=_rate(
            sum(
                left.semantic_outcome == right.semantic_outcome
                and left.to_dict()["deterministic_signature"].get("selected_strategy")
                == right.to_dict()["deterministic_signature"].get("selected_strategy")
                for left, right in pairs
            ),
            len(pairs),
        ),
        evidence_consistency=_rate(
            sum(all(item.evidence_signature == group[0].evidence_signature for item in group) for group in repeat_groups),
            len(repeat_groups),
        ),
        deterministic_repeatability=_rate(
            sum(all(item.deterministic_signature == group[0].deterministic_signature for item in group) for group in repeat_groups),
            len(repeat_groups),
        ),
        failure_boundary_preservation=_rate(sum(expected(record) for record in failures), len(failures)),
    )
