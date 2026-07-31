"""Tests for pure deterministic M10 evaluation metrics."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from evaluation.metrics.evaluation_metrics import (
    EvaluationMetrics,
    calculate_ambiguity_rejection_correctness,
    calculate_determinism,
    calculate_evidence_consistency,
    calculate_failure_rate,
    calculate_metrics,
    calculate_selection_accuracy,
    calculate_success_rate,
    calculate_unavailable_correctness,
)
from evaluation.runner.evaluation_runner import EvaluationRunResult


def _result(
    scenario_name: str = "direct_success",
    baseline_name: str = "baseline_b",
    success: bool = True,
    status: str = "completed",
    reason: str = "goal_satisfied",
    selected: str | None = None,
    evidence: tuple[dict, ...] = (),
) -> EvaluationRunResult:
    return EvaluationRunResult(
        scenario_name,
        baseline_name,
        success,
        status,
        reason,
        selected,
        evidence,
        0.01,
    )


class EvaluationMetricsTest(unittest.TestCase):
    def test_success_failure_and_serialization(self) -> None:
        results = (_result(), _result(success=False, status="failed", reason="policy_failure"))
        metrics = calculate_metrics(results)

        self.assertEqual((metrics.total_runs, metrics.successful_runs, metrics.failed_runs), (2, 1, 1))
        self.assertEqual((metrics.success_rate, metrics.failure_rate), (0.5, 0.5))
        self.assertEqual(EvaluationMetrics.from_dict(metrics.to_dict()), metrics)
        with self.assertRaises(FrozenInstanceError):
            metrics.total_runs = 3

    def test_meta_inference_correctness_metrics(self) -> None:
        selected = _result(
            "unique_strategy_match",
            selected="incremental",
            evidence=({"type": "meta_inference", "status": "selected", "selected_strategy": "incremental"},),
        )
        unavailable = _result(
            "unavailable_strategy", success=False, status="failed", reason="policy_failure",
            evidence=({"type": "meta_inference", "status": "unavailable", "selected_strategy": None},),
        )
        ambiguous = _result(
            "ambiguous_strategy", success=False, status="failed", reason="policy_failure",
            evidence=({"type": "meta_inference", "status": "rejected", "selected_strategy": None},),
        )
        results = (selected, unavailable, ambiguous)

        self.assertEqual(calculate_selection_accuracy(results), 1.0)
        self.assertEqual(calculate_unavailable_correctness(results), 1.0)
        self.assertEqual(calculate_ambiguity_rejection_correctness(results), 1.0)

    def test_determinism_and_evidence_consistency(self) -> None:
        first = _result(evidence=({"type": "policy", "action": "produce_answer"},))
        second = _result(evidence=({"type": "policy", "action": "produce_answer"},))
        changed = _result(evidence=({"type": "policy", "action": "fail_task"},))

        self.assertEqual(calculate_determinism((first, second)), 1.0)
        self.assertEqual(calculate_evidence_consistency((first, second)), 1.0)
        self.assertEqual(calculate_determinism((first, changed)), 0.0)
        self.assertEqual(calculate_evidence_consistency((first, changed)), 0.0)

    def test_empty_input_and_validation(self) -> None:
        self.assertEqual(calculate_success_rate(()), 0.0)
        self.assertEqual(calculate_failure_rate(()), 0.0)
        empty = calculate_metrics(())
        self.assertEqual(empty.to_dict(), {
            "total_runs": 0, "successful_runs": 0, "failed_runs": 0,
            "success_rate": 0.0, "failure_rate": 0.0,
            "strategy_selection_correctness": 0.0, "unavailable_correctness": 0.0,
            "ambiguity_rejection_correctness": 0.0, "deterministic_consistency": 0.0,
            "evidence_consistency": 0.0,
        })
        with self.assertRaises(TypeError):
            calculate_metrics(({} ,))
        with self.assertRaises(ValueError):
            EvaluationMetrics(1, 1, 0, 0.5, 0.0, 0, 0, 0, 0, 0)


if __name__ == "__main__":
    unittest.main()
