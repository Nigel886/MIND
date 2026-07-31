"""Tests for frozen, non-executing M10 evaluation scenario fixtures."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from evaluation.tasks import get_default_evaluation_scenarios
from evaluation.tasks.evaluation_task import EvaluationScenario
from evaluation.tasks.scenarios import SCENARIO_ORDER


class EvaluationFixtureTest(unittest.TestCase):
    def test_all_required_scenarios_exist_in_frozen_order(self) -> None:
        scenarios = get_default_evaluation_scenarios()

        self.assertIsInstance(scenarios, tuple)
        self.assertEqual(tuple(scenario.name for scenario in scenarios), SCENARIO_ORDER)
        self.assertEqual(len(scenarios), 10)
        self.assertTrue(all(isinstance(scenario, EvaluationScenario) for scenario in scenarios))

    def test_required_payload_and_metadata_are_exact(self) -> None:
        scenarios = {scenario.name: scenario for scenario in get_default_evaluation_scenarios()}

        self.assertEqual(
            scenarios["calculator_success"].evaluation_task.task.to_dict()["input"],
            {"operation": "multiply", "operands": [17, 23], "expected_answer": 391},
        )
        self.assertEqual(
            scenarios["unique_strategy_match"].evaluation_task.task.to_dict()["metadata"],
            {"required_inference_capabilities": ["incremental"]},
        )
        self.assertEqual(scenarios["unavailable_strategy"].expected_outcome, "UNAVAILABLE")
        self.assertEqual(scenarios["ambiguous_strategy"].expected_outcome, "REJECTED")
        self.assertEqual(scenarios["m8_compatibility_tool_failure"].to_dict()["metadata"], {"tool_configuration": "without_calculator"})
        self.assertEqual(scenarios["m8_compatibility_bounded_execution"].to_dict()["metadata"], {"max_cycles": 0})

    def test_repeated_calls_are_equal_but_isolated_and_immutable(self) -> None:
        first = get_default_evaluation_scenarios()
        second = get_default_evaluation_scenarios()

        self.assertEqual(first, second)
        self.assertIsNot(first[0], second[0])
        self.assertIsNot(first[0].evaluation_task.task, second[0].evaluation_task.task)
        with self.assertRaises(FrozenInstanceError):
            first[0].name = "changed"
        with self.assertRaises(TypeError):
            first[2].evaluation_task.task.metadata["required_inference_capabilities"] = ()

    def test_serialization_is_deterministic_and_has_no_mutable_aliases(self) -> None:
        first = get_default_evaluation_scenarios()
        serialized = tuple(scenario.to_dict() for scenario in first)
        second_serialized = tuple(
            scenario.to_dict() for scenario in get_default_evaluation_scenarios()
        )

        self.assertEqual(serialized, second_serialized)
        serialized[0]["evaluation_task"]["task"]["input"]["value"] = "changed"
        self.assertEqual(first[0].evaluation_task.task.to_dict()["input"]["value"], "ready")
        restored = tuple(EvaluationScenario.from_dict(item) for item in second_serialized)
        self.assertEqual(restored, first)


if __name__ == "__main__":
    unittest.main()
