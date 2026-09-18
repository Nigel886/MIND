"""Provider-free freeze builder for the prospective M18 v3 suite."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.evaluation.m18_task_generation import canonical_hash, canonical_json
from src.evaluation.m18_v2_suite_freeze import cases as v2_cases
from src.evaluation.m18_v3_provenance import M18V3RunIdentity
from src.evaluation.m18_v3_semantics import (
    M18V3Case, M18V3Episode, M18V2EvaluationCategory,
    M18_V3_BUDGET_ID, M18_V3_ENVIRONMENT_ID, M18_V3_EVALUATOR_ID,
    M18_V3_PUBLIC_ACTION_CONTRACT_ID, M18_V3_RUNTIME_ID, M18_V3_SUITE_VERSION,
)

ROOT = Path("evaluation/m18/suites_v3")
FREEZE_BASELINE = "b8efbfa24d1cfd01cd6dcb4dab1b1acc5703a03e"
SYSTEMS = ("mind_lite_v11", "direct_tool_calling", "react", "plan_and_execute")
FORBIDDEN = frozenset({"expected_final_result", "task_config", "transformation_id", "failure_schedule", "ground_truth", "evaluator_success", "chain_of_thought", "hidden_reasoning", "credentials", "api_key"})


def cases() -> tuple[tuple[M18V3Case, ...], tuple[M18V3Case, ...]]:
    pilot, formal = v2_cases()
    return tuple(M18V3Case(item) for item in pilot), tuple(M18V3Case(item) for item in formal)


def _static_public(case: M18V3Case) -> dict[str, Any]:
    caps=[]
    for item in case.source.public.to_dict()["capabilities"]:
        caps.append({key:item[key] for key in ("tool_id", "display_name", "description", "parameter_schema")})
    return {"case_id":case.case_id, "task_text":case.task_text, "capabilities":caps,
            "suite_identity":M18_V3_SUITE_VERSION, "public_action_contract_id":M18_V3_PUBLIC_ACTION_CONTRACT_ID}


def _private(case: M18V3Case) -> dict[str, Any]:
    return {"v3":case.to_dict(), "source_private_case":case.source.to_dict()}


def _member(case: M18V3Case) -> dict[str, Any]:
    return {"case_id":case.case_id, "generation_seed":case.source.generation_seed,
            "cohort":case.cohort.value, "difficulty":case.difficulty.value,
            "failure_subtype":case.failure_subtype.value if case.failure_subtype else None}


def _counts(values, key):
    result={}
    for value in values: result[key(value)]=result.get(key(value),0)+1
    return dict(sorted(result.items()))


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in _keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in _keys(child)}
    return set()


def _trajectory(case: M18V3Case) -> tuple[list[dict[str, Any]], M18V3Episode, dict[str, int]]:
    """Replay only public admissible actions and audit every active state."""
    episode=M18V3Episode(case); contexts=[]
    audit={"stale": 0, "future": 0, "leaks": 0, "tool": 0, "parameters": 0}
    while episode.public_context().current_action is not None:
        context=episode.public_context().to_dict(); contexts.append(context)
        action=context["current_action"]
        # The closed context admits exactly its active tool and its current
        # public value; it cannot carry a prior/future executable route.
        if len(context["capabilities"]) != 1 or context["capabilities"][0]["tool_id"] != action["tool_id"]:
            audit["future"] += 1
        # A retry after a recoverable public outcome may legitimately repeat
        # the *same current* tool.  "stale" therefore means an additional
        # non-current executable capability, which the cardinality check
        # above detects; it does not mean a repeated current request.
        if FORBIDDEN & _keys(context):
            audit["leaks"] += 1
        schema=action["parameter_schema"]
        if schema != {"type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"], "additionalProperties": False}:
            audit["parameters"] += 1
        if action["tool_id"] != context["capabilities"][0]["tool_id"]:
            audit["tool"] += 1
        outcome=episode.submit_tool({"action":"tool_call", "tool_name":action["tool_id"], "parameters":action["parameters"]})
        if outcome.category.value == "budget_exhausted": raise ValueError("reference trajectory exhausted budget")
    contexts.append(episode.public_context().to_dict())
    if FORBIDDEN & _keys(contexts[-1]):
        audit["leaks"] += 1
    if episode.submit_answer(episode.public_state["current_value"]) is not M18V2EvaluationCategory.SUCCESS: raise ValueError("reference answer unreachable")
    return contexts, episode, audit


def _audit(values: tuple[M18V3Case, ...]) -> dict[str, Any]:
    reachable=uncovered=stale=future=leaks=tool_mismatch=parameter_mismatch=0; max_actions=max_tools=0
    for case in values:
        contexts, episode, state_audit = _trajectory(case)
        reachable += 1; stale += state_audit["stale"]; future += state_audit["future"]
        leaks += state_audit["leaks"]; tool_mismatch += state_audit["tool"]; parameter_mismatch += state_audit["parameters"]
        max_actions=max(max_actions, episode.budget_state.action_cycles); max_tools=max(max_tools, episode.budget_state.tool_attempts)
        for context in contexts:
            action=context["current_action"]
            if action is None: continue
            if set(action["parameters"]) != {"value"} or action["parameters"]["value"] != context["state"]["current_value"]: parameter_mismatch += 1
            if action["tool_id"] != context["capabilities"][0]["tool_id"]: tool_mismatch += 1
    return {"case_count":len(values), "reachable":reachable, "uncovered_public_predicates":uncovered,
            "stale_context_occurrences":stale, "future_context_occurrences":future,
            "truth_leakage_occurrences":leaks, "tool_id_mismatches":tool_mismatch,
            "parameter_contract_mismatches":parameter_mismatch, "max_action_cycles":max_actions,
            "max_tool_attempts":max_tools, "cohort_counts":_counts(values,lambda x:x.cohort.value),
            "difficulty_counts":_counts(values,lambda x:x.difficulty.value),
            "subtype_counts":_counts(tuple(x for x in values if x.failure_subtype),lambda x:x.failure_subtype.value)}


def build() -> tuple[dict[str, Any], dict[str, Any], dict[str, list[dict[str, Any]]]]:
    pilot, formal=cases(); pp,pv=[_static_public(x) for x in pilot],[_private(x) for x in pilot]; fp,fv=[_static_public(x) for x in formal],[_private(x) for x in formal]
    pa,fa=_audit(pilot),_audit(formal)
    split={"suite_identity":M18_V3_SUITE_VERSION,"source_baseline":FREEZE_BASELINE,
           "pilot_ids":[x.case_id for x in pilot],"formal_ids":[x.case_id for x in formal],
           "pilot_membership":[_member(x) for x in pilot],"formal_membership":[_member(x) for x in formal]}
    split["split_hash"]=canonical_hash(split)
    pilot_runs=[M18V3RunIdentity(x.case_id,s,r).run_id for x in pilot for s in SYSTEMS for r in range(1,6)]
    formal_runs=[M18V3RunIdentity(x.case_id,s,r).run_id for x in formal for s in SYSTEMS for r in range(1,6)]
    if len(set(split["pilot_ids"]))!=18 or len(set(split["formal_ids"]))!=162 or set(split["pilot_ids"]) & set(split["formal_ids"]): raise ValueError("invalid v3 split")
    if len(set(pilot_runs))!=360 or len(set(formal_runs))!=3240 or set(pilot_runs)&set(formal_runs): raise ValueError("invalid v3 run universe")
    core={"suite_identity":M18_V3_SUITE_VERSION,"environment_id":M18_V3_ENVIRONMENT_ID,"evaluator_id":M18_V3_EVALUATOR_ID,
          "runtime_id":M18_V3_RUNTIME_ID,"budget_id":M18_V3_BUDGET_ID,"public_action_contract_id":M18_V3_PUBLIC_ACTION_CONTRACT_ID,
          "run_id_schema":"m18_v3_logical_run_id_v1","source_baseline":FREEZE_BASELINE,"repetitions":[1,2,3,4,5],
          "pilot":{**pa,"public_hash":canonical_hash(pp),"private_hash":canonical_hash(pv),"run_count":len(pilot_runs)},
          "formal":{**fa,"public_hash":canonical_hash(fp),"private_hash":canonical_hash(fv),"run_count":len(formal_runs)},
          "split_hash":split["split_hash"],"freeze_status":"FROZEN","real_execution_authorized":False}
    manifest={**core,"manifest_hash":canonical_hash(core)}
    return split,manifest,{"pilot_public":pp,"pilot_private":pv,"formal_public":fp,"formal_private":fv}


def write(root: Path=ROOT) -> dict[str, Any]:
    split,manifest,fixtures=build(); files={root/"pilot/public_cases.json":fixtures["pilot_public"],root/"pilot/private_cases.json":fixtures["pilot_private"],root/"formal/public_cases.json":fixtures["formal_public"],root/"formal/private_cases.json":fixtures["formal_private"],root/"manifests/m18_suite_v3_split.json":split,root/"manifests/m18_suite_v3_manifest.json":manifest}
    for path,value in files.items():
        content=canonical_json(value)+"\n"
        if path.exists() and path.read_text(encoding="utf-8") != content: raise ValueError("refusing frozen v3 overwrite")
        path.parent.mkdir(parents=True,exist_ok=True); path.write_text(content,encoding="utf-8")
    return manifest


def load_and_validate(root: Path=ROOT) -> dict[str, Any]:
    split,manifest,fixtures=build(); expected={root/"pilot/public_cases.json":fixtures["pilot_public"],root/"pilot/private_cases.json":fixtures["pilot_private"],root/"formal/public_cases.json":fixtures["formal_public"],root/"formal/private_cases.json":fixtures["formal_private"],root/"manifests/m18_suite_v3_split.json":split,root/"manifests/m18_suite_v3_manifest.json":manifest}
    for path,value in expected.items():
        if not path.exists() or json.loads(path.read_text(encoding="utf-8")) != value: raise ValueError("frozen v3 artifact drift")
    return manifest
