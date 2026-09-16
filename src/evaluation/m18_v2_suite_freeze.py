"""Deterministic M18 v2 suite construction and provider-free freeze gates."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Callable

from src.evaluation.contracts import EvaluationAction, EvaluationActionType, EvaluationFeedback
from src.evaluation.m18_shared_provider import M18SharedProviderConfiguration
from src.evaluation.m18_suite_freeze import formal_suite, pilot_suite
from src.evaluation.m18_task_generation import M18Cohort, M18FailureSubtype, canonical_hash, canonical_json
from src.evaluation.m18_v2_provenance import (
    M18_V2_COMPARATOR_CONDITIONS, M18_V2_REPETITIONS,
    M18_V2_RUNTIME_ID, project_m18_v2_run_provenances,
)
from src.evaluation.m18_v2_runtime import (
    M18BenchmarkRuntimeCondition, M18V2ResultProvenance,
    M18V2SharedExecutionHarness,
)
from src.evaluation.m18_v2_semantics import (
    M18V2Episode, M18V2EvaluationCategory, M18V2OutcomeCategory,
    M18_V2_BUDGET_ID, M18_V2_ENVIRONMENT_ID, M18_V2_EVALUATOR_ID,
    M18_V2_SUITE_VERSION, generate_m18_v2_case, reference_public_trajectory,
)

ROOT=Path("evaluation/m18/suites_v2")
FREEZE_BASELINE="ee1ca1535733e6992e440478034e48067122f612"

def _v2(v):
    subtype = v.evaluator.failure_schedule.get("subtype") if v.cohort.value == "recovery_correction" else None
    return generate_m18_v2_case(v.cohort,v.difficulty,v.generation_seed,v.namespace,int(v.case_id.rsplit(".",1)[1]),M18FailureSubtype(subtype) if subtype else None)
def cases(): return tuple(_v2(x) for x in pilot_suite()),tuple(_v2(x) for x in formal_suite())
def public(cases): return [x.public.to_dict() for x in cases]
def private(cases): return [x.to_dict() for x in cases]
class _ReferenceAdapter:
    """Provider-free public trajectory adapter used solely for freeze validation."""

    system_condition = "direct_tool_calling"

    def __init__(self, actions: list[EvaluationAction]) -> None:
        self._actions = actions
        self.public_case: dict[str, Any] | None = None

    def initialize(self, case: Any) -> None:
        self.public_case = case.public.to_dict()

    def next_decision(self, feedback: EvaluationFeedback, budget: Any, provider_gate: Any) -> EvaluationAction:
        return provider_gate.invoke(lambda: self._actions.pop(0))


def _public_actions(case: Any) -> tuple[list[EvaluationAction], Any]:
    trajectory = reference_public_trajectory(case)
    actions = [
        EvaluationAction(EvaluationActionType.TOOL_CALL, {
            "tool_name": action["tool_name"], "parameters": action["parameters"],
        })
        for action in trajectory.actions
    ]
    actions.append(EvaluationAction(EvaluationActionType.ANSWER, {"answer": trajectory.final_public_result}))
    return actions, trajectory


def _replay(case: Any, actions: tuple[dict[str, Any], ...]) -> M18V2Episode:
    episode = M18V2Episode(case)
    for action in actions:
        episode.submit_tool(action)
    return episode


def _runtime_reference_gate(case: Any, provider_hash: str) -> tuple[Any, Any]:
    actions, trajectory = _public_actions(case)
    adapter = _ReferenceAdapter(actions)
    runtime = M18V2SharedExecutionHarness(
        M18BenchmarkRuntimeCondition.v2(),
        M18V2ResultProvenance(
            M18BenchmarkRuntimeCondition.v2(), M18_V2_RUNTIME_ID,
            provider_hash, M18_V2_COMPARATOR_CONDITIONS[adapter.system_condition],
        ),
    )
    result = runtime.dry_run(case, adapter)
    if result.evaluator_outcome is not M18V2EvaluationCategory.SUCCESS:
        raise ValueError("frozen case reachability failure")
    if result.final_public_state["current_value"] != trajectory.final_public_result:
        raise ValueError("public final result mismatch")
    if "expected_final_result" in canonical_json(adapter.public_case):
        raise ValueError("public adapter truth leakage")
    return result, trajectory


def _audit(cases, provider_hash):
    reachability = 0
    for x in cases:
        result, t = _runtime_reference_gate(x, provider_hash)
        if t.final_public_result != x.evaluator.expected_final_result:
            raise ValueError("private target/public result mismatch")
        if (result.budget.action_cycles > 6 or result.budget.tool_attempts > 4
                or result.logical_provider_calls > 8):
            raise ValueError("frozen case budget failure")
        if "expected_final_result" in canonical_json(x.public.to_dict()):
            raise ValueError("public truth leakage")
        # Negative controls are evaluated on independent provider-free episodes.
        replay = _replay(x, t.actions)
        if replay.submit_answer(t.final_public_result + 1) is not M18V2EvaluationCategory.WRONG_ANSWER:
            raise ValueError("wrong answer control failure")
        replay = _replay(x, t.actions)
        if replay.submit_answer("malformed") is not M18V2EvaluationCategory.MALFORMED_ANSWER:
            raise ValueError("malformed answer control failure")
        if x.cohort is M18Cohort.B:
            config = x.public.to_dict()["task_config"]
            relevant = config["steps"][0]["tool_id"]
            distractor = next(item["tool_id"] for item in x.public.to_dict()["capabilities"] if item["tool_id"] != relevant)
            failed = M18V2Episode(x)
            outcome = failed.submit_tool({"action": "tool_call", "tool_name": distractor,
                                          "parameters": {"value": config["initial_value"]}})
            if outcome.category is not M18V2OutcomeCategory.INVALID_ACTION:
                raise ValueError("distractor control failure")
        if x.cohort is M18Cohort.C and not any(
                observation["category"] in {"recoverable_failure", "invalid_action"}
                for observation in t.observations):
            raise ValueError("recovery control failure")
        reachability += 1
    return {"case_count":len(cases),"reachability_passed":reachability,
            "target_public_result_mismatches":0,
            "private_hash":canonical_hash(private(cases)),"public_hash":canonical_hash(public(cases)),"cohort_counts":_counts(cases,lambda x:x.cohort.value),"difficulty_counts":_counts(cases,lambda x:x.difficulty.value),"subtype_counts":_counts([x for x in cases if x.failure_subtype],lambda x:x.failure_subtype.value)}
def _counts(cases,key):
    out={}
    for x in cases: out[key(x)]=out.get(key(x),0)+1
    return dict(sorted(out.items()))
def build():
    pilot,formal=cases(); provider=M18SharedProviderConfiguration().config_hash
    pa,fa=_audit(pilot,provider),_audit(formal,provider)
    member = lambda case: {"case_id":case.case_id,"generation_seed":case.generation_seed,
                           "cohort":case.cohort.value,"difficulty":case.difficulty.value,
                           "failure_subtype":case.failure_subtype.value if case.failure_subtype else None}
    split={"suite_identity":M18_V2_SUITE_VERSION,
           "generator_identity":"m18_generation_v2_public_transition_v1",
           "pilot_membership":[member(x) for x in pilot],
           "formal_membership":[member(x) for x in formal],
           "pilot_ids":[x.case_id for x in pilot],"formal_ids":[x.case_id for x in formal],
           "artifacts":{"pilot_public":"pilot/public_cases.json","pilot_private":"pilot/private_cases.json",
                        "formal_public":"formal/public_cases.json","formal_private":"formal/private_cases.json"},
           "artifact_hashes":{"pilot_public":pa["public_hash"],"pilot_private":pa["private_hash"],
                              "formal_public":fa["public_hash"],"formal_private":fa["private_hash"]}}
    if set(split["pilot_ids"])&set(split["formal_ids"]): raise ValueError("split overlap")
    conditions=tuple(M18_V2_COMPARATOR_CONDITIONS.values())
    pu=project_m18_v2_run_provenances(split["pilot_ids"],conditions,provider,FREEZE_BASELINE); fu=project_m18_v2_run_provenances(split["formal_ids"],conditions,provider,FREEZE_BASELINE)
    split["split_hash"]=canonical_hash({k:v for k,v in split.items() if k!="split_hash"})
    if len(pu) != len(set(x.run_id for x in pu)) or len(fu) != len(set(x.run_id for x in fu)) or {x.run_id for x in pu} & {x.run_id for x in fu}:
        raise ValueError("run universe collision")
    core={"suite_identity":M18_V2_SUITE_VERSION,"suite_version":M18_V2_SUITE_VERSION,"generator_identity":"m18_generation_v2_public_transition_v1","environment_id":M18_V2_ENVIRONMENT_ID,"evaluator_id":M18_V2_EVALUATOR_ID,"budget_id":M18_V2_BUDGET_ID,"runtime_id":M18_V2_RUNTIME_ID,"comparator_conditions":M18_V2_COMPARATOR_CONDITIONS,"repetitions":list(range(1,M18_V2_REPETITIONS+1)),"provider_config_hash":provider,"freeze_baseline":FREEZE_BASELINE,"pilot":pa,"formal":fa,"split_manifest_hash":split["split_hash"],"pilot_run_count":len(pu),"formal_run_count":len(fu),"run_id_schema":"m18_v2_logical_run_id_v1","result_namespace_spec":{"pilot":"evaluation/m18/results/v2/pilot/m18_suite_v2","formal":"evaluation/m18/results/v2/formal/m18_suite_v2"},"result_admission_requirements":["run_id","repetition","case_id","suite_identity","environment_id","evaluator_id","budget_id","runtime_id","comparator_condition_id","provider_config_hash","execution_baseline"],"freeze_status":"FROZEN"}
    manifest={**core,"manifest_hash":canonical_hash(core)}
    return pilot,formal,public(pilot),private(pilot),public(formal),private(formal),split,manifest
def write(root=ROOT):
    pilot,formal,pp,pv,fp,fv,split,manifest=build(); files={root/"pilot/public_cases.json":pp,root/"pilot/private_cases.json":pv,root/"formal/public_cases.json":fp,root/"formal/private_cases.json":fv,root/"manifests/m18_suite_v2_split.json":split,root/"manifests/m18_suite_v2_manifest.json":manifest}
    for path,value in files.items():
        content=canonical_json(value)+"\n"
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise ValueError("refusing overwrite of frozen v2 artifact")
            continue
        path.parent.mkdir(parents=True,exist_ok=True); path.write_text(content,encoding="utf-8")
    return manifest
def load_and_validate(root=ROOT):
    pilot,formal,pp,pv,fp,fv,split,manifest=build(); expected={root/"pilot/public_cases.json":pp,root/"pilot/private_cases.json":pv,root/"formal/public_cases.json":fp,root/"formal/private_cases.json":fv,root/"manifests/m18_suite_v2_split.json":split,root/"manifests/m18_suite_v2_manifest.json":manifest}
    for path,value in expected.items():
        if not path.exists() or json.loads(path.read_text(encoding="utf-8")) != value: raise ValueError("frozen v2 artifact drift")
    return manifest
