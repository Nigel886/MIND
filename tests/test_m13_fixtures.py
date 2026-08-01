"""Tests for frozen M13 evaluation scenario definitions."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from evaluation.tasks.m13_fixtures import M13EvaluationScenario, get_m13_evaluation_scenarios


class M13FixtureTests(unittest.TestCase):
    def test_exactly_eight_frozen_scenarios_are_ordered(self) -> None:
        scenarios = get_m13_evaluation_scenarios()

        self.assertEqual(8, len(scenarios))
        self.assertEqual(
            (
                "m13_valid_task_interpretation", "m13_malformed_provider_payload",
                "m13_unsupported_capability", "m13_invalid_constraint_validation_rejection",
                "m13_successful_complete_pipeline", "m13_provider_failure_propagation",
                "m13_snapshot_stale_rejection", "m13_task_requirement_conflict",
            ),
            tuple(item.scenario_id for item in scenarios),
        )
        self.assertEqual("validation:invalid_constraint", scenarios[3].expected_failure_category)

    def test_serialization_round_trip_and_fresh_reconstruction_are_deterministic(self) -> None:
        first = get_m13_evaluation_scenarios()
        second = get_m13_evaluation_scenarios()
        restored = tuple(M13EvaluationScenario.from_dict(item.to_dict()) for item in first)

        self.assertEqual(first, second)
        self.assertEqual(first, restored)
        self.assertIsNot(first[0], second[0])

    def test_scenarios_are_immutable_and_contain_no_secret_metadata(self) -> None:
        scenario = get_m13_evaluation_scenarios()[0]

        with self.assertRaises(FrozenInstanceError):
            scenario.scenario_id = "changed"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            scenario.metadata["new"] = "value"  # type: ignore[index]
        self.assertNotIn("api_key", str(scenario.to_dict()).lower())
