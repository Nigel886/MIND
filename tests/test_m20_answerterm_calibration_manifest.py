"""Offline freeze checks for the post-answer-termination calibration generation."""
from __future__ import annotations

import json
import unittest

from src.evaluation.m20_answer_termination_diagnostic import M20AnswerTerminationDiagnosticRunner
from src.evaluation.m20_deepseek_execution import M20DeepSeekCalibrationRunner
from src.evaluation.m20_calibration_manifest import (
    M20_ANSWERTERM_CALIBRATION_MANIFEST_VERSION, M20_ANSWERTERM_CALIBRATION_NAMESPACE,
    M20_ANSWERTERM_CALIBRATION_PROTOCOL, M20_ANSWERTERM_CALIBRATION_RESULT_PATH,
    M20_ANSWERTERM_ORDERING_RULE, answerterm_work_item, build_answerterm_manifest,
    build_ceilingv2_manifest, build_deepseek_manifest, build_postremediation_manifest,
    validate_answerterm_manifest,
)
from src.evaluation.m20_harness import M20_ANSWER_READINESS_VERSION
from src.evaluation.m20_real_execution_configuration import M20_REAL_RESOURCE_CEILING, M20_REAL_RESOURCE_CEILING_V2


class M20AnswerTerminationCalibrationManifestTest(unittest.TestCase):
    def test_v5_is_deterministic_complete_counterbalanced_and_policy_bound(self):
        first, second = build_answerterm_manifest(), build_answerterm_manifest()
        self.assertEqual(first, second)
        self.assertEqual((first["protocol"], first["namespace"], first["result_path"], first["version"]),
                         (M20_ANSWERTERM_CALIBRATION_PROTOCOL, M20_ANSWERTERM_CALIBRATION_NAMESPACE,
                          M20_ANSWERTERM_CALIBRATION_RESULT_PATH, M20_ANSWERTERM_CALIBRATION_MANIFEST_VERSION))
        self.assertEqual((len(first["case_membership"]), first["repetitions"], len(first["pairs"]), len(first["work_items"])),
                         (12, 5, 60, 120))
        self.assertEqual(first["ordering_rule"], M20_ANSWERTERM_ORDERING_RULE)
        self.assertEqual(sum(pair["conditions"][0] == "m20_mind_adaptive_v1" for pair in first["pairs"]), 30)
        self.assertEqual(first["answer_readiness_identity"], M20_ANSWER_READINESS_VERSION)
        self.assertEqual(first["resource_ceiling_identity"], M20_REAL_RESOURCE_CEILING_V2.identity)
        self.assertNotEqual(first["runtime_generation"]["identity"], build_ceilingv2_manifest()["runtime_generation"]["identity"])
        self.assertEqual(len({item["pair_id"] for item in first["pairs"]}), 60)
        self.assertEqual(len({item["work_id"] for item in first["work_items"]}), 120)

    def test_v5_rejects_historical_and_altered_bindings(self):
        manifest = build_answerterm_manifest()
        historical = build_deepseek_manifest(), build_postremediation_manifest(), build_ceilingv2_manifest()
        for value in historical:
            with self.assertRaises(ValueError): validate_answerterm_manifest(value)
        old_ids = {item["work_id"] for value in historical[1:] for item in value["work_items"]}
        old_ids.update(item.adaptive.execution_id for item in M20DeepSeekCalibrationRunner().work_items())
        old_ids.update(item.fixed.execution_id for item in M20DeepSeekCalibrationRunner().work_items())
        old_ids.update(item.work_id for item in M20AnswerTerminationDiagnosticRunner().work_items())
        self.assertTrue(set(item["work_id"] for item in manifest["work_items"]).isdisjoint(old_ids))
        for key, value in (("namespace", "m20_calibration_ceilingv2_v1"),
                           ("resource_ceiling_identity", M20_REAL_RESOURCE_CEILING.identity),
                           ("answer_readiness_identity", "wrong"), ("ordering_identity", "wrong"),
                           ("provider_hash", "0" * 64), ("runtime_generation", {}),
                           ("manifest_digest", "0" * 64)):
            altered = json.loads(json.dumps(manifest)); altered[key] = value
            with self.assertRaises(ValueError): validate_answerterm_manifest(altered)
        self.assertEqual(answerterm_work_item(manifest, manifest["work_items"][0]["work_id"])["namespace"],
                         M20_ANSWERTERM_CALIBRATION_NAMESPACE)
        with self.assertRaises(ValueError): answerterm_work_item(manifest, next(iter(old_ids)))


if __name__ == "__main__":
    unittest.main()
