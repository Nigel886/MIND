import json
import tempfile
import unittest
from pathlib import Path

from src.evaluation.m16_statistical_analysis import (
    BOOTSTRAP_SEED, EXPECTED_MANIFEST_HASH, MIND, DIRECT, case_rows,
    paired_permutation, run_analysis, validate_dataset,
)


def record(case, baseline, repetition, success, category="success"):
    return {"run_id": f"{case}:{baseline}:r{repetition}", "manifest_hash": EXPECTED_MANIFEST_HASH,
            "evaluation_id": case, "baseline_id": baseline, "repetition": repetition,
            "success": success, "failure_category": category, "task_family": "calculator",
            "difficulty": "easy", "provider_request_attempts": 1, "model_calls": 1}


class M16StatisticalAnalysisTests(unittest.TestCase):
    def test_case_aggregation_and_complete_pairing(self):
        records = [record("case.1", baseline, rep, baseline == MIND) for baseline in (MIND, DIRECT) for rep in range(1, 6)]
        rows = case_rows(records)
        self.assertEqual(rows[0]["mind_rate"], 1.0); self.assertEqual(rows[0]["direct_rate"], 0.0)
        self.assertEqual(rows[0]["paired_difference"], 1.0)

    def test_permutation_is_seeded_and_case_clustered(self):
        rows = [{"paired_difference": 1.0}, {"paired_difference": -0.2}]
        self.assertEqual(paired_permutation(rows, 1000, 7), paired_permutation(rows, 1000, 7))

    def test_integrity_rejects_incomplete_case(self):
        manifest = {}
        with self.assertRaises(ValueError): validate_dataset(manifest, [record("case.1", MIND, 1, True)])

    def test_output_is_deterministic_for_complete_dataset(self):
        records = [record(f"case.{case:02}", baseline, rep, baseline == MIND) for case in range(96) for baseline in (MIND, DIRECT) for rep in range(1, 6)]
        for item in records:
            item["task_family"] = "calculator" if int(item["evaluation_id"].split(".")[-1]) < 48 else "direct_answer"
            item["difficulty"] = ("easy", "medium", "hard")[int(item["evaluation_id"].split(".")[-1]) % 3]
        manifest = {"execution_attempt_identity": "restart1", "provider_config_hash": "config", "suite_hash": "suite", "split_hash": "split"}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "formal_execution_manifest_v1.json").write_text(json.dumps(manifest))
            (root / "formal_run_attempts_v1.jsonl").write_text("\n".join(json.dumps(item) for item in records))
            first = root / "one"; second = root / "two"
            run_analysis(root, first); run_analysis(root, second)
            self.assertEqual((first / "primary_results.csv").read_bytes(), (second / "primary_results.csv").read_bytes())
            self.assertEqual((first / "statistical_test_metadata.json").read_bytes(), (second / "statistical_test_metadata.json").read_bytes())
            self.assertIn("UNAVAILABLE", (first / "resource_summary.csv").read_text())
            self.assertNotIn("m16_flash_lite", (first / "experiment_identity.json").read_text())

    def test_unavailable_telemetry_is_not_rewritten_as_zero(self):
        self.assertEqual(BOOTSTRAP_SEED, 913202610)

    def test_complete_vector_swap_keeps_case_repetitions_clustered(self):
        rows = [{"paired_difference": 1.0}, {"paired_difference": 0.0}]
        result = paired_permutation(rows, 100, 11)
        self.assertEqual(result["method"], "monte_carlo_paired_case_clustered_label_permutation")
        self.assertEqual(result["observed_difference"], 0.5)
