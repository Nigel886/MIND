"""Tests for the frozen M10 comparative experiment protocol execution."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from evaluation.results.comparative_experiments import (
    ComparativeExperimentResult,
    execute_comparative_experiments,
)
from evaluation.tasks.scenarios import SCENARIO_ORDER


class ComparativeExperimentsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.experiments = execute_comparative_experiments()

    def test_all_frozen_scenarios_execute_with_three_repetitions(self) -> None:
        self.assertEqual(
            tuple(experiment.scenario_name for experiment in self.experiments),
            SCENARIO_ORDER,
        )
        self.assertTrue(all(experiment.repetitions == 3 for experiment in self.experiments))
        self.assertTrue(all(len(experiment.baseline_results) == 6 for experiment in self.experiments))
        self.assertTrue(all(experiment.metrics.total_runs == 6 for experiment in self.experiments))

    def test_baseline_separation_and_frozen_failure_paths(self) -> None:
        by_name = {experiment.scenario_name: experiment for experiment in self.experiments}
        unique = by_name["unique_strategy_match"]
        unavailable = by_name["unavailable_strategy"]
        ambiguous = by_name["ambiguous_strategy"]

        self.assertTrue(all(run.result.selected_strategy is None for run in unique.baseline_results if run.result.baseline_name == "baseline_a"))
        self.assertTrue(all(run.result.selected_strategy == "incremental" for run in unique.baseline_results if run.result.baseline_name == "baseline_b"))
        self.assertEqual(unavailable.metrics.unavailable_correctness, 1.0)
        self.assertEqual(ambiguous.metrics.ambiguity_rejection_correctness, 1.0)

    def test_repetitions_are_semantically_deterministic_without_state_leakage(self) -> None:
        repeated = execute_comparative_experiments()

        self.assertIsNot(self.experiments[0], repeated[0])
        self.assertEqual(
            tuple(item.semantic_consistency for item in self.experiments),
            tuple(item.semantic_consistency for item in repeated),
        )
        self.assertTrue(all(all(item.semantic_consistency.values()) for item in repeated))
        first_signatures = tuple(
            tuple(run.result.semantic_signature for run in item.baseline_results)
            for item in self.experiments
        )
        second_signatures = tuple(
            tuple(run.result.semantic_signature for run in item.baseline_results)
            for item in repeated
        )
        self.assertEqual(first_signatures, second_signatures)

    def test_result_is_immutable_serializable_and_compact(self) -> None:
        result = self.experiments[0]
        serialized = result.to_dict()
        restored = ComparativeExperimentResult.from_dict(serialized)

        self.assertEqual(restored, result)
        with self.assertRaises(FrozenInstanceError):
            result.repetitions = 4
        with self.assertRaises(TypeError):
            result.semantic_consistency["baseline_a"] = False
        self.assertNotIn("final_state", str(serialized))
        self.assertNotIn("RuntimeState", str(serialized))

    def test_repetition_validation(self) -> None:
        with self.assertRaises(TypeError):
            execute_comparative_experiments(True)
        with self.assertRaises(ValueError):
            execute_comparative_experiments(2)


if __name__ == "__main__":
    unittest.main()
