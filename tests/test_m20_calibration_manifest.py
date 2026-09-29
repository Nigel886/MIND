import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m20_calibration_manifest import (
    M20_OPENAI_PROVIDER_HASH, build_deepseek_manifest, build_manifest,
    load_deepseek_manifest, load_manifest, persist_deepseek_manifest, persist_manifest,
    require_manifest, validate_deepseek_manifest,
)
from src.evaluation.m20_real_execution_configuration import M20_REAL_PROVIDER_CONFIGURATION


class M20CalibrationManifestTest(unittest.TestCase):
    def test_historical_v1_is_deterministic_and_preserved(self):
        value = build_manifest()
        self.assertEqual(value["digest"], "31ce468ca217e7ea8ddc813c5740def250baa99f31871102b786f6bcbb2a71d8")
        self.assertEqual(value["provider_hash"], M20_OPENAI_PROVIDER_HASH)
        with TemporaryDirectory() as directory:
            self.assertEqual(persist_manifest(Path(directory) / "v1.json"),
                             load_manifest(Path(directory) / "v1.json"))

    def test_deepseek_v2_is_deterministic_complete_and_reloadable(self):
        first, second = build_deepseek_manifest(), build_deepseek_manifest()
        self.assertEqual(first, second)
        self.assertEqual(first["version"], "m20_calibration_manifest_v2")
        self.assertEqual(first["provider_hash"], M20_REAL_PROVIDER_CONFIGURATION.identity_hash)
        self.assertEqual((len(first["pairs"]), first["repetitions"]), (60, 5))
        self.assertEqual(len({pair["pair_id"] for pair in first["pairs"]}), 60)
        self.assertEqual({pair["cohort"] for pair in first["pairs"]},
                         {"information_acquisition", "distractor_unnecessary_action", "answer_ready_early_stop",
                          "recovery_replanning", "resource_constrained", "multi_step_stateful"})
        with TemporaryDirectory() as directory:
            self.assertEqual(persist_deepseek_manifest(Path(directory) / "v2.json"),
                             load_deepseek_manifest(Path(directory) / "v2.json"))

    def test_v2_mutations_fail_closed_and_only_v2_reaches_execution_gate(self):
        value = build_deepseek_manifest()
        for key in ("provider_hash", "resource_ceiling_identity", "environment_id", "metric_version", "statistical_protocol"):
            changed = json.loads(json.dumps(value)); changed[key] = "wrong"
            with self.assertRaises(ValueError):
                validate_deepseek_manifest(changed)
        changed = json.loads(json.dumps(value)); changed["pairs"].pop()
        with self.assertRaises(ValueError):
            validate_deepseek_manifest(changed)
        with self.assertRaises(ValueError):
            require_manifest(build_manifest())
        with self.assertRaises(PermissionError):
            require_manifest(value)
        with self.assertRaises(ValueError):
            require_manifest(None)


if __name__ == "__main__":
    unittest.main()
