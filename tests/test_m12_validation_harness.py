"""Correctness tests for the non-analytical M12 validation harness."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from evaluation.tasks import get_m12_validation_scenarios
from evaluation.validation import M12ValidationHarness, M12ValidationRecord
from src.core.meta_inference import MetaInferenceDecisionStatus


class M12ValidationHarnessTest(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = M12ValidationHarness()
        self.scenarios = {
            scenario.name: scenario for scenario in get_m12_validation_scenarios()
        }

    def test_consumes_decision_fixtures_and_returns_compact_records(self) -> None:
        selected = self.harness.run(self.scenarios["m12_unique_capability_match"])
        unavailable = self.harness.run(self.scenarios["m12_unavailable_capability"])
        rejected = self.harness.run(self.scenarios["m12_ambiguous_capability_match"])

        self.assertEqual(selected.scenario_id, "m12_unique_capability_match")
        self.assertEqual(selected.baseline_name, "full_mind_meta_inference")
        self.assertEqual(
            (selected.decision_status, selected.selected_strategy),
            (MetaInferenceDecisionStatus.SELECTED.value, "calculator_strategy"),
        )
        self.assertEqual(unavailable.decision_status, MetaInferenceDecisionStatus.UNAVAILABLE.value)
        self.assertIsNone(unavailable.selected_strategy)
        self.assertEqual(rejected.decision_status, MetaInferenceDecisionStatus.REJECTED.value)
        self.assertEqual(rejected.execution_signature["termination_reason"], "policy_failure")
        self.assertNotIn("final_state", selected.to_dict())
        self.assertNotIn("task_id", selected.to_dict())

    def test_consumes_m8_compatibility_fixtures_without_meta_decisions(self) -> None:
        records = self.harness.run_all(
            tuple(
                self.scenarios[name]
                for name in (
                    "m12_m8_direct_task",
                    "m12_m8_calculator_task",
                    "m12_m8_unsupported_task",
                    "m12_m8_controlled_failure",
                )
            ),
        )

        self.assertEqual(
            tuple(record.execution_signature["status"] for record in records),
            ("completed", "completed", "failed", "failed"),
        )
        self.assertEqual(
            tuple(record.execution_signature["termination_reason"] for record in records),
            ("goal_satisfied", "goal_satisfied", "unsupported_task", "tool_failure"),
        )
        self.assertTrue(all(record.decision_status is None for record in records))
        self.assertTrue(all(record.baseline_name == "m8_goal_directed_agent" for record in records))

    def test_repeated_execution_has_stable_semantic_output(self) -> None:
        scenario = self.scenarios["m12_evidence_consistency"]
        records = self.harness.run_repeated(scenario, 3)

        self.assertEqual(records, (records[0], records[0], records[0]))
        self.assertEqual(records[0].decision_status, MetaInferenceDecisionStatus.SELECTED.value)
        self.assertEqual(records[0].selected_strategy, "calculator_strategy")
        self.assertTrue(any(item["type"] == "meta_inference" for item in records[0].evidence_signature))

    def test_record_is_immutable_serializable_and_has_no_mutable_aliases(self) -> None:
        record = self.harness.run(self.scenarios["m12_unique_capability_match"])
        serialized = record.to_dict()

        self.assertEqual(M12ValidationRecord.from_dict(serialized), record)
        with self.assertRaises(FrozenInstanceError):
            record.scenario_id = "changed"
        with self.assertRaises(TypeError):
            record.execution_signature["status"] = "changed"
        serialized["evidence_signature"][0]["status"] = "changed"
        self.assertNotEqual(serialized["evidence_signature"], record.to_dict()["evidence_signature"])

    def test_input_validation_rejects_non_fixture_values(self) -> None:
        scenario = self.scenarios["m12_unique_capability_match"]

        with self.assertRaises(TypeError):
            self.harness.run({}, 1)
        with self.assertRaises(TypeError):
            self.harness.run(scenario, True)
        with self.assertRaises(ValueError):
            self.harness.run(scenario, -1)
        with self.assertRaises(ValueError):
            self.harness.run_repeated(scenario, 0)
        with self.assertRaises(TypeError):
            self.harness.run_all([scenario, {}])


if __name__ == "__main__":
    unittest.main()
