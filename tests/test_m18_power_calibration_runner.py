import tempfile
import unittest
from pathlib import Path

from src.evaluation.m18_power_calibration_runner import (
    M18_POWER_CALIBRATION_COMPARATORS, M18_POWER_CALIBRATION_ID,
    M18PowerCalibrationDispatch, M18PowerCalibrationPlan, M18PowerCalibrationPreflightError,
    M18PowerCalibrationRunner,
)
from src.evaluation.m18_v2_provider_diagnostics import (
    M18V2ProviderDiagnostic, M18V2ProviderExecutionFailure, M18V2SystematicProviderStop,
)
from src.evaluation.m18_v2_pilot_runner import M18V2PilotIntegrityError


class M18PowerCalibrationRunnerTests(unittest.TestCase):
    def setUp(self): self.root = Path(__file__).resolve().parents[1]
    @staticmethod
    def dispatches(): return M18PowerCalibrationRunner.corrected_dispatches()

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
            done = runner.execute(provider=lambda p: ("success", "success"), dispatches=self.dispatches())
            self.assertEqual(480, len(done)); self.assertEqual((480, 480, 0), (runner.preflight().expected, runner.preflight().valid, runner.preflight().missing))
            self.assertEqual(0, sum(1 for _ in (self.root / "evaluation/m18/results/m18_power_calibration_v1/pilot").glob("*.json")) if (self.root / "evaluation/m18/results/m18_power_calibration_v1/pilot").exists() else 0)

    def test_missing_only_duplicate_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = M18PowerCalibrationRunner.from_repository(self.root, result_root=Path(directory))
            runner.execute(provider=lambda p: ("success", "success"), dispatches=self.dispatches(), limit=1)
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

    def test_corrected_dispatch_and_strict_integer_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = M18PowerCalibrationRunner.from_repository(self.root, result_root=Path(directory))
            self.assertEqual(1, len(runner.execute(provider=lambda p: ("success", "success"), dispatches=self.dispatches(), limit=1)))
        stale = {**self.dispatches(), "mind_lite_v11": M18PowerCalibrationDispatch.__new__(M18PowerCalibrationDispatch)}
        object.__setattr__(stale["mind_lite_v11"], "comparator_id", "mind_lite_v11")
        object.__setattr__(stale["mind_lite_v11"], "comparator_contract_id", "m18_v3")
        object.__setattr__(stale["mind_lite_v11"], "strict_integer_answer", True)
        with tempfile.TemporaryDirectory() as directory:
            runner = M18PowerCalibrationRunner.from_repository(self.root, result_root=Path(directory))
            with self.assertRaises(M18PowerCalibrationPreflightError): runner.execute(provider=lambda p: ("success", "success"), dispatches=stale, limit=1)
            permissive = {**self.dispatches(), "direct_tool_calling": M18PowerCalibrationDispatch.__new__(M18PowerCalibrationDispatch)}
            object.__setattr__(permissive["direct_tool_calling"], "comparator_id", "direct_tool_calling")
            object.__setattr__(permissive["direct_tool_calling"], "comparator_contract_id", "m18_v3_comparator_contract_v2")
            object.__setattr__(permissive["direct_tool_calling"], "strict_integer_answer", False)
            with self.assertRaises(M18PowerCalibrationPreflightError): runner.execute(provider=lambda p: ("success", "success"), dispatches=permissive, limit=1)
            with self.assertRaises(M18PowerCalibrationPreflightError): runner.execute(provider=lambda p: ("success", "success"), dispatches=None, limit=1)

    def test_collision_formal_and_stop_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); runner = M18PowerCalibrationRunner(M18PowerCalibrationPlan.from_repository(base), result_root=base / "evidence")
            with self.assertRaises(M18PowerCalibrationPreflightError): runner.execute(provider=lambda p: ("success", "success"), dispatches=self.dispatches(), historical_ids={runner.plan.expected[0].run_id})
            formal = base / "evaluation/m18/results/m18_power_calibration_v1/formal"
            formal.mkdir(parents=True); (formal / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(M18PowerCalibrationPreflightError): runner.preflight(require_empty=True)
            (formal / "unexpected.json").unlink()
            runner.store.persist_stop(__import__("src.evaluation.m18_v2_provider_diagnostics", fromlist=["M18V2SystematicProviderStopEvent"]).M18V2SystematicProviderStopEvent("mind_lite_v11", "mind_policy", "provider_contract_error", ("one", "two"), 2))
            with self.assertRaises(M18PowerCalibrationPreflightError): runner.preflight(require_empty=True)

    def test_crash_recovery_and_provider_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = M18PowerCalibrationRunner.from_repository(self.root, result_root=Path(directory))
            with self.assertRaises(RuntimeError): runner.execute(provider=lambda p: ("success", "success"), dispatches=self.dispatches(), limit=1, after_persist=lambda r: (_ for _ in ()).throw(RuntimeError("after commit")))
            self.assertEqual(479, len(runner.store.missing()))
            calls=[]
            def structural(p):
                calls.append(p.run_id)
                raise M18V2ProviderExecutionFailure(M18V2ProviderDiagnostic("provider_contract_error", p.identity.comparator_id, "mind_policy", 1, 1, False, "token=supersecretvalue"))
            with self.assertRaises(M18V2SystematicProviderStop): runner.execute(provider=structural, dispatches=self.dispatches(), limit=5)
            self.assertIsNotNone(runner.store.systematic_stop()); self.assertLess(len(calls), 5)
            with self.assertRaises(M18V2SystematicProviderStop): runner.execute(provider=structural, dispatches=self.dispatches(), limit=1)
            rendered = runner.store.stop_path.read_text(encoding="utf-8") + "".join(p.read_text(encoding="utf-8") for p in runner.store.root.glob("*.json"))
            self.assertNotIn("supersecretvalue", rendered)

    def test_transient_provider_failures_do_not_create_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = M18PowerCalibrationRunner.from_repository(self.root, result_root=Path(directory))
            def transient(p):
                raise M18V2ProviderExecutionFailure(M18V2ProviderDiagnostic("timeout", p.identity.comparator_id, "mind_policy", 1, 3, True, "BearerSecret token=supersecretvalue"))
            runner.execute(provider=transient, dispatches=self.dispatches(), limit=2)
            self.assertIsNone(runner.store.systematic_stop())


if __name__ == "__main__": unittest.main()
