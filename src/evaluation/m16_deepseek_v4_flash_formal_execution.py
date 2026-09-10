"""Guarded, isolated future M16 DeepSeek V4 Flash formal entry point."""
from __future__ import annotations
import argparse, os
from dataclasses import dataclass
from pathlib import Path
from typing import Any,Callable
from evaluation.tasks.m16_cohort_a_held_out import get_m16_cohort_a_held_out_suite
from src.core.inference_registry import InferenceStrategyRegistry
from src.core.inference_strategy import InferenceStrategy
from src.evaluation.deepseek_direct_action_provider import DeepSeekDirectActionProvider
from src.evaluation.deepseek_transport import DeepSeekGenerationConfig,DeepSeekRestTransport
from src.evaluation.direct_tool_calling import DirectToolCallingEvaluationAgent
from src.evaluation.m16_benchmark_contracts import M16BaselineID,counterbalanced_schedule,load_frozen_m16_deepseek_manifest
from src.evaluation.m16_benchmark_runner import M16BenchmarkRunner,M16RunActor
from src.evaluation.m16_gemini_assets import load_schema
from src.evaluation.m16_mind_session_adapter import M16MINDSessionEvaluationAdapter
from src.evaluation.m16_result_store import M16ResultStore
from src.integration.deepseek_m13_provider import DeepSeekM13InterpretationProvider
from src.integration.llm_session_admission import M13SessionAdmissionResolver
from src.integration.task_interpreter import TaskInterpreter

EXPECTED_MANIFEST_HASH="fd4d65dcbc962096c6110f19d0017672b3e5942dff07cbf930e98d72523e657f"
EXPECTED_SUITE_HASH="a450c6fa2955136da5d4db08b892af442ab7be66034412739d91e7cbf076445c"
EXPECTED_SPLIT_HASH="a41ca5a326da4f722de1fcca4c7a4b85fcf860767ba1bb0311aa6cc4176aefe3"
DEFAULT_RESULT_DIRECTORY="evaluation/results/m16_deepseek_v4_flash"
@dataclass(frozen=True)
class _FormalRunCase: case:Any; environment:Any; private_truth:Any; task_family:str; difficulty:str; eligibility:str="formal_eligible"
def adapt_deepseek_formal_envelope(envelope:Any)->_FormalRunCase: return _FormalRunCase(envelope.evaluation_case,envelope.environment_specification,envelope.private_truth,envelope.task_family.value,envelope.difficulty.value)
def validate_deepseek_formal_preflight():
    m=load_frozen_m16_deepseek_manifest()
    if m.manifest_hash!=EXPECTED_MANIFEST_HASH: raise RuntimeError("frozen DeepSeek manifest hash mismatch")
    if (m.protocol_version,m.suite_generation_protocol_version,m.completion_semantics_version)!=("1.2.0","1.1.0","m16_completion_v2"): raise RuntimeError("frozen execution identity mismatch")
    suite=get_m16_cohort_a_held_out_suite()
    if suite.suite_hash!=EXPECTED_SUITE_HASH or suite.held_out_split_hash!=EXPECTED_SPLIT_HASH: raise RuntimeError("frozen suite identity mismatch")
    cases=tuple(adapt_deepseek_formal_envelope(x) for x in suite.cases); definitions=counterbalanced_schedule(m,tuple(x.case.evaluation_id for x in cases))
    if len(cases)!=96 or len(definitions)!=960 or len({x.run_id for x in definitions})!=960: raise RuntimeError("frozen schedule mismatch")
    return m,cases,definitions
class _IdentityInference:
    def infer(self,observation,belief): return belief
def build_deepseek_formal_baseline_factories()->dict[M16BaselineID,Callable[[],M16RunActor]]:
    def mind():
        observations=[]; registry=InferenceStrategyRegistry(); registry.register(InferenceStrategy("calculator_strategy","Formal calculator capability",("calculator",)),_IdentityInference())
        provider=DeepSeekM13InterpretationProvider(DeepSeekRestTransport(DeepSeekGenerationConfig()),("calculator",),observations.append)
        return M16RunActor(M16MINDSessionEvaluationAdapter(M13SessionAdmissionResolver(TaskInterpreter(provider),registry)),observations)
    def direct():
        observations=[]; provider=DeepSeekDirectActionProvider(DeepSeekRestTransport(DeepSeekGenerationConfig()),observations.append)
        return M16RunActor(DirectToolCallingEvaluationAgent(provider,{"calculator":load_schema("m16_calculator_tool_v1.json")},"m16-deepseek-v4-flash-v1"),observations)
    return {M16BaselineID.MIND_LITE_V1:mind,M16BaselineID.DIRECT_TOOL_CALLING:direct}
def execute_deepseek_formal_benchmark(result_dir:str|Path=DEFAULT_RESULT_DIRECTORY)->int:
    if Path(result_dir) in {Path("evaluation/results/m16"),Path("evaluation/results/m16_flash_lite")}: raise ValueError("Gemini result directories are immutable and excluded")
    if not os.environ.get("DEEPSEEK_API_KEY"): raise RuntimeError("DEEPSEEK_API_KEY is required")
    m,cases,definitions=validate_deepseek_formal_preflight(); store=M16ResultStore(result_dir,m); store.initialize(); completed=store.completed_run_ids(); runner=M16BenchmarkRunner(m,build_deepseek_formal_baseline_factories()); by_id={x.case.evaluation_id:x for x in cases}; count=0
    for d in definitions:
        if d.run_id in completed: continue
        prior=[x for x in store.load_records() if x.run_id==d.run_id]; store.append(runner.execute(by_id[d.evaluation_id],d,len(prior)+1)); count+=1
    return count
def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="M16 DeepSeek V4 Flash formal execution"); p.add_argument("--result-dir",default=DEFAULT_RESULT_DIRECTORY); p.add_argument("--execute",action="store_true"); a=p.parse_args(argv)
    if not a.execute: p.error("refusing formal execution without --execute")
    return execute_deepseek_formal_benchmark(a.result_dir)
if __name__=="__main__": raise SystemExit(main())
