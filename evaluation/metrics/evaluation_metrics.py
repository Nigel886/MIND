"""Pure deterministic metrics for M10 compact evaluation summaries."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
from typing import Any, Iterable

from evaluation.runner.evaluation_runner import EvaluationRunResult


_META_BASELINE = "baseline_b"
_UNIQUE_SCENARIO = "unique_strategy_match"
_UNAVAILABLE_SCENARIO = "unavailable_strategy"
_AMBIGUOUS_SCENARIO = "ambiguous_strategy"


def _results(value: Iterable[EvaluationRunResult]) -> tuple[EvaluationRunResult, ...]:
    """Validate a finite public collection without executing anything."""

    if isinstance(value, (str, bytes)):
        raise TypeError("results must be an iterable of EvaluationRunResult")
    try:
        results = tuple(value)
    except TypeError as error:
        raise TypeError("results must be an iterable of EvaluationRunResult") from error
    if any(not isinstance(result, EvaluationRunResult) for result in results):
        raise TypeError("results must contain only EvaluationRunResult values")
    return results


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _meta_status(result: EvaluationRunResult) -> str | None:
    for evidence in result.evidence_summary:
        if evidence.get("type") == "meta_inference":
            return evidence.get("status")
    return None


def _scenario_results(
    results: tuple[EvaluationRunResult, ...],
    scenario_name: str,
) -> tuple[EvaluationRunResult, ...]:
    return tuple(
        result
        for result in results
        if result.scenario_name == scenario_name
        and result.baseline_name == _META_BASELINE
    )


def calculate_success_rate(results: Iterable[EvaluationRunResult]) -> float:
    """Return the fraction of compact runs marked successful, or 0.0 when empty."""

    checked = _results(results)
    return _rate(sum(result.success for result in checked), len(checked))


def calculate_failure_rate(results: Iterable[EvaluationRunResult]) -> float:
    """Return the fraction of compact runs not marked successful, or 0.0 when empty."""

    checked = _results(results)
    return _rate(sum(not result.success for result in checked), len(checked))


def calculate_selection_accuracy(results: Iterable[EvaluationRunResult]) -> float:
    """Measure selected-strategy evidence for unique-match Baseline B runs."""

    checked = _scenario_results(_results(results), _UNIQUE_SCENARIO)
    return _rate(
        sum(
            _meta_status(result) == "selected"
            and result.selected_strategy is not None
            for result in checked
        ),
        len(checked),
    )


def calculate_unavailable_correctness(results: Iterable[EvaluationRunResult]) -> float:
    """Measure explicit unavailable failure semantics for Baseline B runs."""

    checked = _scenario_results(_results(results), _UNAVAILABLE_SCENARIO)
    return _rate(
        sum(
            _meta_status(result) == "unavailable"
            and result.agent_status == "failed"
            and result.termination_reason == "policy_failure"
            and result.selected_strategy is None
            for result in checked
        ),
        len(checked),
    )


def calculate_ambiguity_rejection_correctness(
    results: Iterable[EvaluationRunResult],
) -> float:
    """Measure explicit ambiguity rejection semantics for Baseline B runs."""

    checked = _scenario_results(_results(results), _AMBIGUOUS_SCENARIO)
    return _rate(
        sum(
            _meta_status(result) == "rejected"
            and result.agent_status == "failed"
            and result.termination_reason == "policy_failure"
            and result.selected_strategy is None
            for result in checked
        ),
        len(checked),
    )


def _consistency(
    results: tuple[EvaluationRunResult, ...],
    attribute: str,
) -> float:
    groups: dict[tuple[str, str], list[Any]] = {}
    for result in results:
        groups.setdefault((result.scenario_name, result.baseline_name), []).append(
            getattr(result, attribute),
        )
    return _rate(sum(all(value == values[0] for value in values) for values in groups.values()), len(groups))


def calculate_determinism(results: Iterable[EvaluationRunResult]) -> float:
    """Return the fraction of scenario/baseline groups with equal semantic signatures."""

    return _consistency(_results(results), "semantic_signature")


def calculate_evidence_consistency(results: Iterable[EvaluationRunResult]) -> float:
    """Return the fraction of scenario/baseline groups with equal evidence summaries."""

    return _consistency(_results(results), "evidence_summary")


@dataclass(frozen=True)
class EvaluationMetrics:
    """Immutable deterministic metrics calculated from compact public summaries."""

    total_runs: int
    successful_runs: int
    failed_runs: int
    success_rate: float
    failure_rate: float
    strategy_selection_correctness: float
    unavailable_correctness: float
    ambiguity_rejection_correctness: float
    deterministic_consistency: float
    evidence_consistency: float

    def __post_init__(self) -> None:
        for value, name in (
            (self.total_runs, "total_runs"),
            (self.successful_runs, "successful_runs"),
            (self.failed_runs, "failed_runs"),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int, not bool")
            if value < 0:
                raise ValueError(f"{name} must not be negative")
        if self.successful_runs + self.failed_runs != self.total_runs:
            raise ValueError("run counts must equal total_runs")
        rates = (
            self.success_rate,
            self.failure_rate,
            self.strategy_selection_correctness,
            self.unavailable_correctness,
            self.ambiguity_rejection_correctness,
            self.deterministic_consistency,
            self.evidence_consistency,
        )
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in rates):
            raise TypeError("metric rates must be numbers, not bools")
        if any(not isfinite(value) or value < 0 or value > 1 for value in rates):
            raise ValueError("metric rates must be finite values from 0.0 through 1.0")
        if not isclose(self.success_rate, _rate(self.successful_runs, self.total_runs)):
            raise ValueError("success_rate does not match run counts")
        if not isclose(self.failure_rate, _rate(self.failed_runs, self.total_runs)):
            raise ValueError("failure_rate does not match run counts")

    def to_dict(self) -> dict[str, Any]:
        """Serialize scalar metric values into a fresh ordinary dictionary."""

        return {
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "strategy_selection_correctness": self.strategy_selection_correctness,
            "unavailable_correctness": self.unavailable_correctness,
            "ambiguity_rejection_correctness": self.ambiguity_rejection_correctness,
            "deterministic_consistency": self.deterministic_consistency,
            "evidence_consistency": self.evidence_consistency,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationMetrics":
        """Reconstruct metrics without coercing malformed serialized data."""

        if not isinstance(data, dict):
            raise TypeError("EvaluationMetrics data must be a dict")
        return cls(**data)


def calculate_metrics(results: Iterable[EvaluationRunResult]) -> EvaluationMetrics:
    """Calculate all approved M10 metrics from existing public run summaries."""

    checked = _results(results)
    successful = sum(result.success for result in checked)
    return EvaluationMetrics(
        total_runs=len(checked),
        successful_runs=successful,
        failed_runs=len(checked) - successful,
        success_rate=calculate_success_rate(checked),
        failure_rate=calculate_failure_rate(checked),
        strategy_selection_correctness=calculate_selection_accuracy(checked),
        unavailable_correctness=calculate_unavailable_correctness(checked),
        ambiguity_rejection_correctness=calculate_ambiguity_rejection_correctness(checked),
        deterministic_consistency=calculate_determinism(checked),
        evidence_consistency=calculate_evidence_consistency(checked),
    )
