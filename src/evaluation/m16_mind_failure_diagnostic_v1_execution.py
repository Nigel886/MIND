"""Guarded future entry point for M16 post-hoc diagnostic v1.

Importing this module and running preflight are read-only with respect to
providers, Agents, and the diagnostic result directory.  Real execution is
only reachable through the explicit ``--execute`` gate.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from evaluation.tasks.m16_cohort_a_held_out import get_m16_cohort_a_held_out_suite
from src.evaluation.m16_diagnostic_telemetry import DIAGNOSTIC_RESULT_DIRECTORY, validate_diagnostic_result_directory
from src.evaluation.m16_formal_execution_lock import M16FormalExecutionLock, recover_stale_lock
from src.evaluation.m16_mind_failure_diagnostic_v1 import (
    DIAGNOSTIC_BASELINE,
    DIAGNOSTIC_RESULT_SCHEMA_VERSION,
    EXPECTED_DIAGNOSTIC_MANIFEST_HASH,
    M16DiagnosticAttemptRecord,
    M16DiagnosticAttemptStatus,
    M16MindFailureDiagnosticManifest,
    M16MindFailureDiagnosticStore,
    diagnostic_schedule,
    load_frozen_m16_mind_failure_diagnostic_manifest,
)


DEFAULT_RESULT_DIRECTORY = str(DIAGNOSTIC_RESULT_DIRECTORY).replace("\\", "/")


def validate_diagnostic_v1_preflight(
    result_dir: str | Path = DEFAULT_RESULT_DIRECTORY,
    manifest: M16MindFailureDiagnosticManifest | None = None,
) -> tuple[M16MindFailureDiagnosticManifest, tuple[Any, ...], tuple[Any, ...]]:
    """Verify frozen identity and schedule before any provider/Agent work."""
    directory = validate_diagnostic_result_directory(result_dir)
    active_manifest = manifest or load_frozen_m16_mind_failure_diagnostic_manifest()
    if active_manifest.manifest_hash != EXPECTED_DIAGNOSTIC_MANIFEST_HASH:
        raise RuntimeError("diagnostic manifest hash mismatch")
    if active_manifest.result_directory != str(directory).replace("\\", "/"):
        raise RuntimeError("diagnostic result directory identity mismatch")
    suite = get_m16_cohort_a_held_out_suite()
    if suite.suite_hash != active_manifest.source_suite_hash or suite.held_out_split_hash != active_manifest.source_split_hash:
        raise RuntimeError("diagnostic source suite identity mismatch")
    cases = tuple(sorted(suite.cases, key=lambda item: item.evaluation_id))
    definitions = diagnostic_schedule(active_manifest, tuple(item.evaluation_id for item in cases))
    if len(cases) != 96 or len(definitions) != 96:
        raise RuntimeError("diagnostic v1 case schedule mismatch")
    if len({item.run_id for item in definitions}) != 96 or any(item.run_id.startswith("m16:") for item in definitions):
        raise RuntimeError("diagnostic run identity isolation failure")
    if active_manifest.baseline != DIAGNOSTIC_BASELINE or active_manifest.repetitions != 1:
        raise RuntimeError("diagnostic baseline/repetition contract mismatch")
    # Reading an existing store is permitted only after namespace and manifest
    # validation; it never reads, resumes, or counts historical result sets.
    if directory.exists():
        store = M16MindFailureDiagnosticStore(directory, active_manifest)
        store.initialize()
        unknown = {item.run_id for item in store.completed_run_ids()} - {item.run_id for item in definitions}
        if unknown:
            raise RuntimeError("diagnostic resume state contains foreign run IDs")
    return active_manifest, cases, definitions


def execute_m16_mind_failure_diagnostic_v1(result_dir: str | Path = DEFAULT_RESULT_DIRECTORY) -> int:
    """Execute only after an operator explicitly selects the ``--execute`` gate."""
    manifest = load_frozen_m16_mind_failure_diagnostic_manifest()
    directory = validate_diagnostic_result_directory(result_dir)
    with M16FormalExecutionLock(directory, manifest.manifest_hash):
        _, cases, definitions = validate_diagnostic_v1_preflight(directory, manifest)
        store = M16MindFailureDiagnosticStore(directory, manifest)
        store.initialize()
        completed = store.completed_run_ids()
        # These imports and constructions remain after preflight, ownership,
        # and result-store initialization.  Importing this module never reaches
        # this branch and therefore cannot create an Agent or provider call.
        from src.core.inference_registry import InferenceStrategyRegistry
        from src.core.inference_strategy import InferenceStrategy
        from src.evaluation.m16_benchmark_contracts import (
            M16BaselineID, M16FailureCategory, M16FormalRunDefinition,
            load_frozen_m16_deepseek_restart1_manifest,
        )
        from src.evaluation.m16_benchmark_runner import M16BenchmarkRunner, M16RunActor
        from src.evaluation.m16_deepseek_v4_flash_formal_execution import _IdentityInference, adapt_deepseek_formal_envelope
        from src.evaluation.m16_mind_session_adapter import M16MINDSessionEvaluationAdapter
        from src.evaluation.deepseek_transport import DeepSeekGenerationConfig, DeepSeekRestTransport
        from src.integration.deepseek_m13_provider import DeepSeekM13InterpretationProvider
        from src.integration.llm_session_admission import M13SessionAdmissionResolver
        from src.integration.task_interpreter import TaskInterpreter
        from src.evaluation.m16_diagnostic_telemetry import M16DiagnosticTelemetry

        formal_manifest = load_frozen_m16_deepseek_restart1_manifest()
        case_by_id = {item.evaluation_id: adapt_deepseek_formal_envelope(item) for item in cases}

        def make_actor(events: list[Any]) -> M16RunActor:
            observations: list[Any] = []
            telemetry = M16DiagnosticTelemetry(events.append)
            registry = InferenceStrategyRegistry()
            registry.register(InferenceStrategy("calculator_strategy", "Formal calculator capability", ("calculator",)), _IdentityInference())
            provider = DeepSeekM13InterpretationProvider(
                DeepSeekRestTransport(DeepSeekGenerationConfig()), ("calculator",), observations.append,
            )
            adapter = M16MINDSessionEvaluationAdapter(
                M13SessionAdmissionResolver(TaskInterpreter(provider), registry, telemetry), telemetry=telemetry,
            )
            return M16RunActor(adapter, observations, telemetry)

        count = 0
        for index, definition in enumerate(definitions):
            if definition.run_id in completed:
                continue
            attempt_number = store.next_attempt_number(definition.run_id)
            attempt_id = definition.attempt_id(attempt_number)
            events: list[Any] = []
            try:
                runner = M16BenchmarkRunner(
                    formal_manifest,
                    {
                        M16BaselineID.MIND_LITE_V1: lambda: make_actor(events),
                        M16BaselineID.DIRECT_TOOL_CALLING: lambda: (_ for _ in ()).throw(RuntimeError("Direct baseline is excluded")),
                    },
                )
                formal_definition = M16FormalRunDefinition(
                    formal_manifest.manifest_hash, definition.public_case_id, M16BaselineID.MIND_LITE_V1, 1, index,
                )
                record = runner.execute(case_by_id[definition.public_case_id], formal_definition, 1)
                status = (
                    M16DiagnosticAttemptStatus.PROVIDER_INFRASTRUCTURE_INVALID
                    if record.failure_category is M16FailureCategory.PROVIDER_INFRASTRUCTURE_INVALID_RUN
                    else M16DiagnosticAttemptStatus.TERMINAL_VALID
                )
                observed_outcome = record.failure_category.value
            except Exception:
                status = M16DiagnosticAttemptStatus.INTERRUPTED_INCOMPLETE
                observed_outcome = "execution_exception"
            store.append_events(definition.run_id, attempt_id, events)
            store.append_attempt(M16DiagnosticAttemptRecord(
                DIAGNOSTIC_RESULT_SCHEMA_VERSION, manifest.manifest_hash,
                definition.run_id, attempt_id, attempt_number,
                definition.public_case_id, 1, status, observed_outcome, len(events),
            ))
            count += 1
        return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M16 post-hoc MIND failure diagnostic v1")
    parser.add_argument("--result-dir", default=DEFAULT_RESULT_DIRECTORY)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--recover-stale-lock", action="store_true")
    arguments = parser.parse_args(argv)
    directory = validate_diagnostic_result_directory(arguments.result_dir)
    manifest = load_frozen_m16_mind_failure_diagnostic_manifest()
    if arguments.recover_stale_lock:
        if arguments.execute or arguments.preflight:
            parser.error("stale-lock recovery cannot combine with preflight or execution")
        recover_stale_lock(directory, manifest.manifest_hash)
        return 0
    if arguments.execute:
        return execute_m16_mind_failure_diagnostic_v1(directory)
    if arguments.preflight:
        validate_diagnostic_v1_preflight(directory, manifest)
        return 0
    parser.error("refusing diagnostic execution without --execute; use --preflight for read-only validation")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
