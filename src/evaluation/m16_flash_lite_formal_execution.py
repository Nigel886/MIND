"""Guarded Gemini 3.1 Flash-Lite replacement M16 formal entry point.

This module has a separate manifest and result location from the permanently
aborted Gemini 2.5 Flash experiment.  Importing it never executes a provider
call or a formal case.
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from evaluation.tasks.m16_cohort_a_held_out import get_m16_cohort_a_held_out_suite
from src.core.inference_registry import InferenceStrategyRegistry
from src.core.inference_strategy import InferenceStrategy
from src.evaluation.direct_tool_calling import DirectToolCallingEvaluationAgent
from src.evaluation.gemini_direct_action_provider import GeminiDirectActionProvider
from src.evaluation.gemini_transport import GeminiFlashLiteGenerationConfig, GeminiRestTransport
from src.evaluation.m16_benchmark_contracts import (
    M16BaselineID, counterbalanced_schedule, load_frozen_m16_flash_lite_manifest,
)
from src.evaluation.m16_benchmark_runner import M16BenchmarkRunner, M16RunActor
from src.evaluation.m16_gemini_assets import load_schema
from src.evaluation.m16_mind_session_adapter import M16MINDSessionEvaluationAdapter
from src.evaluation.m16_result_store import M16ResultStore
from src.integration.gemini_m13_provider import GeminiM13InterpretationProvider
from src.integration.llm_session_admission import M13SessionAdmissionResolver
from src.integration.task_interpreter import TaskInterpreter


EXPECTED_MANIFEST_HASH = "ca50805d8c50cbdfa7164550b97ac90bd20975ff39a0a71b703d20f37a24cefa"
EXPECTED_SUITE_HASH = "a450c6fa2955136da5d4db08b892af442ab7be66034412739d91e7cbf076445c"
EXPECTED_SPLIT_HASH = "a41ca5a326da4f722de1fcca4c7a4b85fcf860767ba1bb0311aa6cc4176aefe3"
DEFAULT_RESULT_DIRECTORY = "evaluation/results/m16_flash_lite"


@dataclass(frozen=True)
class _FormalRunCase:
    case: Any
    environment: Any
    private_truth: Any
    task_family: str
    difficulty: str
    eligibility: str = "formal_eligible"


def adapt_flash_lite_formal_envelope(envelope: Any) -> _FormalRunCase:
    """Private mechanical mapping; private truth is not sent to a provider."""
    return _FormalRunCase(envelope.evaluation_case, envelope.environment_specification,
                           envelope.private_truth, envelope.task_family.value,
                           envelope.difficulty.value)


def validate_flash_lite_formal_preflight() -> tuple[Any, tuple[_FormalRunCase, ...], tuple[Any, ...]]:
    """Validate frozen identities without constructing a provider or running a case."""
    manifest = load_frozen_m16_flash_lite_manifest()
    if manifest.manifest_hash != EXPECTED_MANIFEST_HASH:
        raise RuntimeError("frozen Flash-Lite formal manifest hash mismatch")
    if (manifest.protocol_version, manifest.suite_generation_protocol_version,
        manifest.completion_semantics_version) != ("1.2.0", "1.1.0", "m16_completion_v2"):
        raise RuntimeError("frozen execution identity mismatch")
    suite = get_m16_cohort_a_held_out_suite()
    if suite.suite_hash != EXPECTED_SUITE_HASH or suite.held_out_split_hash != EXPECTED_SPLIT_HASH:
        raise RuntimeError("frozen formal suite identity mismatch")
    cases = tuple(adapt_flash_lite_formal_envelope(item) for item in suite.cases)
    definitions = counterbalanced_schedule(manifest, tuple(item.case.evaluation_id for item in cases))
    if len(cases) != 96 or len(definitions) != 960 or len({item.run_id for item in definitions}) != 960:
        raise RuntimeError("frozen formal schedule mismatch")
    return manifest, cases, definitions


class _IdentityInference:
    def infer(self, observation, belief): return belief


def build_flash_lite_formal_baseline_factories() -> dict[M16BaselineID, Callable[[], M16RunActor]]:
    """Build fresh same-model actors after explicit preflight validation."""
    def mind() -> M16RunActor:
        observations = []; registry = InferenceStrategyRegistry()
        registry.register(InferenceStrategy("calculator_strategy", "Formal calculator capability", ("calculator",)), _IdentityInference())
        provider = GeminiM13InterpretationProvider(
            GeminiRestTransport(GeminiFlashLiteGenerationConfig()), ("calculator",), observations.append,
        )
        resolver = M13SessionAdmissionResolver(TaskInterpreter(provider), registry)
        return M16RunActor(M16MINDSessionEvaluationAdapter(resolver), observations)

    def direct() -> M16RunActor:
        observations = []
        provider = GeminiDirectActionProvider(GeminiRestTransport(GeminiFlashLiteGenerationConfig()), observations.append)
        return M16RunActor(DirectToolCallingEvaluationAgent(
            provider, {"calculator": load_schema("m16_calculator_tool_v1.json")}, "m16-gemini-31-flash-lite-v1",
        ), observations)

    return {M16BaselineID.MIND_LITE_V1: mind, M16BaselineID.DIRECT_TOOL_CALLING: direct}


def execute_flash_lite_formal_benchmark(result_dir: str | Path = DEFAULT_RESULT_DIRECTORY) -> int:
    """Execute only after separately authorized future formal-readiness review."""
    if Path(result_dir) == Path("evaluation/results/m16"):
        raise ValueError("aborted Gemini 2.5 Flash results are immutable and excluded")
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is required for formal execution")
    manifest, cases, definitions = validate_flash_lite_formal_preflight()
    store = M16ResultStore(result_dir, manifest); store.initialize(); completed = store.completed_run_ids()
    runner = M16BenchmarkRunner(manifest, build_flash_lite_formal_baseline_factories())
    by_id = {item.case.evaluation_id: item for item in cases}; count = 0
    for definition in definitions:
        if definition.run_id in completed:
            continue
        prior = [record for record in store.load_records() if record.run_id == definition.run_id]
        store.append(runner.execute(by_id[definition.evaluation_id], definition, len(prior) + 1)); count += 1
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M16 Gemini 3.1 Flash-Lite formal execution")
    parser.add_argument("--result-dir", default=DEFAULT_RESULT_DIRECTORY)
    parser.add_argument("--execute", action="store_true", help="execute only after formal authorization")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("refusing formal execution without --execute")
    return execute_flash_lite_formal_benchmark(args.result_dir)


if __name__ == "__main__":
    raise SystemExit(main())
