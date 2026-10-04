import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m20_calibration_manifest import build_deepseek_manifest, build_postremediation_manifest
from src.evaluation.m20_deepseek_execution import M20DeepSeekCalibrationRunner
from src.evaluation.m20_postremediation_calibration_execution import (M20PostRemediationCalibrationRunner,
    authorization_payload, verify_authorization)


def _answer_transport(request, timeout):
    return {"model": "deepseek-flash", "choices": [{"message": {"content": '{"kind":"answer","payload":"no"}'}}]}


class M20PostRemediationCalibrationExecutionTest(unittest.TestCase):
    def test_v2_runner_rejects_v3_before_transport(self):
        with self.assertRaises(ValueError):
            M20DeepSeekCalibrationRunner(build_postremediation_manifest())

    def test_authorization_is_exact_and_v3_runner_admits_only_v3(self):
        runner = M20PostRemediationCalibrationRunner(); payload = authorization_payload()
        self.assertEqual(len(runner.work_items()), 120)
        for key, changed in (("manifest_digest", "0" * 64), ("runtime_identity", "wrong"),
                             ("provider_hash", "wrong"), ("resource_ceiling_identity", "wrong"),
                             ("work_ids", payload["work_ids"][:-1])):
            invalid = dict(payload); invalid[key] = changed
            with self.assertRaises(PermissionError): verify_authorization(invalid)
        with self.assertRaises(PermissionError): verify_authorization(None)
        with self.assertRaises(ValueError): M20PostRemediationCalibrationRunner(build_deepseek_manifest())

    def test_prefix_resume_and_idempotence_are_transport_bounded(self):
        runner = M20PostRemediationCalibrationRunner(); calls = []
        def fake(request, timeout): calls.append(request); return _answer_transport(request, timeout)
        with TemporaryDirectory() as directory:
            root = Path(directory) / "v3"
            runner.run_prefix_for_testing(authorization_payload(), fake, root, 2)
            self.assertGreater(len(calls), 0)
            # Existing terminal records are reconstructed and not replayed.
            before = len(calls); runner.run_prefix_for_testing(authorization_payload(), fake, root, 2)
            self.assertEqual(len(calls), before)
            marker = json.loads((root / "manifest.json").read_text())
            self.assertEqual(marker["namespace"], "m20_calibration_postremediation_v1")

    def test_corrupt_marker_fails_before_transport(self):
        runner = M20PostRemediationCalibrationRunner(); calls = []
        with TemporaryDirectory() as directory:
            root = Path(directory) / "v3"; runner.run_prefix_for_testing(authorization_payload(), lambda r,t: (_ for _ in ()).throw(AssertionError()), root, 0)
            (root / "manifest.json").write_text('{"bad":true}')
            with self.assertRaises(Exception): runner.run_prefix_for_testing(authorization_payload(), lambda r,t: calls.append(r), root, 0)
            self.assertEqual(calls, [])


if __name__ == "__main__": unittest.main()
