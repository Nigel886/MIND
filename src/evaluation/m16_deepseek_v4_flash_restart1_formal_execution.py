"""Guarded replacement entry point for the DeepSeek M16 restart1 experiment."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from evaluation.tasks.m16_cohort_a_held_out import get_m16_cohort_a_held_out_suite
from src.evaluation.m16_benchmark_contracts import counterbalanced_schedule, load_frozen_m16_deepseek_restart1_manifest
from src.evaluation.m16_benchmark_runner import M16BenchmarkRunner
from src.evaluation.m16_deepseek_v4_flash_formal_execution import adapt_deepseek_formal_envelope, build_deepseek_formal_baseline_factories
from src.evaluation.m16_formal_execution_lock import M16FormalExecutionLock, recover_stale_lock
from src.evaluation.m16_result_store import M16ResultStore


EXPECTED_MANIFEST_HASH = "559c5e5dec527d5abffedb409725b89580818bd832846f64adedcd328d081ac9"
EXPECTED_SUITE_HASH = "a450c6fa2955136da5d4db08b892af442ab7be66034412739d91e7cbf076445c"
EXPECTED_SPLIT_HASH = "a41ca5a326da4f722de1fcca4c7a4b85fcf860767ba1bb0311aa6cc4176aefe3"
DEFAULT_RESULT_DIRECTORY = "evaluation/results/m16_deepseek_v4_flash_restart1"
_HISTORICAL_DIRECTORIES = frozenset({
    Path("evaluation/results/m16"),
    Path("evaluation/results/m16_flash_lite"),
    Path("evaluation/results/m16_deepseek_v4_flash"),
})


def validate_restart1_formal_preflight():
    manifest = load_frozen_m16_deepseek_restart1_manifest()
    if manifest.manifest_hash != EXPECTED_MANIFEST_HASH:
        raise RuntimeError("frozen DeepSeek restart1 manifest hash mismatch")
    if manifest.execution_attempt_identity != "restart1":
        raise RuntimeError("frozen DeepSeek restart1 execution identity mismatch")
    if (manifest.protocol_version, manifest.suite_generation_protocol_version, manifest.completion_semantics_version) != ("1.2.0", "1.1.0", "m16_completion_v2"):
        raise RuntimeError("frozen execution identity mismatch")
    suite = get_m16_cohort_a_held_out_suite()
    if suite.suite_hash != EXPECTED_SUITE_HASH or suite.held_out_split_hash != EXPECTED_SPLIT_HASH:
        raise RuntimeError("frozen suite identity mismatch")
    cases = tuple(adapt_deepseek_formal_envelope(item) for item in suite.cases)
    definitions = counterbalanced_schedule(manifest, tuple(item.case.evaluation_id for item in cases))
    if len(cases) != 96 or len(definitions) != 960 or len({item.run_id for item in definitions}) != 960:
        raise RuntimeError("frozen restart1 schedule mismatch")
    return manifest, cases, definitions


def _reject_historical_directory(result_directory: str | Path) -> Path:
    directory = Path(result_directory)
    if directory in _HISTORICAL_DIRECTORIES:
        raise ValueError("historical formal result directories are immutable and excluded")
    return directory


def execute_deepseek_restart1_formal_benchmark(result_dir: str | Path = DEFAULT_RESULT_DIRECTORY) -> int:
    directory = _reject_historical_directory(result_dir)
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise RuntimeError("DEEPSEEK_API_KEY is required")
    manifest = load_frozen_m16_deepseek_restart1_manifest()
    if manifest.manifest_hash != EXPECTED_MANIFEST_HASH:
        raise RuntimeError("frozen DeepSeek restart1 manifest hash mismatch")
    with M16FormalExecutionLock(directory, manifest.manifest_hash):
        manifest, cases, definitions = validate_restart1_formal_preflight()
        store = M16ResultStore(directory, manifest)
        store.initialize()
        completed = store.completed_run_ids()
        runner = M16BenchmarkRunner(manifest, build_deepseek_formal_baseline_factories())
        by_id = {item.case.evaluation_id: item for item in cases}
        count = 0
        for definition in definitions:
            if definition.run_id in completed:
                continue
            prior = [record for record in store.load_records() if record.run_id == definition.run_id]
            store.append(runner.execute(by_id[definition.evaluation_id], definition, len(prior) + 1))
            count += 1
        return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M16 DeepSeek V4 Flash restart1 formal execution")
    parser.add_argument("--result-dir", default=DEFAULT_RESULT_DIRECTORY)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--recover-stale-lock", action="store_true")
    arguments = parser.parse_args(argv)
    directory = _reject_historical_directory(arguments.result_dir)
    manifest = load_frozen_m16_deepseek_restart1_manifest()
    if arguments.recover_stale_lock:
        if arguments.execute:
            parser.error("stale-lock recovery cannot execute formal work")
        recover_stale_lock(directory, manifest.manifest_hash)
        return 0
    if not arguments.execute:
        parser.error("refusing formal execution without --execute")
    return execute_deepseek_restart1_formal_benchmark(directory)


if __name__ == "__main__":
    raise SystemExit(main())
