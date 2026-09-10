"""Contract tests for the inert repaired M16 post-hoc evaluation freeze."""
from __future__ import annotations

from dataclasses import replace
import importlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m16_benchmark_contracts import M16BaselineID, M16FailureCategory, M16RunAttemptRecord, RESULT_SCHEMA_VERSION, load_frozen_m16_deepseek_restart1_manifest, counterbalanced_schedule
from src.evaluation.m16_deepseek_repaired_posthoc_v1 import (
    DIRECT_REQUEST_HASH, MIND_REQUEST_HASH, MIND_SCHEMA_HASH, PROVIDER_CONFIG_HASH,
    M16RepairedPostHocResultStore, load_repaired_posthoc_manifest, repaired_posthoc_schedule,
)
from src.evaluation.m16_deepseek_repaired_posthoc_v1_execution import (
    EXPECTED_REPAIRED_POSTHOC_MANIFEST_HASH, main, validate_repaired_posthoc_preflight,
)
from src.evaluation.m16_formal_execution_lock import FormalExecutionAlreadyActiveError, M16FormalExecutionLock


def _ids() -> tuple[str, ...]:
    return tuple(f"m16.cohort_a.direct_answer.easy.{index:02d}" for index in range(96))


class RepairedPostHocTests(unittest.TestCase):
    def setUp(self) -> None: self.manifest = load_repaired_posthoc_manifest()

    def _temporary_manifest(self, directory: Path):
        return replace(self.manifest, result_namespace=str(directory).replace("\\", "/"))

    def test_manifest_identity_and_schedule_are_frozen(self) -> None:
        self.assertEqual(self.manifest.manifest_hash, EXPECTED_REPAIRED_POSTHOC_MANIFEST_HASH)
        self.assertEqual((self.manifest.mind_request_template_hash, self.manifest.canonical_schema_hash, self.manifest.direct_request_hash, self.manifest.provider_config_hash), (MIND_REQUEST_HASH, MIND_SCHEMA_HASH, DIRECT_REQUEST_HASH, PROVIDER_CONFIG_HASH))
        self.assertEqual(self.manifest, type(self.manifest).from_dict(self.manifest.to_dict()))
        schedule = repaired_posthoc_schedule(self.manifest, _ids())
        self.assertEqual((len(schedule), len({item.run_id for item in schedule})), (960, 960))
        self.assertTrue(all(item.run_id.startswith("m16-repaired-posthoc-v1:") for item in schedule))
        self.assertEqual(schedule[0].baseline_id, M16BaselineID.DIRECT_TOOL_CALLING)
        self.assertEqual(schedule[1].baseline_id, M16BaselineID.MIND_LITE_V1)
        historical = counterbalanced_schedule(load_frozen_m16_deepseek_restart1_manifest(), _ids())
        self.assertTrue({item.run_id for item in schedule}.isdisjoint(item.run_id for item in historical))
        self.assertEqual(
            tuple(item.baseline_id for item in schedule[:6]),
            (
                M16BaselineID.DIRECT_TOOL_CALLING, M16BaselineID.MIND_LITE_V1,
                M16BaselineID.MIND_LITE_V1, M16BaselineID.DIRECT_TOOL_CALLING,
                M16BaselineID.DIRECT_TOOL_CALLING, M16BaselineID.MIND_LITE_V1,
            ),
        )

    def test_store_terminal_and_resumable_semantics(self) -> None:
        with TemporaryDirectory() as temporary:
            directory = Path(temporary) / "results"; manifest = self._temporary_manifest(directory)
            store = M16RepairedPostHocResultStore(directory, manifest); store.initialize()
            schedule = repaired_posthoc_schedule(manifest, _ids())
            terminal = M16RunAttemptRecord(RESULT_SCHEMA_VERSION, schedule[0].run_id, schedule[0].attempt_id(1), 1, schedule[0].evaluation_id, schedule[0].baseline_id, 1, "direct_answer", "easy", "eligible", "m16_completion_v2", False, M16FailureCategory.AGENT_FAIL, 0, 0, manifest_hash=manifest.manifest_hash)
            resumable = M16RunAttemptRecord(RESULT_SCHEMA_VERSION, schedule[1].run_id, schedule[1].attempt_id(1), 1, schedule[1].evaluation_id, schedule[1].baseline_id, 1, "direct_answer", "easy", "eligible", "m16_completion_v2", False, M16FailureCategory.PROVIDER_INFRASTRUCTURE_INVALID_RUN, 0, 0, manifest_hash=manifest.manifest_hash)
            interrupted = M16RunAttemptRecord(RESULT_SCHEMA_VERSION, schedule[2].run_id, schedule[2].attempt_id(1), 1, schedule[2].evaluation_id, schedule[2].baseline_id, 1, "direct_answer", "easy", "eligible", "m16_completion_v2", False, M16FailureCategory.INTERRUPTED_INCOMPLETE, 0, 0, manifest_hash=manifest.manifest_hash)
            store.append(terminal); store.append(resumable); store.append(interrupted)
            self.assertEqual(store.completed_run_ids(), frozenset({terminal.run_id}))

    def test_preflight_is_zero_result_write_and_lock_blocks_second_owner(self) -> None:
        with TemporaryDirectory() as temporary:
            directory = Path(temporary) / "results"; manifest = self._temporary_manifest(directory)
            before = tuple(directory.glob("**/*")) if directory.exists() else ()
            _, cases, schedule = validate_repaired_posthoc_preflight(directory, manifest, manifest.manifest_hash)
            after = tuple(directory.glob("**/*")) if directory.exists() else ()
            self.assertEqual((len(cases), len(schedule), before, after), (96, 960, (), ()))
            directory.mkdir()
            _, partial_cases, partial_schedule = validate_repaired_posthoc_preflight(directory, manifest, manifest.manifest_hash)
            self.assertEqual((len(partial_cases), len(partial_schedule)), (96, 960))
            with M16FormalExecutionLock(directory, manifest.manifest_hash):
                with self.assertRaises(FormalExecutionAlreadyActiveError):
                    validate_repaired_posthoc_preflight(directory, manifest, manifest.manifest_hash)

    def test_foreign_manifest_and_execute_gate_fail_closed(self) -> None:
        with TemporaryDirectory() as temporary:
            directory = Path(temporary) / "results"; manifest = self._temporary_manifest(directory)
            directory.mkdir(); (directory / "repaired_posthoc_manifest_v1.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(Exception): validate_repaired_posthoc_preflight(directory, manifest, manifest.manifest_hash)
        with self.assertRaises(SystemExit): main([])

    def test_import_is_inert_and_historical_namespaces_are_never_targets(self) -> None:
        module = importlib.import_module("src.evaluation.m16_deepseek_repaired_posthoc_v1_execution")
        self.assertTrue(callable(module.validate_repaired_posthoc_preflight))
        self.assertNotIn(self.manifest.result_namespace, self.manifest.historical_exclusions)
        self.assertTrue(all("repaired_posthoc" not in item for item in self.manifest.historical_exclusions))


if __name__ == "__main__": unittest.main()
