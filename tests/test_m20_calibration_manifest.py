import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m20_calibration_manifest import (
    M20_OPENAI_PROVIDER_HASH, M20_POSTREMEDIATION_CALIBRATION_MANIFEST_VERSION,
    M20_POSTREMEDIATION_CALIBRATION_NAMESPACE, M20_POSTREMEDIATION_CALIBRATION_PROTOCOL,
    M20_POSTREMEDIATION_CALIBRATION_RESULT_PATH, M20_POSTREMEDIATION_ORDERING_RULE,
    build_deepseek_manifest, build_manifest, build_postremediation_manifest,
    load_deepseek_manifest, load_manifest, load_postremediation_manifest,
    persist_deepseek_manifest, persist_manifest, persist_postremediation_manifest,
    postremediation_work_item, require_manifest, validate_deepseek_manifest,
    validate_postremediation_manifest,
)
from src.evaluation.m20_deepseek_execution import M20DeepSeekCalibrationRunner
from src.evaluation.m20_real_provider_diagnostic import (
    M20_DIAGNOSTIC_GENERATION_V2, M20_DIAGNOSTIC_GENERATION_V3,
    M20_DIAGNOSTIC_GENERATION_V4, M20_DIAGNOSTIC_GENERATION_V5,
    M20RealProviderDiagnosticRunner,
)
from src.evaluation.m20_real_execution_configuration import M20_REAL_PROVIDER_CONFIGURATION


class M20CalibrationManifestTest(unittest.TestCase):
    def test_postremediation_v3_is_distinct_deterministic_and_nonempirical(self):
        first, second = build_postremediation_manifest(), build_postremediation_manifest()
        self.assertEqual(first, second)
        self.assertEqual((first["protocol"], first["namespace"], first["result_path"], first["version"]),
                         (M20_POSTREMEDIATION_CALIBRATION_PROTOCOL,
                          M20_POSTREMEDIATION_CALIBRATION_NAMESPACE,
                          M20_POSTREMEDIATION_CALIBRATION_RESULT_PATH,
                          M20_POSTREMEDIATION_CALIBRATION_MANIFEST_VERSION))
        self.assertEqual((len(first["case_membership"]), first["repetitions"], len(first["pairs"]),
                          len(first["work_items"])), (12, 5, 60, 120))
        self.assertEqual({case["cohort"] for case in first["case_membership"]},
                         {"information_acquisition", "distractor_unnecessary_action", "answer_ready_early_stop",
                          "recovery_replanning", "resource_constrained", "multi_step_stateful"})
        self.assertEqual(first["ordering_rule"], M20_POSTREMEDIATION_ORDERING_RULE)
        self.assertEqual(sum(pair["conditions"][0] == "m20_mind_adaptive_v1" for pair in first["pairs"]), 30)
        self.assertEqual(len({pair["pair_id"] for pair in first["pairs"]}), 60)
        self.assertEqual(len({work["work_id"] for work in first["work_items"]}), 120)
        self.assertTrue(all(pair["manifest_digest"] == first["manifest_digest"] and
                            pair["ordering_identity"] == first["ordering_identity"] and
                            pair["runtime_generation"] == first["runtime_generation"]["identity"]
                            for pair in first["pairs"]))
        self.assertEqual(first["scientific_contract"]["resource_mre"], -0.25)
        self.assertEqual(first["runtime_generation"]["resource_admission"],
                         "m20_pretransport_provider_admission_v1")
        self.assertEqual(first["failure_replacement_contract"]["maximum_linked_replacements"], 1)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "v3.json"
            self.assertEqual(persist_postremediation_manifest(path), load_postremediation_manifest(path))

    def test_postremediation_v3_rejects_historical_and_stale_identity(self):
        value = build_postremediation_manifest()
        historical_ids = {item.adaptive.execution_id for item in M20DeepSeekCalibrationRunner().work_items()}
        historical_ids.update(item.fixed.execution_id for item in M20DeepSeekCalibrationRunner().work_items())
        generations = (None, M20_DIAGNOSTIC_GENERATION_V2, M20_DIAGNOSTIC_GENERATION_V3,
                       M20_DIAGNOSTIC_GENERATION_V4, M20_DIAGNOSTIC_GENERATION_V5)
        diagnostic_ids = set()
        for generation in generations:
            runner = (M20RealProviderDiagnosticRunner() if generation is None
                      else M20RealProviderDiagnosticRunner(generation=generation))
            diagnostic_ids.update(item.work_id for item in runner.work_items())
        v3_ids = {item["work_id"] for item in value["work_items"]}
        self.assertTrue(v3_ids.isdisjoint(historical_ids | diagnostic_ids))
        with self.assertRaises(ValueError):
            validate_postremediation_manifest(build_deepseek_manifest())
        for key, bad in (("namespace", "m20_calibration_v2"), ("provider_hash", "0" * 64),
                         ("resource_ceiling_identity", "wrong"), ("ordering_identity", "wrong"),
                         ("manifest_digest", "0" * 64), ("case_source_digest", "wrong")):
            altered = json.loads(json.dumps(value)); altered[key] = bad
            with self.assertRaises(ValueError): validate_postremediation_manifest(altered)
        self.assertEqual(postremediation_work_item(value, next(iter(v3_ids)))["namespace"],
                         M20_POSTREMEDIATION_CALIBRATION_NAMESPACE)
        for stale in (next(iter(historical_ids)), next(iter(diagnostic_ids))):
            with self.assertRaises(ValueError): postremediation_work_item(value, stale)

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
