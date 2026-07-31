"""Controlled M12 decision-semantics evaluation without performance claims."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from evaluation.tasks.evaluation_task import EvaluationScenario
from evaluation.tasks.fixtures import get_m12_validation_scenarios
from evaluation.validation.harness import M12ValidationHarness, M12ValidationRecord
from src.core.meta_inference import MetaInferenceDecisionStatus


_FIXED_BASELINE = "fixed_strategy_selection"
_FULL_MIND_BASELINE = "full_mind_meta_inference"
_FIXED_STRATEGY = "fixed_strategy"
_DECISION_SCENARIO_IDS = (
    "m12_unique_capability_match",
    "m12_unavailable_capability",
    "m12_ambiguous_capability_match",
    "m12_evidence_consistency",
)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("mapping keys must be strings")
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("float values must be finite")
        return value
    raise ValueError("values must be JSON-compatible data")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


@dataclass(frozen=True)
class M12DecisionRecord:
    """One compact decision-only baseline record with no execution objects."""

    scenario_id: str
    baseline_name: str
    decision_status: str
    selected_strategy: str | None
    evidence_signature: tuple[dict[str, Any], ...]

    def __post_init__(self) -> None:
        _text(self.scenario_id, "scenario_id")
        _text(self.baseline_name, "baseline_name")
        try:
            status = MetaInferenceDecisionStatus(self.decision_status)
        except (TypeError, ValueError) as error:
            raise ValueError("decision_status must be a valid Meta-Inference status") from error
        if status is MetaInferenceDecisionStatus.SELECTED:
            _text(self.selected_strategy, "selected_strategy")
        elif self.selected_strategy is not None:
            raise ValueError("non-selected decisions must not include a strategy")
        if not isinstance(self.evidence_signature, (tuple, list)):
            raise TypeError("evidence_signature must be an ordered sequence")
        if any(not isinstance(item, dict) for item in self.evidence_signature):
            raise TypeError("evidence_signature must contain dictionaries")
        object.__setattr__(self, "evidence_signature", _freeze(tuple(self.evidence_signature)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "baseline_name": self.baseline_name,
            "decision_status": self.decision_status,
            "selected_strategy": self.selected_strategy,
            "evidence_signature": _thaw(self.evidence_signature),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "M12DecisionRecord":
        if not isinstance(data, dict):
            raise TypeError("M12DecisionRecord data must be a dict")
        return cls(
            scenario_id=data["scenario_id"],
            baseline_name=data["baseline_name"],
            decision_status=data["decision_status"],
            selected_strategy=data["selected_strategy"],
            evidence_signature=data["evidence_signature"],
        )


@dataclass(frozen=True)
class M12DecisionMetrics:
    """The five frozen M12 decision-semantics metrics and no performance rate."""

    selection_correctness: float
    unavailable_correctness: float
    ambiguity_rejection_correctness: float
    decision_semantic_consistency: float
    evidence_consistency: float

    def __post_init__(self) -> None:
        values = (
            self.selection_correctness,
            self.unavailable_correctness,
            self.ambiguity_rejection_correctness,
            self.decision_semantic_consistency,
            self.evidence_consistency,
        )
        if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in values):
            raise TypeError("metric values must be numbers, not bools")
        if any(not isfinite(item) or item < 0 or item > 1 for item in values):
            raise ValueError("metric values must be finite values from 0.0 through 1.0")

    def to_dict(self) -> dict[str, float]:
        return {
            "selection_correctness": self.selection_correctness,
            "unavailable_correctness": self.unavailable_correctness,
            "ambiguity_rejection_correctness": self.ambiguity_rejection_correctness,
            "decision_semantic_consistency": self.decision_semantic_consistency,
            "evidence_consistency": self.evidence_consistency,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "M12DecisionMetrics":
        if not isinstance(data, dict):
            raise TypeError("M12DecisionMetrics data must be a dict")
        return cls(**data)


@dataclass(frozen=True)
class M12DecisionEvaluationResult:
    """Immutable compact records and calculated semantics for the M12 decision scope."""

    scenario_ids: tuple[str, ...]
    repetitions: int
    fixed_strategy_records: tuple[M12DecisionRecord, ...]
    full_mind_records: tuple[M12DecisionRecord, ...]
    metrics: M12DecisionMetrics

    def __post_init__(self) -> None:
        if not isinstance(self.scenario_ids, (tuple, list)):
            raise TypeError("scenario_ids must be an ordered sequence")
        ids = tuple(self.scenario_ids)
        if ids != _DECISION_SCENARIO_IDS:
            raise ValueError("scenario_ids must match the frozen M12 decision scope")
        if isinstance(self.repetitions, bool) or not isinstance(self.repetitions, int):
            raise TypeError("repetitions must be an int, not bool")
        if self.repetitions < 1:
            raise ValueError("repetitions must be at least one")
        for records, baseline_name, name in (
            (self.fixed_strategy_records, _FIXED_BASELINE, "fixed_strategy_records"),
            (self.full_mind_records, _FULL_MIND_BASELINE, "full_mind_records"),
        ):
            if not isinstance(records, (tuple, list)):
                raise TypeError(f"{name} must be an ordered sequence")
            if len(records) != len(ids) * self.repetitions:
                raise ValueError(f"{name} has an invalid record count")
            if any(not isinstance(record, M12DecisionRecord) for record in records):
                raise TypeError(f"{name} must contain M12DecisionRecord values")
            expected_ids = tuple(item for item in ids for _ in range(self.repetitions))
            if tuple(record.scenario_id for record in records) != expected_ids:
                raise ValueError(f"{name} must be ordered by frozen scenario then repetition")
            if any(record.baseline_name != baseline_name for record in records):
                raise ValueError(f"{name} has an invalid baseline")
        if not isinstance(self.metrics, M12DecisionMetrics):
            raise TypeError("metrics must be an M12DecisionMetrics")
        object.__setattr__(self, "scenario_ids", ids)
        object.__setattr__(self, "fixed_strategy_records", tuple(self.fixed_strategy_records))
        object.__setattr__(self, "full_mind_records", tuple(self.full_mind_records))

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_ids": list(self.scenario_ids),
            "repetitions": self.repetitions,
            "fixed_strategy_records": [item.to_dict() for item in self.fixed_strategy_records],
            "full_mind_records": [item.to_dict() for item in self.full_mind_records],
            "metrics": self.metrics.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "M12DecisionEvaluationResult":
        if not isinstance(data, dict):
            raise TypeError("M12DecisionEvaluationResult data must be a dict")
        return cls(
            scenario_ids=tuple(data["scenario_ids"]),
            repetitions=data["repetitions"],
            fixed_strategy_records=tuple(
                M12DecisionRecord.from_dict(item) for item in data["fixed_strategy_records"]
            ),
            full_mind_records=tuple(
                M12DecisionRecord.from_dict(item) for item in data["full_mind_records"]
            ),
            metrics=M12DecisionMetrics.from_dict(data["metrics"]),
        )


def _decision_record(record: M12ValidationRecord) -> M12DecisionRecord:
    if record.decision_status is None:
        raise ValueError("M12 decision evaluation requires a Meta-Inference decision")
    return M12DecisionRecord(
        scenario_id=record.scenario_id,
        baseline_name=_FULL_MIND_BASELINE,
        decision_status=record.decision_status,
        selected_strategy=record.selected_strategy,
        evidence_signature=tuple(
            dict(item)
            for item in record.evidence_signature
            if item.get("type") == "meta_inference"
        ),
    )


def _fixed_strategy_record(scenario: EvaluationScenario) -> M12DecisionRecord:
    """Return the frozen static baseline without registering or executing a strategy."""

    return M12DecisionRecord(
        scenario_id=scenario.name,
        baseline_name=_FIXED_BASELINE,
        decision_status=MetaInferenceDecisionStatus.SELECTED.value,
        selected_strategy=_FIXED_STRATEGY,
        evidence_signature=(
            {
                "type": "fixed_strategy_selection",
                "status": MetaInferenceDecisionStatus.SELECTED.value,
                "selected_strategy": _FIXED_STRATEGY,
            },
        ),
    )


def _records_for(
    records: tuple[M12DecisionRecord, ...],
    scenario_id: str,
) -> tuple[M12DecisionRecord, ...]:
    return tuple(record for record in records if record.scenario_id == scenario_id)


def _consistent(records: tuple[M12DecisionRecord, ...], attribute: str) -> float:
    groups = tuple(_records_for(records, scenario_id) for scenario_id in _DECISION_SCENARIO_IDS)
    return _rate(
        sum(
            bool(group) and all(getattr(record, attribute) == getattr(group[0], attribute) for record in group)
            for group in groups
        ),
        len(groups),
    )


def _metrics(records: tuple[M12DecisionRecord, ...]) -> M12DecisionMetrics:
    unique = _records_for(records, "m12_unique_capability_match")
    unavailable = _records_for(records, "m12_unavailable_capability")
    ambiguous = _records_for(records, "m12_ambiguous_capability_match")
    return M12DecisionMetrics(
        selection_correctness=_rate(
            sum(
                record.decision_status == MetaInferenceDecisionStatus.SELECTED.value
                and record.selected_strategy == "calculator_strategy"
                for record in unique
            ),
            len(unique),
        ),
        unavailable_correctness=_rate(
            sum(record.decision_status == MetaInferenceDecisionStatus.UNAVAILABLE.value for record in unavailable),
            len(unavailable),
        ),
        ambiguity_rejection_correctness=_rate(
            sum(record.decision_status == MetaInferenceDecisionStatus.REJECTED.value for record in ambiguous),
            len(ambiguous),
        ),
        decision_semantic_consistency=_consistent(records, "decision_status"),
        evidence_consistency=_consistent(records, "evidence_signature"),
    )


def _decision_scenarios(scenarios: Iterable[EvaluationScenario]) -> tuple[EvaluationScenario, ...]:
    checked = tuple(scenarios)
    by_id = {scenario.name: scenario for scenario in checked}
    if tuple(by_id) != tuple(scenario.name for scenario in checked):
        raise ValueError("M12 decision scenarios must not contain duplicate identifiers")
    try:
        selected = tuple(by_id[scenario_id] for scenario_id in _DECISION_SCENARIO_IDS)
    except KeyError as error:
        raise ValueError("M12 decision scenarios are incomplete") from error
    return selected


def evaluate_m12_decision_semantics(
    repetitions: int = 3,
    scenarios: Iterable[EvaluationScenario] | None = None,
) -> M12DecisionEvaluationResult:
    """Execute only the frozen M12 decision scope and calculate its five metrics."""

    if isinstance(repetitions, bool) or not isinstance(repetitions, int):
        raise TypeError("repetitions must be an int, not bool")
    if repetitions < 1:
        raise ValueError("repetitions must be at least one")
    frozen = _decision_scenarios(
        get_m12_validation_scenarios() if scenarios is None else scenarios,
    )
    harness = M12ValidationHarness()
    fixed_records: list[M12DecisionRecord] = []
    full_mind_records: list[M12DecisionRecord] = []
    for scenario in frozen:
        fixed_records.extend(_fixed_strategy_record(scenario) for _ in range(repetitions))
        full_mind_records.extend(
            _decision_record(record)
            for record in harness.run_repeated(scenario, repetitions)
        )
    ordered_full_mind = tuple(full_mind_records)
    return M12DecisionEvaluationResult(
        scenario_ids=_DECISION_SCENARIO_IDS,
        repetitions=repetitions,
        fixed_strategy_records=tuple(fixed_records),
        full_mind_records=ordered_full_mind,
        metrics=_metrics(ordered_full_mind),
    )
