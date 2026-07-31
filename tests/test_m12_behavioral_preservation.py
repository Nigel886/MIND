"""Tests for the bounded M12 M8-behavior preservation evaluation only."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from evaluation.validation import (
    M12BehavioralPreservationResult,
    evaluate_m12_behavioral_preservation,
)


class M12BehavioralPreservationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = evaluate_m12_behavioral_preservation()

    def test_compares_only_the_four_frozen_m8_compatibility_scenarios(self) -> None:
        self.assertEqual(
            self.result.scenario_ids,
            (
                "m12_m8_direct_task",
                "m12_m8_calculator_task",
                "m12_m8_unsupported_task",
                "m12_m8_controlled_failure",
            ),
        )
        self.assertEqual(self.result.repetitions, 3)
        self.assertEqual(len(self.result.m8_records), 12)
        self.assertEqual(len(self.result.meta_inference_records), 12)
        self.assertTrue(all(item.baseline_name == "m8_goal_directed_agent" for item in self.result.m8_records))
        self.assertTrue(all(item.baseline_name == "m9_meta_inference_agent" for item in self.result.meta_inference_records))

    def test_outcome_and_failure_semantics_are_preserved(self) -> None:
        metrics = self.result.metrics

        self.assertEqual(metrics.outcome_preservation, 1.0)
        self.assertEqual(metrics.failure_semantic_preservation, 1.0)
        m8_failures = [item for item in self.result.m8_records if item.failure_signature is not None]
        meta_failures = [item for item in self.result.meta_inference_records if item.failure_signature is not None]
        self.assertEqual(len(m8_failures), 6)
        self.assertEqual(
            tuple(item.failure_signature["termination_reason"] for item in m8_failures),
            tuple(item.failure_signature["termination_reason"] for item in meta_failures),
        )

    def test_repeated_execution_has_stable_semantic_signatures(self) -> None:
        repeated = evaluate_m12_behavioral_preservation()

        self.assertEqual(self.result.metrics.deterministic_execution_consistency, 1.0)
        self.assertEqual(repeated, self.result)
        self.assertEqual(
            tuple(item.outcome_signature for item in repeated.meta_inference_records),
            tuple(item.outcome_signature for item in self.result.meta_inference_records),
        )

    def test_records_are_compact_immutable_and_serializable(self) -> None:
        serialized = self.result.to_dict()
        restored = M12BehavioralPreservationResult.from_dict(serialized)

        self.assertEqual(restored, self.result)
        with self.assertRaises(FrozenInstanceError):
            self.result.repetitions = 4
        with self.assertRaises(TypeError):
            self.result.m8_records[0].outcome_signature["status"] = "changed"
        self.assertNotIn("RuntimeState", str(serialized))
        self.assertNotIn("task_id", str(serialized))
        self.assertNotIn("timestamp", str(serialized))

    def test_input_validation_rejects_invalid_repetition_counts(self) -> None:
        with self.assertRaises(TypeError):
            evaluate_m12_behavioral_preservation(True)
        with self.assertRaises(ValueError):
            evaluate_m12_behavioral_preservation(0)


if __name__ == "__main__":
    unittest.main()
