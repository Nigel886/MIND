import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m20_calibration_manifest import build_ceilingv2_manifest, build_deepseek_manifest, build_postremediation_manifest
from src.evaluation.m20_ceilingv2_calibration_execution import (
    M20CeilingV2CalibrationRunner, ceilingv2_authorization_payload,
    verify_ceilingv2_authorization,
)
from src.evaluation.m20_deepseek_execution import M20DeepSeekCalibrationRunner
from src.evaluation.m20_harness import M20IntegrityError, M20Outcome, ResourceDimension
from src.evaluation.m20_postremediation_calibration_execution import M20PostRemediationCalibrationRunner


def _answer_transport(request, timeout):
    return {"model": "deepseek-flash", "choices": [{"message": {"content": '{"kind":"answer","payload":"no"}'}}]}


class M20CeilingV2CalibrationExecutionTest(unittest.TestCase):
    def test_v4_runner_is_v2_bound_and_v3_v2_paths_reject_before_transport(self):
        runner = M20CeilingV2CalibrationRunner()
        ceiling = runner.harness.manifest.resource_ceiling
        self.assertEqual((ceiling.reasoning_steps, ceiling.tool_attempts, ceiling.provider_interactions,
                          ceiling.decision_cycles), (16, 8, 8, 8))
        self.assertEqual(len(runner.work_items()), 120)
        calls = []
        with TemporaryDirectory() as directory:
            with self.assertRaises(PermissionError):
                runner.run_prefix_for_testing(None, lambda r, t: calls.append(r), Path(directory), 1)
            self.assertEqual(calls, [])
        with self.assertRaises(ValueError): M20PostRemediationCalibrationRunner(build_ceilingv2_manifest())
        with self.assertRaises(ValueError): M20DeepSeekCalibrationRunner(build_ceilingv2_manifest())

    def test_authorization_is_exact_and_mutations_reject_before_fake_transport(self):
        runner, payload, calls = M20CeilingV2CalibrationRunner(), ceilingv2_authorization_payload(), []
        for key, changed in (("manifest_digest", "0" * 64), ("pair_work_binding_digest", "wrong"),
                             ("runtime_identity", "wrong"), ("ordering_identity", "wrong"),
                             ("provider_hash", "wrong"), ("namespace", "wrong"),
                             ("resource_ceiling_digest", "wrong"), ("pair_ids", payload["pair_ids"][:-1]),
                             ("work_ids", payload["work_ids"] + ["extra"])):
            invalid = dict(payload); invalid[key] = changed
            with self.assertRaises(PermissionError):
                runner.run_prefix_for_testing(invalid, lambda r, t: calls.append(r), Path("unused"), 1)
        self.assertEqual(calls, [])
        with self.assertRaises(PermissionError): verify_ceilingv2_authorization(None)
        with self.assertRaises(PermissionError): verify_ceilingv2_authorization(payload, build_postremediation_manifest())
        with TemporaryDirectory() as directory:
            runner.run_prefix_for_testing(payload, _answer_transport, Path(directory), 1)

    def test_prefix_resume_completed_idempotence_and_corruption_fail_closed(self):
        runner, payload, calls = M20CeilingV2CalibrationRunner(), ceilingv2_authorization_payload(), []
        def fake(request, timeout):
            calls.append(request); return _answer_transport(request, timeout)
        with TemporaryDirectory() as directory:
            root = Path(directory) / "v4"
            runner.run_prefix_for_testing(payload, fake, root, 2)
            before = len(calls); runner.run_prefix_for_testing(payload, fake, root, 2)
            self.assertEqual(len(calls), before)
            marker = json.loads((root / "manifest.json").read_text())
            self.assertEqual(marker["namespace"], "m20_calibration_ceilingv2_v1")
            record = next(root.glob("*.json"))
            if record.name == "manifest.json": record = next(path for path in root.glob("*.json") if path.name != "manifest.json")
            value = json.loads(record.read_text()); value["outcome"] = "success"
            record.write_text(json.dumps(value))
            with self.assertRaises(M20IntegrityError): runner.run_prefix_for_testing(payload, fake, root, 1)
            self.assertEqual(len(calls), before)

    def test_v2_capacity_and_retry_chain_are_effective_runtime_semantics(self):
        runner, payload = M20CeilingV2CalibrationRunner(), ceilingv2_authorization_payload()
        state = runner.harness.manifest.resource_ceiling.resource_state("capacity-test")
        for _ in range(8):
            state = state.consume(ResourceDimension.PROVIDER_INTERACTION, 1, "proposal")
        with self.assertRaises(Exception): state.consume(ResourceDimension.PROVIDER_INTERACTION, 1, "proposal")
        tool_state = runner.harness.manifest.resource_ceiling.resource_state("tool-capacity-test")
        for _ in range(8):
            tool_state = tool_state.consume(ResourceDimension.TOOL_ATTEMPT, 1, "action")
        with self.assertRaises(Exception): tool_state.consume(ResourceDimension.TOOL_ATTEMPT, 1, "action")
        for retries_after_initial in (0, 1, 2):
            attempts = []
            def flaky(request, timeout):
                attempts.append(request)
                if len(attempts) <= retries_after_initial: raise OSError("retry")
                return _answer_transport(request, timeout)
            with TemporaryDirectory() as directory:
                record = runner.run_prefix_for_testing(payload, flaky, Path(directory), 1)[0]
            self.assertEqual(record.telemetry.provider_interactions, 1)
            self.assertEqual(record.telemetry.provider_transport_attempts, retries_after_initial + 1)
            self.assertEqual([item.retry_index for item in record.telemetry.retries],
                             list(range(retries_after_initial + 1)))
            self.assertEqual(len({item.logical_operation_id for item in record.telemetry.retries}), 1)
            self.assertEqual(len({item.physical_attempt_id for item in record.telemetry.retries}), retries_after_initial + 1)

    def test_full_fake_lifecycle_is_idempotent_and_replacement_rules_stay_shared(self):
        runner, payload, calls = M20CeilingV2CalibrationRunner(), ceilingv2_authorization_payload(), []
        def fake(request, timeout):
            calls.append(request); return _answer_transport(request, timeout)
        with TemporaryDirectory() as directory:
            root = Path(directory) / "v4"
            records = runner.run(payload, fake, root)
            self.assertEqual(len(records), 120)
            before = len(calls); rerun = runner.run(payload, fake, root)
            self.assertEqual(len(calls), before); self.assertEqual(len(rerun), 120)
        performance_record = next(record for record in records if record.outcome is M20Outcome.FAILURE_OR_INCORRECT)
        with self.assertRaises(PermissionError): runner.harness.replacement(performance_record)


if __name__ == "__main__":
    unittest.main()
