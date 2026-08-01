"""Tests for the explicitly invoked M14 Cohort A runner."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from evaluation.tasks.m14_cohort_a_fixtures import get_m14_cohort_a_fixtures
from src.evaluation.cohort_a_runner import (
    CONTROL_BASELINE_ID,
    MIND_BASELINE_ID,
    CohortARunner,
)


class CohortARunnerTests(unittest.TestCase):
    def test_runner_preserves_fixture_baseline_repeat_order(self) -> None:
        fixtures = get_m14_cohort_a_fixtures()[:1]
        records = CohortARunner(repetitions=3).run(fixtures)

        self.assertEqual(
            [(record.task_id, record.baseline_id, record.repeat_index) for record in records],
            [
                ("m14-direct-ready", MIND_BASELINE_ID, 0),
                ("m14-direct-ready", MIND_BASELINE_ID, 1),
                ("m14-direct-ready", MIND_BASELINE_ID, 2),
                ("m14-direct-ready", CONTROL_BASELINE_ID, 0),
                ("m14-direct-ready", CONTROL_BASELINE_ID, 1),
                ("m14-direct-ready", CONTROL_BASELINE_ID, 2),
            ],
        )

    def test_runner_creates_fresh_mind_adapter_and_environment_per_run(self) -> None:
        fixtures = get_m14_cohort_a_fixtures()[:1]
        with patch("src.evaluation.cohort_a_runner.MINDGoalDirectedEvaluationAdapter", wraps=__import__("src.evaluation.cohort_a_runner", fromlist=["MINDGoalDirectedEvaluationAdapter"]).MINDGoalDirectedEvaluationAdapter) as adapter, patch("src.evaluation.cohort_a_runner.DeterministicEvaluationEnvironment", wraps=__import__("src.evaluation.cohort_a_runner", fromlist=["DeterministicEvaluationEnvironment"]).DeterministicEvaluationEnvironment) as environment:
            CohortARunner(repetitions=2).run(fixtures)

        self.assertEqual(adapter.call_count, 2)
        self.assertEqual(environment.call_count, 4)

    def test_runner_records_expected_success_and_failure_semantics(self) -> None:
        fixtures = get_m14_cohort_a_fixtures()
        records = CohortARunner(repetitions=1).run(fixtures)

        by_task = {record.task_id: record for record in records if record.baseline_id == MIND_BASELINE_ID}
        self.assertEqual(by_task["m14-direct-ready"].outcome.outcome_type.value, "success")
        self.assertEqual(by_task["m14-calculator-multiply"].outcome.outcome_type.value, "success")
        self.assertEqual(by_task["m14-unsupported-operation"].outcome.outcome_type.value, "success")
        self.assertEqual(by_task["m14-declared-tool-failure"].outcome.outcome_type.value, "success")

    def test_repeated_runs_have_equal_semantic_signatures(self) -> None:
        fixtures = get_m14_cohort_a_fixtures()[:2]
        records = CohortARunner(repetitions=3).run(fixtures)

        signatures = {}
        for record in records:
            signatures.setdefault((record.task_id, record.baseline_id), set()).add(record.deterministic_signature)
        self.assertTrue(all(len(values) == 1 for values in signatures.values()))

    def test_runner_does_not_run_on_construction(self) -> None:
        runner = CohortARunner()

        self.assertEqual(runner.baseline_order, (MIND_BASELINE_ID, CONTROL_BASELINE_ID))
        self.assertEqual(runner.repetitions, 3)


if __name__ == "__main__":
    unittest.main()
