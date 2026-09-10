from __future__ import annotations

import json
import importlib
import io
from dataclasses import replace
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
from src.evaluation.m16_mind_failure_diagnostic_v1_execution import execute_m16_mind_failure_diagnostic_v1, main, validate_diagnostic_v1_preflight
from src.core.inference_registry import InferenceStrategyRegistry
from src.core.inference_strategy import InferenceStrategy
from src.evaluation.m16_benchmark_contracts import M16BaselineID, M16FormalExecutionManifest
from src.evaluation.m16_benchmark_runner import M16BenchmarkRunner, M16RunActor
from src.evaluation.m16_mind_session_adapter import M16MINDSessionEvaluationAdapter
from src.evaluation.m16_failure_mechanism_audit import CountingSyntheticProvider, _IdentityInference
from src.integration.llm_provider import ProviderResponse
from src.integration.llm_session_admission import M13SessionAdmissionResolver
from src.integration.task_interpreter import TaskInterpreter
from evaluation.tasks.m16_benchmark_dry_run_fixtures import get_m16_benchmark_dry_run_cases
from evaluation.tasks.m16_cohort_a_held_out import get_m16_cohort_a_held_out_suite
import src.evaluation.m16_diagnostic_telemetry as telemetry_module
import src.evaluation.m16_mind_failure_diagnostic_v1 as diagnostic_module
import src.evaluation.m16_mind_failure_diagnostic_v1_execution as execution_module


