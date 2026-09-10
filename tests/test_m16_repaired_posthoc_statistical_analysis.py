import json
import tempfile
import unittest
from pathlib import Path

from src.evaluation.m16_repaired_posthoc_statistical_analysis import (
    BOOTSTRAP_SEED, DIRECT, EXPECTED_MANIFEST_HASH, MIND, case_rows,
    load_repaired_records, run_analysis, validate_dataset,
)
from src.evaluation.m16_deepseek_repaired_posthoc_v1 import load_repaired_posthoc_manifest


class RepairedPostHocAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.root = Path("evaluation/results/m16_deepseek_repaired_posthoc_v1")

    def test_authoritative_dataset_has_complete_paired_clusters(self):
        _, records = load_repaired_records(self.root)
        rows = case_rows(records)
        self.assertEqual((len(records), len(rows)), (960, 96))
        self.assertTrue(all(r["mind_successes"] == 5 for r in rows))
        self.assertAlmostEqual(sum(r["paired_difference"] for r in rows) / 96, .1)

    def test_fixed_analysis_is_deterministic_and_preserves_telemetry_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            one, two = Path(temp) / "one", Path(temp) / "two"
            first, second = run_analysis(self.root, one), run_analysis(self.root, two)
            self.assertEqual((one / "primary_results.csv").read_bytes(), (two / "primary_results.csv").read_bytes())
            self.assertEqual(first["permutation"], second["permutation"])
            self.assertIn("UNAVAILABLE", (one / "resource_summary.csv").read_text())
            self.assertEqual(BOOTSTRAP_SEED, 970000002)

    def test_rejects_foreign_or_incomplete_records(self):
        manifest = load_repaired_posthoc_manifest().to_dict()
        with self.assertRaises(ValueError):
            validate_dataset(manifest, [])
        manifest["post_hoc"] = False
        with self.assertRaises(ValueError):
            validate_dataset(manifest, [])

    def test_case_rows_keep_full_vectors_not_independent_repetitions(self):
        records = []
        for b in (MIND, DIRECT):
            for rep in range(1, 6):
                records.append({"evaluation_id": "case", "baseline_id": b, "repetition": rep, "success": b == MIND, "task_family": "calculator", "difficulty": "easy"})
        row = case_rows(records)[0]
        self.assertEqual((row["mind_rate"], row["direct_rate"], row["paired_difference"]), (1.0, 0.0, 1.0))


if __name__ == "__main__":
    unittest.main()
