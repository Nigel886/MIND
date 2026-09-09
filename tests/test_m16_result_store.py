import tempfile
import unittest

from src.evaluation.m16_benchmark_contracts import (
    M16BaselineID,
    M16FailureCategory,
    M16FormalExecutionManifest,
    M16FormalRunDefinition,
    M16RunAttemptRecord,
    RESULT_SCHEMA_VERSION,
)
from src.evaluation.m16_result_store import M16ResultStore


class ResultStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = M16FormalExecutionManifest("1.1.0", "1.0.0", "suite", "split", "1", "config")
        self.definition = M16FormalRunDefinition(
            self.manifest.manifest_hash,
            "development-case",
            M16BaselineID.MIND_LITE_V1,
            1,
            0,
        )

    def _record(self, attempt_number: int, category: M16FailureCategory) -> M16RunAttemptRecord:
        return M16RunAttemptRecord(
            RESULT_SCHEMA_VERSION,
            self.definition.run_id,
            self.definition.attempt_id(attempt_number),
            attempt_number,
            self.definition.evaluation_id,
            self.definition.baseline_id,
            self.definition.repetition,
            "direct_answer",
            "easy",
            "development",
            "agent_final_answer",
            category is M16FailureCategory.SUCCESS,
            category,
            1,
            0,
            manifest_hash=self.manifest.manifest_hash,
        )

    def _store(self, directory: str) -> M16ResultStore:
        store = M16ResultStore(directory, self.manifest)
        store.initialize()
        return store

    def test_resumable_categories_do_not_complete_a_run(self) -> None:
        for category in (
            M16FailureCategory.PROVIDER_INFRASTRUCTURE_INVALID_RUN,
            M16FailureCategory.INTERRUPTED_INCOMPLETE,
        ):
            with self.subTest(category=category), tempfile.TemporaryDirectory() as directory:
                store = self._store(directory)
                store.append(self._record(1, category))
                self.assertNotIn(self.definition.run_id, store.completed_run_ids())

    def test_each_terminal_category_completes_a_run(self) -> None:
        terminal_categories = (
            M16FailureCategory.SUCCESS,
            M16FailureCategory.WRONG_ANSWER,
            M16FailureCategory.AGENT_FAIL,
            M16FailureCategory.INVALID_ACTION,
            M16FailureCategory.TIMEOUT,
            M16FailureCategory.STEP_BUDGET_EXHAUSTED,
            M16FailureCategory.TOOL_BUDGET_EXHAUSTED,
        )
        for category in terminal_categories:
            with self.subTest(category=category), tempfile.TemporaryDirectory() as directory:
                store = self._store(directory)
                store.append(self._record(1, category))
                self.assertIn(self.definition.run_id, store.completed_run_ids())

    def test_later_terminal_attempt_completes_prior_interrupted_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            store.append(self._record(1, M16FailureCategory.INTERRUPTED_INCOMPLETE))
            store.append(self._record(2, M16FailureCategory.SUCCESS))
            self.assertIn(self.definition.run_id, store.completed_run_ids())

    def test_later_terminal_attempt_completes_prior_provider_invalid_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            store.append(self._record(1, M16FailureCategory.PROVIDER_INFRASTRUCTURE_INVALID_RUN))
            store.append(self._record(2, M16FailureCategory.WRONG_ANSWER))
            self.assertIn(self.definition.run_id, store.completed_run_ids())

    def test_multiple_resumable_attempts_remain_resumable_and_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            first = self._record(1, M16FailureCategory.INTERRUPTED_INCOMPLETE)
            second = self._record(2, M16FailureCategory.PROVIDER_INFRASTRUCTURE_INVALID_RUN)
            store.append(first)
            store.append(second)
            records = store.load_records()
            self.assertEqual(tuple(record.attempt_number for record in records), (1, 2))
            self.assertEqual(tuple(record.attempt_id for record in records), (first.attempt_id, second.attempt_id))
            self.assertNotIn(self.definition.run_id, store.completed_run_ids())

    def test_duplicate_attempt_and_incompatible_manifest_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._store(directory)
            record = self._record(1, M16FailureCategory.SUCCESS)
            store.append(record)
            with self.assertRaises(ValueError):
                store.append(record)
            incompatible = M16FormalExecutionManifest("1.1.0", "1.0.0", "other-suite", "split", "1", "config")
            with self.assertRaises(ValueError):
                M16ResultStore(directory, incompatible).initialize()
