"""Tests for the bounded M12 decision-semantics evaluation only."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from evaluation.tasks import get_m12_validation_scenarios
from evaluation.validation import (
    M12DecisionEvaluationResult,
    evaluate_m12_decision_semantics,
)


class M12DecisionEvaluationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = evaluate_m12_decision_semantics()

    def test_uses_only_frozen_decision_scenarios_with_fixed_repetitions(self) -> None:
        self.assertEqual(
            self.result.scenario_ids,
            (
                "m12_unique_capability_match",
                "m12_unavailable_capability",
                "m12_ambiguous_capability_match",
                "m12_evidence_consistency",
            ),
        )
        self.assertEqual(self.result.repetitions, 3)
        self.assertEqual(len(self.result.fixed_strategy_records), 12)
        self.assertEqual(len(self.result.full_mind_records), 12)
        fixture_names = {item.name for item in get_m12_validation_scenarios()}
        self.assertTrue(set(self.result.scenario_ids).issubset(fixture_names))

    def test_full_mind_decision_metrics_match_frozen_expected_semantics(self) -> None:
        metrics = self.result.metrics

        self.assertEqual(metrics.selection_correctness, 1.0)
        self.assertEqual(metrics.unavailable_correctness, 1.0)
        self.assertEqual(metrics.ambiguity_rejection_correctness, 1.0)
        self.assertEqual(metrics.decision_semantic_consistency, 1.0)
        self.assertEqual(metrics.evidence_consistency, 1.0)

    def test_fixed_baseline_is_static_and_does_not_mask_failure_semantics(self) -> None:
        fixed = self.result.fixed_strategy_records
        full_mind = self.result.full_mind_records

        self.assertTrue(all(record.decision_status == "selected" for record in fixed))
        self.assertTrue(all(record.selected_strategy == "fixed_strategy" for record in fixed))
        unavailable = [record for record in full_mind if record.scenario_id == "m12_unavailable_capability"]
        ambiguous = [record for record in full_mind if record.scenario_id == "m12_ambiguous_capability_match"]
        self.assertTrue(all(record.decision_status == "unavailable" for record in unavailable))
        self.assertTrue(all(record.decision_status == "rejected" for record in ambiguous))

    def test_repeated_evaluation_is_semantically_deterministic(self) -> None:
        repeated = evaluate_m12_decision_semantics()

        self.assertIsNot(repeated, self.result)
        self.assertEqual(repeated, self.result)
        self.assertEqual(
            tuple(record.to_dict() for record in repeated.full_mind_records),
            tuple(record.to_dict() for record in self.result.full_mind_records),
        )

    def test_result_is_immutable_serializable_and_compact(self) -> None:
        serialized = self.result.to_dict()
        restored = M12DecisionEvaluationResult.from_dict(serialized)

        self.assertEqual(restored, self.result)
        with self.assertRaises(FrozenInstanceError):
            self.result.repetitions = 4
        with self.assertRaises(TypeError):
            self.result.full_mind_records[0].evidence_signature[0]["status"] = "changed"
        self.assertNotIn("RuntimeState", str(serialized))
        self.assertNotIn("task_id", str(serialized))
        self.assertNotIn("timestamp", str(serialized))

    def test_input_validation_rejects_invalid_repetitions_and_incomplete_scope(self) -> None:
        with self.assertRaises(TypeError):
            evaluate_m12_decision_semantics(True)
        with self.assertRaises(ValueError):
            evaluate_m12_decision_semantics(0)
        with self.assertRaises(ValueError):
            evaluate_m12_decision_semantics(
                scenarios=get_m12_validation_scenarios()[:3],
            )


if __name__ == "__main__":
    unittest.main()
