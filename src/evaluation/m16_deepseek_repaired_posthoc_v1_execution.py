"""Inert explicit-gate entry point for repaired M16 post-hoc evaluation."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from src.evaluation.m16_deepseek_repaired_posthoc_v1 import (
    HISTORICAL_EXCLUSIONS, RESULT_DIRECTORY, M16RepairedPostHocManifest,
    M16RepairedPostHocResultStore, load_repaired_posthoc_manifest,
    repaired_posthoc_schedule,
)
from src.evaluation.m16_formal_execution_lock import M16FormalExecutionLock, recover_stale_lock


EXPECTED_REPAIRED_POSTHOC_MANIFEST_HASH = "7fb0013b2c93f23b6288604e374c9374477c427a14babbb7556454641f4304bb"
DEFAULT_RESULT_DIRECTORY = RESULT_DIRECTORY


def _directory(directory: str | Path, manifest: M16RepairedPostHocManifest) -> Path:
    path = Path(directory)
    if str(path).replace("\\", "/") != manifest.result_namespace: raise ValueError("result namespace identity mismatch")
    if str(path).replace("\\", "/") in HISTORICAL_EXCLUSIONS: raise ValueError("historical namespace is immutable")
    return path


def _preflight_under_lock(directory: Path, manifest: M16RepairedPostHocManifest, expected_hash: str) -> tuple[M16RepairedPostHocManifest, tuple[Any, ...], tuple[Any, ...]]:
    if manifest.manifest_hash != expected_hash: raise RuntimeError("repaired manifest hash mismatch")
    from evaluation.tasks.m16_cohort_a_held_out import get_m16_cohort_a_held_out_suite
    suite = get_m16_cohort_a_held_out_suite()
    if (suite.suite_hash, suite.held_out_split_hash) != (manifest.suite_hash, manifest.split_hash): raise RuntimeError("frozen suite identity mismatch")
    cases = tuple(sorted(suite.cases, key=lambda item: item.evaluation_id))
    definitions = repaired_posthoc_schedule(manifest, tuple(item.evaluation_id for item in cases))
    if len(cases) != 96 or len(definitions) != 960 or len({item.run_id for item in definitions}) != 960: raise RuntimeError("repaired schedule mismatch")
    records = M16RepairedPostHocResultStore(directory, manifest).inspect()
    known = {item.run_id for item in definitions}
    if {item.run_id for item in records} - known: raise RuntimeError("foreign repaired resume state")
    return manifest, cases, definitions


def validate_repaired_posthoc_preflight(result_dir: str | Path = DEFAULT_RESULT_DIRECTORY, manifest: M16RepairedPostHocManifest | None = None, expected_hash: str = EXPECTED_REPAIRED_POSTHOC_MANIFEST_HASH) -> tuple[M16RepairedPostHocManifest, tuple[Any, ...], tuple[Any, ...]]:
    active = manifest or load_repaired_posthoc_manifest()
    directory = _directory(result_dir, active)
    with M16FormalExecutionLock(directory, active.manifest_hash):
        return _preflight_under_lock(directory, active, expected_hash)


def execute_repaired_posthoc_evaluation(result_dir: str | Path = DEFAULT_RESULT_DIRECTORY) -> int:
    """Execute only after an explicit CLI gate; never reached during import/preflight."""
    if not os.environ.get("DEEPSEEK_API_KEY"): raise RuntimeError("DEEPSEEK_API_KEY is required")
    manifest = load_repaired_posthoc_manifest()
    directory = _directory(result_dir, manifest)
    with M16FormalExecutionLock(directory, manifest.manifest_hash):
        manifest, cases, definitions = _preflight_under_lock(directory, manifest, EXPECTED_REPAIRED_POSTHOC_MANIFEST_HASH)
        store = M16RepairedPostHocResultStore(directory, manifest)
        store.initialize()
        from src.evaluation.m16_benchmark_runner import M16BenchmarkRunner
        from src.evaluation.m16_deepseek_v4_flash_formal_execution import adapt_deepseek_formal_envelope, build_deepseek_formal_baseline_factories
        runner = M16BenchmarkRunner(manifest, build_deepseek_formal_baseline_factories())
        by_id = {item.evaluation_id: adapt_deepseek_formal_envelope(item) for item in cases}
        completed, count = store.completed_run_ids(), 0
        for definition in definitions:
            if definition.run_id in completed: continue
            prior = [item for item in store.load_records() if item.run_id == definition.run_id]
            store.append(runner.execute(by_id[definition.evaluation_id], definition, len(prior) + 1))
            count += 1
        return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M16 repaired DeepSeek post-hoc evaluation")
    parser.add_argument("--result-dir", default=DEFAULT_RESULT_DIRECTORY)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--recover-stale-lock", action="store_true")
    args = parser.parse_args(argv)
    manifest = load_repaired_posthoc_manifest()
    directory = _directory(args.result_dir, manifest)
    if args.recover_stale_lock:
        if args.preflight or args.execute: parser.error("stale-lock recovery cannot combine with preflight or execution")
        recover_stale_lock(directory, manifest.manifest_hash); return 0
    if args.execute: return execute_repaired_posthoc_evaluation(directory)
    if args.preflight: validate_repaired_posthoc_preflight(directory, manifest); return 0
    parser.error("refusing evaluation without --execute; use --preflight for read-only validation")
    return 2


if __name__ == "__main__": raise SystemExit(main())
