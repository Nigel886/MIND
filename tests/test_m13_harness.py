"""Tests for the M13 local-only controlled evaluation harness."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from evaluation.tasks.m13_fixtures import M13Baseline, get_m13_evaluation_scenarios
from evaluation.validation.m13_harness import M13EvaluationHarness, M13EvaluationRecord
from src.core.meta_engine import MetaInferenceEngine


def _scenarios() -> dict[str, object]:
    return {item.scenario_id: item for item in get_m13_evaluation_scenarios()}


class M13HarnessTests(unittest.TestCase):
    def test_fixture_baselines_produce_their_frozen_semantics(self) -> None:
        harness = M13EvaluationHarness()

        for scenario in get_m13_evaluation_scenarios():
            record = harness.execute(scenario)
            self.assertEqual(scenario.expected_outcome, record.semantic_outcome)
            self.assertEqual(scenario.expected_failure_category, record.failure_category)
            if scenario.expected_selected_strategy is not None:
                self.assertEqual(
                    scenario.expected_selected_strategy,
                    record.to_dict()["deterministic_signature"]["selected_strategy"],
                )

    def test_m12_baseline_matches_successful_full_pipeline_selection(self) -> None:
        scenario = _scenarios()["m13_successful_complete_pipeline"]
        harness = M13EvaluationHarness()

        baseline_a = harness.execute(scenario, M13Baseline.M12_DETERMINISTIC)
        baseline_c = harness.execute(scenario)

        self.assertEqual("selected", baseline_a.semantic_outcome)
        self.assertEqual("selected", baseline_c.semantic_outcome)
        self.assertEqual(
            baseline_a.to_dict()["deterministic_signature"]["selected_strategy"],
            baseline_c.to_dict()["deterministic_signature"]["selected_strategy"],
        )

    def test_provider_failure_is_not_conflated_with_interpreter_or_validation_failure(self) -> None:
        record = M13EvaluationHarness().execute(_scenarios()["m13_provider_failure_propagation"])

        self.assertEqual("provider:timeout", record.failure_category)
        self.assertEqual(({"owner": "provider", "category": "timeout"},), record.evidence_signature)

    def test_snapshot_stale_and_task_conflict_do_not_invoke_engine(self) -> None:
        harness = M13EvaluationHarness()
        scenarios = _scenarios()
        with patch.object(
            MetaInferenceEngine,
            "select",
            side_effect=AssertionError("engine must not be called"),
        ) as select:
            stale = harness.execute(scenarios["m13_snapshot_stale_rejection"])
            conflict = harness.execute(scenarios["m13_task_requirement_conflict"])

        self.assertEqual("integration:snapshot_stale", stale.failure_category)
        self.assertEqual("integration:task_requirement_conflict", conflict.failure_category)
        self.assertEqual(0, select.call_count)

    def test_repeated_execution_is_semantically_stable_and_records_round_trip(self) -> None:
        scenario = _scenarios()["m13_successful_complete_pipeline"]
        records = M13EvaluationHarness().execute_repeated(scenario, 3)

        self.assertEqual((records[0], records[0], records[0]), records)
        self.assertEqual(records[0], M13EvaluationRecord.from_dict(records[0].to_dict()))
