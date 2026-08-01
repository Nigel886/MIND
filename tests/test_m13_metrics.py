"""Tests for M13 protocol-scoped, non-performance metric aggregation."""

from __future__ import annotations

import unittest

from evaluation.tasks.m13_fixtures import M13Baseline, get_m13_evaluation_scenarios
from evaluation.validation.m13_harness import M13EvaluationHarness
from evaluation.validation.m13_metrics import M13EvaluationMetrics, calculate_m13_metrics


class M13MetricTests(unittest.TestCase):
    def test_metrics_aggregate_frozen_semantics_deterministically(self) -> None:
        scenarios = get_m13_evaluation_scenarios()
        harness = M13EvaluationHarness()
        records = [harness.execute(item) for item in scenarios]
        successful = next(item for item in scenarios if item.expected_selected_strategy is not None)
        records.extend(harness.execute_repeated(successful, 3))
        records.extend(harness.execute_repeated(successful, 3, M13Baseline.M12_DETERMINISTIC))

        first = calculate_m13_metrics(records, scenarios)
        second = calculate_m13_metrics(records, scenarios)

        self.assertEqual(first, second)
        self.assertEqual(1.0, first.proposal_validity)
        self.assertEqual(1.0, first.validation_rejection_correctness)
        self.assertEqual(1.0, first.decision_consistency)
        self.assertEqual(1.0, first.deterministic_repeatability)
        self.assertEqual(first, M13EvaluationMetrics.from_dict(first.to_dict()))

    def test_metric_model_rejects_performance_style_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            M13EvaluationMetrics(1.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
