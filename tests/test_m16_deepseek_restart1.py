from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from evaluation.tasks.m16_cohort_a_held_out import get_m16_cohort_a_held_out_suite
from src.evaluation.m16_benchmark_contracts import counterbalanced_schedule, load_frozen_m16_deepseek_manifest, load_frozen_m16_deepseek_restart1_manifest
from src.evaluation.m16_deepseek_v4_flash_restart1_formal_execution import (
    DEFAULT_RESULT_DIRECTORY,
    EXPECTED_MANIFEST_HASH,
    execute_deepseek_restart1_formal_benchmark,
    validate_restart1_formal_preflight,
)
from src.evaluation.m16_formal_execution_lock import FormalExecutionAlreadyActiveError, M16FormalExecutionLock
from src.evaluation.m16_result_store import M16ResultStore


ROOT = Path(__file__).resolve().parents[1]


class DeepSeekRestart1Tests(unittest.TestCase):
    def test_replacement_identity_is_deterministic_and_isolated(self) -> None:
        config = (ROOT / "evaluation/config/m16_deepseek_v4_flash_v1.json").read_bytes()
        manifest = load_frozen_m16_deepseek_restart1_manifest()
        invalidated = load_frozen_m16_deepseek_manifest()
        suite = get_m16_cohort_a_held_out_suite()
        definitions = counterbalanced_schedule(manifest, tuple(item.evaluation_case.evaluation_id for item in suite.cases))
        old_definitions = counterbalanced_schedule(invalidated, tuple(item.evaluation_case.evaluation_id for item in suite.cases))
        self.assertEqual(sha256(config).hexdigest(), "c074c0e08e6b7be9a93b955a5c5f85da52bb7e9cf83601477ab2e18dad4bc780")
        self.assertEqual((manifest.execution_attempt_identity, manifest.manifest_hash), ("restart1", EXPECTED_MANIFEST_HASH))
        self.assertNotEqual(manifest.manifest_hash, invalidated.manifest_hash)
        self.assertEqual((len(definitions), len({item.run_id for item in definitions})), (960, 960))
        self.assertFalse({item.run_id for item in definitions} & {item.run_id for item in old_definitions})
        self.assertEqual((suite.suite_hash, suite.held_out_split_hash), ("a450c6fa2955136da5d4db08b892af442ab7be66034412739d91e7cbf076445c", "a41ca5a326da4f722de1fcca4c7a4b85fcf860767ba1bb0311aa6cc4176aefe3"))

    def test_replacement_preflight_preserves_contract_and_is_zero_state(self) -> None:
        manifest, cases, definitions = validate_restart1_formal_preflight()
        self.assertEqual((manifest.protocol_version, manifest.completion_semantics_version, manifest.repetition_count), ("1.2.0", "m16_completion_v2", 5))
        self.assertEqual((len(cases), len(definitions)), (96, 960))
        self.assertEqual(DEFAULT_RESULT_DIRECTORY, "evaluation/results/m16_deepseek_v4_flash_restart1")
        self.assertFalse((ROOT / DEFAULT_RESULT_DIRECTORY).exists())

    def test_held_lock_rejects_before_preflight_or_provider_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {"DEEPSEEK_API_KEY": "development"}):
            directory = Path(temporary) / "restart1"
            manifest = load_frozen_m16_deepseek_restart1_manifest()
            with M16FormalExecutionLock(directory, manifest.manifest_hash):
                with patch("src.evaluation.m16_deepseek_v4_flash_restart1_formal_execution.validate_restart1_formal_preflight") as preflight:
                    with self.assertRaises(FormalExecutionAlreadyActiveError):
                        execute_deepseek_restart1_formal_benchmark(directory)
                    preflight.assert_not_called()
                self.assertFalse(directory.exists())

    def test_historical_state_cannot_initialize_replacement_store(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "state"
            invalidated = load_frozen_m16_deepseek_manifest()
            M16ResultStore(directory, invalidated).initialize()
            with self.assertRaises(ValueError):
                M16ResultStore(directory, load_frozen_m16_deepseek_restart1_manifest()).initialize()

    def test_historical_directories_are_rejected_without_execution(self) -> None:
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "development"}):
            for directory in ("evaluation/results/m16", "evaluation/results/m16_flash_lite", "evaluation/results/m16_deepseek_v4_flash"):
                with self.assertRaises(ValueError):
                    execute_deepseek_restart1_formal_benchmark(directory)
