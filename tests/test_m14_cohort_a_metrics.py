"""Tests for descriptive M14 Cohort A metrics."""

from __future__ import annotations

import unittest

from evaluation.tasks.m14_cohort_a_fixtures import get_m14_cohort_a_fixtures
from src.evaluation.cohort_a import CohortAResultRecord, aggregate_cohort_a_metrics
from src.evaluation.cohort_a_runner import CohortARunner


class CohortAMetricTests(unittest.TestCase):
    def test_aggregation_is_correct_for_deterministic_records(self) -> None:
        records = CohortARunner(repetitions=1).run(get_m14_cohort_a_fixtures()[:2])
        metrics = aggregate_cohort_a_metrics(records)

        self.assertEqual(metrics.total_runs, 4)
        self.assertEqual(metrics.outcome_counts["success"], 4)
        self.assertEqual(metrics.total_tool_calls, 2)
        self.assertEqual(metrics.success_rate, 1.0)

    def test_metric_aggregation_is_deterministic(self) -> None:
        fixtures = get_m14_cohort_a_fixtures()[:2]
        first = CohortARunner(repetitions=2).metrics(CohortARunner(repetitions=2).run(fixtures))
        second = CohortARunner(repetitions=2).metrics(CohortARunner(repetitions=2).run(fixtures))

        self.assertEqual(first.to_dict(), second.to_dict())

    def test_result_record_serialization_is_compact_and_round_trips(self) -> None:
        record = CohortARunner(repetitions=1).run(get_m14_cohort_a_fixtures()[:1])[0]

        restored = CohortAResultRecord.from_dict(record.to_dict())

        self.assertEqual(restored, record)
        self.assertNotIn("runtime_state", record.to_dict()["trace_summary"])
        self.assertNotIn("belief", record.to_dict()["trace_summary"])

    def test_result_record_rejects_private_trace_fields(self) -> None:
        record = CohortARunner(repetitions=1).run(get_m14_cohort_a_fixtures()[:1])[0]
        with self.assertRaises(ValueError):
            CohortAResultRecord(
                task_id=record.task_id,
                baseline_id=record.baseline_id,
                repeat_index=record.repeat_index,
                outcome=record.outcome,
                trace_summary={"hidden_reasoning": "not permitted"},
                resource_usage={},
                configuration_hash=record.configuration_hash,
            )

    def test_empty_metrics_are_deterministic(self) -> None:
        metrics = aggregate_cohort_a_metrics(())

        self.assertEqual(metrics.total_runs, 0)
        self.assertEqual(metrics.success_rate, 0.0)
        self.assertEqual(metrics.to_dict()["outcome_counts"], {})


if __name__ == "__main__":
    unittest.main()
