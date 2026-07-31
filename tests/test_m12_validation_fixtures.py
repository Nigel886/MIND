"""Correctness tests for frozen, non-executing M12 validation fixtures."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from evaluation.tasks import get_m12_validation_scenarios
from evaluation.tasks.evaluation_task import EvaluationScenario
from evaluation.tasks.fixtures import M12_SCENARIO_ORDER
from src.core.meta_inference import MetaInferenceDecisionStatus


class M12ValidationFixtureTest(unittest.TestCase):
    def test_required_scenarios_have_frozen_order_and_count(self) -> None:
        scenarios = get_m12_validation_scenarios()

        self.assertIsInstance(scenarios, tuple)
        self.assertEqual(tuple(item.name for item in scenarios), M12_SCENARIO_ORDER)
        self.assertEqual(len(scenarios), 8)
        self.assertTrue(all(isinstance(item, EvaluationScenario) for item in scenarios))

    def test_decision_scenarios_preserve_expected_semantics(self) -> None:
        scenarios = {item.name: item for item in get_m12_validation_scenarios()}

        self.assertEqual(
            scenarios["m12_unique_capability_match"].expected_outcome,
            MetaInferenceDecisionStatus.SELECTED.value,
        )
        self.assertEqual(
            scenarios["m12_unique_capability_match"].to_dict()["metadata"],
            {
                "protocol_version": "M12-v1",
                "baseline_scope": ["A", "B", "C"],
                "expected_selected_strategy": "calculator_strategy",
                "registry_descriptors": [
                    {"name": "calculator_strategy", "capabilities": ["calculator"]},
                ],
            },
        )
        self.assertEqual(
            scenarios["m12_unavailable_capability"].expected_outcome,
            MetaInferenceDecisionStatus.UNAVAILABLE.value,
        )
        self.assertEqual(
            scenarios["m12_ambiguous_capability_match"].expected_outcome,
            MetaInferenceDecisionStatus.REJECTED.value,
        )
        self.assertEqual(
            scenarios["m12_evidence_consistency"].to_dict()["metadata"]["ignore_fields"],
            ["uuid", "timestamp"],
        )

    def test_m8_compatibility_scenarios_preserve_frozen_inputs(self) -> None:
        scenarios = {item.name: item for item in get_m12_validation_scenarios()}

        self.assertEqual(
            scenarios["m12_m8_direct_task"].expected_outcome,
            "completed",
        )
        self.assertEqual(
            scenarios["m12_m8_calculator_task"].evaluation_task.task.to_dict()["input"],
            {"operation": "multiply", "operands": [17, 23], "expected_answer": 391},
        )
        self.assertEqual(
            scenarios["m12_m8_unsupported_task"].expected_outcome,
            "unsupported_task",
        )
        self.assertEqual(
            scenarios["m12_m8_controlled_failure"].to_dict()["metadata"],
            {
                "protocol_version": "M12-v1",
                "baseline_scope": ["A", "B", "C"],
                "comparison_scope": "failure_semantics",
                "tool_configuration": "without_calculator",
            },
        )

    def test_repeated_calls_are_equal_isolated_and_immutable(self) -> None:
        first = get_m12_validation_scenarios()
        second = get_m12_validation_scenarios()

        self.assertEqual(first, second)
        self.assertIsNot(first[0], second[0])
        self.assertIsNot(first[0].evaluation_task.task, second[0].evaluation_task.task)
        with self.assertRaises(FrozenInstanceError):
            first[0].name = "changed"
        with self.assertRaises(TypeError):
            first[0].metadata["protocol_version"] = "changed"

    def test_serialization_round_trip_is_deterministic_and_isolated(self) -> None:
        scenarios = get_m12_validation_scenarios()
        serialized = tuple(item.to_dict() for item in scenarios)
        repeated = tuple(item.to_dict() for item in get_m12_validation_scenarios())

        self.assertEqual(serialized, repeated)
        serialized[0]["metadata"]["registry_descriptors"][0]["name"] = "changed"
        self.assertEqual(
            scenarios[0].to_dict()["metadata"]["registry_descriptors"][0]["name"],
            "calculator_strategy",
        )
        restored = tuple(EvaluationScenario.from_dict(item) for item in repeated)
        self.assertEqual(restored, scenarios)


if __name__ == "__main__":
    unittest.main()
