import tempfile
import unittest
from pathlib import Path

from src.evaluation.m18_power_calibration_runner import (
    M18_POWER_CALIBRATION_COMPARATORS, M18_POWER_CALIBRATION_ID,
    M18PowerCalibrationPlan, M18PowerCalibrationRecord, M18PowerCalibrationRunner,
)
from src.evaluation.m18_v2_pilot_runner import M18V2PilotIntegrityError


class M18PowerCalibrationRunnerTests(unittest.TestCase):
    def setUp(self): self.root = Path(__file__).resolve().parents[1]

    def test_frozen_480_universe_and_pairing(self):
        plan = M18PowerCalibrationPlan.from_repository(self.root)
        self.assertEqual(M18_POWER_CALIBRATION_ID, plan.manifest["suite_id"])
        self.assertEqual(48, len(plan.manifest["cases"]))
        self.assertEqual(480, len(plan.expected))
        self.assertEqual(480, len({row.run_id for row in plan.expected}))
        self.assertEqual({"mind_lite_v11": 240, "direct_tool_calling": 240}, {c: sum(p.identity.comparator_id == c for p in plan.expected) for c in M18_POWER_CALIBRATION_COMPARATORS})
        self.assertTrue(all(row.run_id.startswith("m18pcv1-") for row in plan.expected))
        self.assertEqual(240, len({p.identity.paired_cell_key for p in plan.expected}))

    def test_preflight_and_fake_full_lifecycle_are_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = M18PowerCalibrationRunner.from_repository(self.root, result_root=Path(directory))
            self.assertEqual((480, 0, 480, 0, 0, 0), tuple(runner.preflight().__dict__[k] for k in ("expected", "valid", "missing", "duplicates", "invalid", "unexpected")))
            done = runner.execute(provider=lambda p: ("success", "success"))
            self.assertEqual(480, len(done)); self.assertEqual((480, 480, 0), (runner.preflight().expected, runner.preflight().valid, runner.preflight().missing))
            self.assertEqual(0, sum(1 for _ in (self.root / "evaluation/m18/results/m18_power_calibration_v1/pilot").glob("*.json")) if (self.root / "evaluation/m18/results/m18_power_calibration_v1/pilot").exists() else 0)

    def test_missing_only_duplicate_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = M18PowerCalibrationRunner.from_repository(self.root, result_root=Path(directory))
            runner.execute(provider=lambda p: ("success", "success"), limit=1)
            self.assertEqual(479, len(runner.store.missing()))
            row = runner.store.records()[0]
            with self.assertRaises(M18V2PilotIntegrityError): runner.store.persist(row)
            path = runner.store.root / (row.run_id + ".json")
            path.write_text('{"tampered":true}', encoding="utf-8")
            with self.assertRaises(M18V2PilotIntegrityError): runner.store.records()

    def test_no_cli_execution_and_no_foreign_comparators(self):
        self.assertEqual(("mind_lite_v11", "direct_tool_calling"), M18_POWER_CALIBRATION_COMPARATORS)
        with self.assertRaises(SystemExit):
            from src.evaluation.m18_power_calibration_runner import main
            main(["--condition", "m18_suite_v3"])


if __name__ == "__main__": unittest.main()
