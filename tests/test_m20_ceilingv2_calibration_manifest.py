import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m20_calibration_manifest import (
    M20_CEILINGV2_CALIBRATION_MANIFEST_VERSION,
    M20_CEILINGV2_CALIBRATION_NAMESPACE,
    M20_CEILINGV2_CALIBRATION_PROTOCOL,
    M20_CEILINGV2_CALIBRATION_RESULT_PATH,
    M20_CEILINGV2_ORDERING_RULE,
    build_ceilingv2_manifest,
    build_deepseek_manifest,
    build_postremediation_manifest,
    ceilingv2_work_item,
    load_ceilingv2_manifest,
    persist_ceilingv2_manifest,
    validate_ceilingv2_manifest,
)
from src.evaluation.m20_deepseek_execution import M20DeepSeekCalibrationRunner
from src.evaluation.m20_real_provider_diagnostic import (
    M20_DIAGNOSTIC_GENERATION_V2,
    M20_DIAGNOSTIC_GENERATION_V3,
    M20_DIAGNOSTIC_GENERATION_V4,
    M20_DIAGNOSTIC_GENERATION_V5,
    M20RealProviderDiagnosticRunner,
)
from src.evaluation.m20_real_execution_configuration import M20_REAL_RESOURCE_CEILING, M20_REAL_RESOURCE_CEILING_V2


class M20CeilingV2CalibrationManifestTest(unittest.TestCase):
    def test_v4_is_deterministic_complete_counterbalanced_and_v2_bound(self):
        first, second = build_ceilingv2_manifest(), build_ceilingv2_manifest()
        self.assertEqual(first, second)
        self.assertEqual((first["protocol"], first["namespace"], first["result_path"], first["version"]),
                         (M20_CEILINGV2_CALIBRATION_PROTOCOL, M20_CEILINGV2_CALIBRATION_NAMESPACE,
                          M20_CEILINGV2_CALIBRATION_RESULT_PATH, M20_CEILINGV2_CALIBRATION_MANIFEST_VERSION))
        self.assertEqual((len(first["case_membership"]), first["repetitions"], len(first["pairs"]),
                          len(first["work_items"])), (12, 5, 60, 120))
        self.assertEqual(first["ordering_rule"], M20_CEILINGV2_ORDERING_RULE)
        self.assertEqual(sum(pair["conditions"][0] == "m20_mind_adaptive_v1" for pair in first["pairs"]), 30)
        self.assertEqual(sum(pair["conditions"][0] == "m20_mind_fixed_v1" for pair in first["pairs"]), 30)
        self.assertEqual(first["case_source_digest"],
                         "4a00cb4128ef747419c601ed6696dd042cba7d4b45d09407e3fb68eb2a42ca12")
        self.assertEqual(first["provider_hash"],
                         "522fcf28714e168ce9854069468c51d3d3cb565404d7bdad3317e4fcc8f199ad")
        self.assertEqual(first["resource_ceiling_identity"], M20_REAL_RESOURCE_CEILING_V2.identity)
        self.assertEqual(first["resource_ceiling_identity"],
                         "m20_real_ceiling_v2:6b4537f6d7e688f30517307cfd2019d99ad20380f76110f8f5515d400bfa08e0")
        self.assertNotEqual(first["resource_ceiling_identity"], M20_REAL_RESOURCE_CEILING.identity)
        self.assertEqual(first["runtime_generation"]["resource_ceiling_identity"], M20_REAL_RESOURCE_CEILING_V2.identity)
        self.assertEqual(len({pair["pair_id"] for pair in first["pairs"]}), 60)
        self.assertEqual(len({item["work_id"] for item in first["work_items"]}), 120)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "v4.json"
            self.assertEqual(persist_ceilingv2_manifest(path), load_ceilingv2_manifest(path))

    def test_v4_rejects_historical_generations_and_every_stale_binding(self):
        value = build_ceilingv2_manifest()
        v4_ids = {item["work_id"] for item in value["work_items"]}
        v3 = build_postremediation_manifest()
        historical_ids = {item.adaptive.execution_id for item in M20DeepSeekCalibrationRunner().work_items()}
        historical_ids.update(item.fixed.execution_id for item in M20DeepSeekCalibrationRunner().work_items())
        historical_ids.update(item["work_id"] for item in v3["work_items"])
        diagnostic_ids = set()
        for generation in (None, M20_DIAGNOSTIC_GENERATION_V2, M20_DIAGNOSTIC_GENERATION_V3,
                           M20_DIAGNOSTIC_GENERATION_V4, M20_DIAGNOSTIC_GENERATION_V5):
            runner = M20RealProviderDiagnosticRunner() if generation is None else M20RealProviderDiagnosticRunner(generation=generation)
            diagnostic_ids.update(item.work_id for item in runner.work_items())
        self.assertTrue(v4_ids.isdisjoint(historical_ids | diagnostic_ids))
        for historical in (build_deepseek_manifest(), v3):
            with self.assertRaises(ValueError):
                validate_ceilingv2_manifest(historical)
        for key, bad in (("namespace", "m20_calibration_postremediation_v1"),
                         ("provider_hash", "0" * 64), ("case_source_digest", "wrong"),
                         ("resource_ceiling_identity", M20_REAL_RESOURCE_CEILING.identity),
                         ("ordering_identity", "wrong"), ("manifest_digest", "0" * 64)):
            altered = json.loads(json.dumps(value)); altered[key] = bad
            with self.assertRaises(ValueError): validate_ceilingv2_manifest(altered)
        self.assertEqual(ceilingv2_work_item(value, next(iter(v4_ids)))["namespace"],
                         M20_CEILINGV2_CALIBRATION_NAMESPACE)
        with self.assertRaises(ValueError):
            ceilingv2_work_item(value, next(iter(historical_ids)))
        with self.assertRaises(ValueError):
            ceilingv2_work_item(value, next(iter(diagnostic_ids)))


if __name__ == "__main__":
    unittest.main()