class M16MindFailureDiagnosticV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_frozen_m16_mind_failure_diagnostic_manifest()

    def test_manifest_is_canonical_and_reproducible(self) -> None:
        self.assertEqual(self.manifest.to_dict(), load_frozen_m16_mind_failure_diagnostic_manifest().to_dict())
        self.assertEqual(self.manifest.manifest_hash, load_frozen_m16_mind_failure_diagnostic_manifest().manifest_hash)
        self.assertEqual(self.manifest.provider_config_hash, "c074c0e08e6b7be9a93b955a5c5f85da52bb7e9cf83601477ab2e18dad4bc780")

    def test_preflight_is_read_only_and_execute_gate_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result_directory = Path(temporary) / "diagnostic"
            manifest = self._temporary_manifest(result_directory)
            self.assertFalse(result_directory.exists())
            active, cases, schedule = self._preflight(result_directory, manifest)
            self.assertEqual((active.expected_run_count, len(cases), len(schedule)), (96, 96, 96))
            self.assertFalse(result_directory.exists())
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main([])

    def test_preflight_mismatch_stops_before_provider_or_agent_construction(self) -> None:
        mismatched = replace(self.manifest, source_suite_hash="wrong")
        provider_calls = 0
        with self.assertRaises(RuntimeError):
            validate_diagnostic_v1_preflight(manifest=mismatched)
        self.assertEqual(provider_calls, 0)

    def _temporary_manifest(self, directory: Path):
        with patch.object(diagnostic_module, "DIAGNOSTIC_RESULT_DIRECTORY", directory):
            return replace(self.manifest, result_directory=str(directory).replace("\\", "/"))

    def _preflight(self, directory: Path, manifest):
        with patch.object(telemetry_module, "DIAGNOSTIC_RESULT_DIRECTORY", directory), patch.object(diagnostic_module, "DIAGNOSTIC_RESULT_DIRECTORY", directory), patch.object(execution_module, "EXPECTED_DIAGNOSTIC_MANIFEST_HASH", manifest.manifest_hash):
            return validate_diagnostic_v1_preflight(directory, manifest)

    def test_preflight_is_zero_write_for_absent_empty_and_valid_namespaces(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("absent", "empty", "valid", "terminal"):
                with self.subTest(name=name):
                    directory = root / name
                    if name != "absent":
                        directory.mkdir()
                    manifest = self._temporary_manifest(directory)
                    if name in {"valid", "terminal"}:
                        with patch.object(telemetry_module, "DIAGNOSTIC_RESULT_DIRECTORY", directory):
                            store = M16MindFailureDiagnosticStore(directory, manifest)
                            store.initialize()
                            definition = diagnostic_schedule(manifest, tuple(item.evaluation_id for item in get_m16_cohort_a_held_out_suite().cases))[0]
                            store.append_attempt(M16DiagnosticAttemptRecord(
                                DIAGNOSTIC_RESULT_SCHEMA_VERSION, manifest.manifest_hash, definition.run_id,
                                definition.attempt_id(1), 1, definition.public_case_id, 1,
                                M16DiagnosticAttemptStatus.INTERRUPTED_INCOMPLETE if name == "valid" else M16DiagnosticAttemptStatus.TERMINAL_VALID,
                                "interrupted" if name == "valid" else "agent_fail", 0,
                            ))
                    before = {item.relative_to(root): item.read_bytes() for item in directory.rglob("*") if item.is_file()} if directory.exists() else {}
                    self._preflight(directory, manifest)
                    after = {item.relative_to(root): item.read_bytes() for item in directory.rglob("*") if item.is_file()} if directory.exists() else {}
                    self.assertEqual(before, after)
                    self.assertFalse(M16FormalExecutionLock(directory, manifest.manifest_hash).path.exists())

    def test_preflight_rejects_foreign_state_and_active_owner_before_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "diagnostic"
            directory.mkdir()
            manifest = self._temporary_manifest(directory)
            (directory / "diagnostic_manifest_v1.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(Exception):
                self._preflight(directory, manifest)
            (directory / "diagnostic_manifest_v1.json").unlink()
            provider_calls = agent_runs = 0
            with M16FormalExecutionLock(directory, manifest.manifest_hash):
                with self.assertRaises(FormalExecutionAlreadyActiveError):
                    self._preflight(directory, manifest)
            self._preflight(directory, manifest)
            with M16FormalExecutionLock(directory, manifest.manifest_hash):
                pass
            self.assertEqual((provider_calls, agent_runs), (0, 0))

    def test_active_execution_owner_rejects_execute_before_provider_construction(self) -> None:
        directory = Path("evaluation/results/m16_mind_failure_diagnostic_v1")
        with M16FormalExecutionLock(directory, self.manifest.manifest_hash):
            with self.assertRaises(FormalExecutionAlreadyActiveError):
                execute_m16_mind_failure_diagnostic_v1(directory)

    def test_import_is_inert(self) -> None:
        module = importlib.import_module("src.evaluation.m16_mind_failure_diagnostic_v1_execution")
        self.assertTrue(callable(module.main))

    def _run_e2e(self, case_index: int, telemetry_enabled: bool):
        """Run actual M16 adapter/environment/judge wiring with no network."""
        case = get_m16_benchmark_dry_run_cases()[case_index]
        manifest = M16FormalExecutionManifest("1.1.0", "1.0.0", "suite", "split", "1", "config", repetition_count=1)
        events = []
        provider = CountingSyntheticProvider(ProviderResponse({
            "intent": "synthetic", "required_capabilities": ["calculator"], "constraints": {}, "evidence": {},
        }))
        from src.evaluation.m16_diagnostic_telemetry import M16DiagnosticTelemetry
        telemetry = M16DiagnosticTelemetry(events.append if telemetry_enabled else None)
        registry = InferenceStrategyRegistry()
        registry.register(InferenceStrategy("synthetic_calculator", "Synthetic capability", ("calculator",)), _IdentityInference())

        def actor():
            resolver = M13SessionAdmissionResolver(TaskInterpreter(provider), registry, telemetry)
            return M16RunActor(M16MINDSessionEvaluationAdapter(resolver, telemetry=telemetry), [], telemetry)

        runner = M16BenchmarkRunner(manifest, {M16BaselineID.MIND_LITE_V1: actor, M16BaselineID.DIRECT_TOOL_CALLING: actor})
        definition = next(item for item in runner.schedule((case,)) if item.baseline_id is M16BaselineID.MIND_LITE_V1)
        return runner.execute(case, definition), provider.calls, [event.stage_name for event in events]

    def test_e2e_calculator_runner_observes_real_tool_evaluator_and_terminal_boundaries(self) -> None:
        off, off_calls, _ = self._run_e2e(1, False)
        on, on_calls, stages = self._run_e2e(1, True)
        self.assertEqual((off.to_dict(), off_calls), (on.to_dict(), on_calls))
        self.assertTrue(on.success)
        self.assertLess(stages.index(M16DiagnosticStage.INTEGRATION_SELECTED), stages.index(M16DiagnosticStage.PRIVATE_TASK_PROJECTED))
        self.assertLess(stages.index(M16DiagnosticStage.PRIVATE_TASK_PROJECTED), stages.index(M16DiagnosticStage.PRIVATE_SESSION_CREATED))
        self.assertLess(stages.index(M16DiagnosticStage.PROJECTED_TOOL_ACTION), stages.index(M16DiagnosticStage.TOOL_INVOKED))
        self.assertLess(stages.index(M16DiagnosticStage.TOOL_INVOKED), stages.index(M16DiagnosticStage.EVALUATOR_INVOKED))
        self.assertLess(stages.index(M16DiagnosticStage.EVALUATOR_INVOKED), stages.index(M16DiagnosticStage.TERMINAL_ADAPTER_ACTION))
        for stage in (
            M16DiagnosticStage.PROJECTED_TOOL_ACTION,
            M16DiagnosticStage.TOOL_INVOKED,
            M16DiagnosticStage.EVALUATOR_INVOKED,
            M16DiagnosticStage.TERMINAL_ADAPTER_ACTION,
            M16DiagnosticStage.TERMINAL_REASON,
        ):
            self.assertIn(stage, stages)

    def test_e2e_direct_runner_observes_answer_evaluator_and_no_tool(self) -> None:
        off, off_calls, _ = self._run_e2e(0, False)
        on, on_calls, stages = self._run_e2e(0, True)
        self.assertEqual((off.to_dict(), off_calls), (on.to_dict(), on_calls))
        self.assertTrue(on.success)
        self.assertLess(stages.index(M16DiagnosticStage.INTEGRATION_SELECTED), stages.index(M16DiagnosticStage.PRIVATE_TASK_PROJECTED))
        self.assertLess(stages.index(M16DiagnosticStage.PRIVATE_TASK_PROJECTED), stages.index(M16DiagnosticStage.PRIVATE_SESSION_CREATED))
        self.assertLess(stages.index(M16DiagnosticStage.PROJECTED_ANSWER_ACTION), stages.index(M16DiagnosticStage.EVALUATOR_INVOKED))
        self.assertLess(stages.index(M16DiagnosticStage.EVALUATOR_INVOKED), stages.index(M16DiagnosticStage.TERMINAL_ADAPTER_ACTION))
        self.assertIn(M16DiagnosticStage.PROJECTED_ANSWER_ACTION, stages)
        self.assertIn(M16DiagnosticStage.EVALUATOR_INVOKED, stages)
        self.assertIn(M16DiagnosticStage.TERMINAL_ADAPTER_ACTION, stages)
        self.assertIn(M16DiagnosticStage.TERMINAL_REASON, stages)
        self.assertNotIn(M16DiagnosticStage.TOOL_INVOKED, stages)

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
