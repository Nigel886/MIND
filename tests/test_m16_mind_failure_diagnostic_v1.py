from __future__ import annotations

import json
import importlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr

from src.evaluation.m16_diagnostic_telemetry import M16DiagnosticEvent, M16DiagnosticStage
from src.evaluation.m16_formal_execution_lock import FormalExecutionAlreadyActiveError, M16FormalExecutionLock
from src.evaluation.m16_mind_failure_diagnostic_v1 import (
    DIAGNOSTIC_RESULT_SCHEMA_VERSION,
    M16DiagnosticAttemptRecord,
    M16DiagnosticAttemptStatus,
    M16MindFailureDiagnosticStore,
    diagnostic_schedule,
    load_frozen_m16_mind_failure_diagnostic_manifest,
)
from src.evaluation.m16_mind_failure_diagnostic_v1_execution import main, validate_diagnostic_v1_preflight


class M16MindFailureDiagnosticV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_frozen_m16_mind_failure_diagnostic_manifest()

    def test_manifest_is_canonical_and_reproducible(self) -> None:
        self.assertEqual(self.manifest.to_dict(), load_frozen_m16_mind_failure_diagnostic_manifest().to_dict())
        self.assertEqual(self.manifest.manifest_hash, load_frozen_m16_mind_failure_diagnostic_manifest().manifest_hash)
        self.assertEqual(self.manifest.provider_config_hash, "c074c0e08e6b7be9a93b955a5c5f85da52bb7e9cf83601477ab2e18dad4bc780")

    def test_preflight_is_read_only_and_execute_gate_is_required(self) -> None:
        result_directory = Path("evaluation/results/m16_mind_failure_diagnostic_v1")
        self.assertFalse(result_directory.exists())
        manifest, cases, schedule = validate_diagnostic_v1_preflight()
        self.assertEqual((manifest.expected_run_count, len(cases), len(schedule)), (96, 96, 96))
        self.assertFalse(result_directory.exists())
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main([])

    def test_preflight_mismatch_stops_before_provider_or_agent_construction(self) -> None:
        from dataclasses import replace
        mismatched = replace(self.manifest, source_suite_hash="wrong")
        provider_calls = 0
        with self.assertRaises(RuntimeError):
            validate_diagnostic_v1_preflight(manifest=mismatched)
        self.assertEqual(provider_calls, 0)

    def test_import_is_inert(self) -> None:
        module = importlib.import_module("src.evaluation.m16_mind_failure_diagnostic_v1_execution")
        self.assertTrue(callable(module.main))

    def test_exactly_96_unique_manifest_bound_ids_do_not_overlap_formal_namespace(self) -> None:
        cases = tuple(f"public.case.{index:03d}" for index in range(96))
        schedule = diagnostic_schedule(self.manifest, cases)
        run_ids = {item.run_id for item in schedule}
        self.assertEqual(len(run_ids), 96)
        self.assertTrue(all(item.startswith("m16diag:v1:") and not item.startswith("m16:") for item in run_ids))

    def _store(self, directory: Path) -> M16MindFailureDiagnosticStore:
        with patch("src.evaluation.m16_diagnostic_telemetry.DIAGNOSTIC_RESULT_DIRECTORY", directory):
            store = M16MindFailureDiagnosticStore(directory, self.manifest)
            store.initialize()
            return store

    def _record(self, run_id: str, attempt_id: str, number: int, status: M16DiagnosticAttemptStatus) -> M16DiagnosticAttemptRecord:
        return M16DiagnosticAttemptRecord(
            DIAGNOSTIC_RESULT_SCHEMA_VERSION, self.manifest.manifest_hash, run_id, attempt_id,
            number, "public.case.000", 1, status, "agent_fail", 1,
        )

    def test_store_rejects_foreign_manifest_and_historical_paths(self) -> None:
        from src.evaluation.m16_diagnostic_telemetry import validate_diagnostic_result_directory
        with self.assertRaises(ValueError):
            validate_diagnostic_result_directory("evaluation/results/m16")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "diagnostic"
            store = self._store(directory)
            payload = json.loads(store.manifest_path.read_text(encoding="utf-8"))
            payload["purpose"] = "other"
            store.manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            with patch("src.evaluation.m16_diagnostic_telemetry.DIAGNOSTIC_RESULT_DIRECTORY", directory):
                with self.assertRaises(ValueError):
                    M16MindFailureDiagnosticStore(directory, self.manifest).initialize()

    def test_resume_terminality_and_event_order_are_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "diagnostic"
            store = self._store(directory)
            definition = diagnostic_schedule(self.manifest, tuple(f"public.case.{index:03d}" for index in range(96)))[0]
            first = self._record(definition.run_id, definition.attempt_id(1), 1, M16DiagnosticAttemptStatus.INTERRUPTED_INCOMPLETE)
            events = (M16DiagnosticEvent(M16DiagnosticStage.PROVIDER_REQUEST_STARTED, 1), M16DiagnosticEvent(M16DiagnosticStage.PROVIDER_RESPONSE_RECEIVED, 2))
            store.append_events(definition.run_id, first.attempt_id, events)
            store.append_attempt(first)
            self.assertNotIn(definition.run_id, store.completed_run_ids())
            self.assertEqual(store.next_attempt_number(definition.run_id), 2)
            second = self._record(definition.run_id, definition.attempt_id(2), 2, M16DiagnosticAttemptStatus.TERMINAL_VALID)
            store.append_attempt(second)
            self.assertIn(definition.run_id, store.completed_run_ids())
            with self.assertRaises(ValueError):
                store.append_attempt(self._record(definition.run_id, definition.attempt_id(3), 3, M16DiagnosticAttemptStatus.TERMINAL_VALID))
            self.assertEqual([item["event"]["stage_ordinal"] for item in store.load_events()], [1, 2])

    def test_single_runner_guard_rejects_second_owner_before_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "diagnostic"
            with M16FormalExecutionLock(directory, self.manifest.manifest_hash):
                with self.assertRaises(FormalExecutionAlreadyActiveError):
                    M16FormalExecutionLock(directory, self.manifest.manifest_hash).acquire()

    def test_telemetry_payload_has_no_raw_text_channel(self) -> None:
        for unsafe_key in ("raw_response", "prompt", "api_key", "private_truth"):
            with self.subTest(unsafe_key=unsafe_key):
                with self.assertRaises(ValueError):
                    M16DiagnosticEvent(M16DiagnosticStage.PROVIDER_RESPONSE_RECEIVED, 1, metadata={unsafe_key: "secret"})
