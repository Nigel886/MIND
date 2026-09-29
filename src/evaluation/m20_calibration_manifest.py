"""Canonical M20 calibration manifest; identity validation only, never execution."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Mapping
from src.evaluation.m20_harness import M20Condition, M20_METRIC_VERSION, M20_PROTOCOL_ID, canonical_hash, canonical_json
from src.evaluation.m20_real_case_source import M20_REAL_CASE_REPETITIONS, real_case_definitions, real_case_source_digest
from src.evaluation.m20_real_execution_configuration import M20_REAL_PROVIDER_CONFIGURATION, M20_REAL_RESOURCE_CEILING

M20_CALIBRATION_MANIFEST_VERSION = "m20_calibration_manifest_v1"
M20_CALIBRATION_RETRY_FAILURE_ID = "m20_provider_client_retry_v1"
M20_CALIBRATION_REPLACEMENT_RULE = "m20_one_linked_infrastructure_provider_replacement_v1"

def _pair_id(case_id: str, repetition: int) -> str:
    return canonical_hash({"suite":"m20_suite_v1","case":case_id,"repetition":repetition,"conditions":[M20Condition.MIND_ADAPTIVE.value,M20Condition.MIND_FIXED.value]})

def build_manifest() -> dict[str, Any]:
    cases = real_case_definitions()
    entries=[]
    for case_index, case in enumerate(cases):
        for repetition in range(1, M20_REAL_CASE_REPETITIONS + 1):
            pair_id=_pair_id(case.case_id,repetition)
            order=(M20Condition.MIND_ADAPTIVE.value,M20Condition.MIND_FIXED.value) if (case_index+repetition)%2 else (M20Condition.MIND_FIXED.value,M20Condition.MIND_ADAPTIVE.value)
            entries.append({"pair_id":pair_id,"case_id":case.case_id,"payload_digest":case.payload_digest,"cohort":case.cohort,"cluster_id":case.cluster_id,"repetition":repetition,"conditions":list(order)})
    core={"version":M20_CALIBRATION_MANIFEST_VERSION,"suite_id":"m20_suite_v1","environment_id":"m20_environment_v1","evaluator_id":"m20_evaluator_v1","metric_version":M20_METRIC_VERSION,"statistical_protocol":M20_PROTOCOL_ID,"case_source_version":"m20_real_case_source_v1","case_source_digest":real_case_source_digest(),"provider_hash":M20_REAL_PROVIDER_CONFIGURATION.identity_hash,"resource_ceiling_identity":M20_REAL_RESOURCE_CEILING.identity,"retry_failure_identity":M20_CALIBRATION_RETRY_FAILURE_ID,"replacement_rule":M20_CALIBRATION_REPLACEMENT_RULE,"repetitions":M20_REAL_CASE_REPETITIONS,"ordering_rule":"m20_pair_counterbalance_v1","pairs":entries}
    core["ordering_identity"]=canonical_hash({"rule":core["ordering_rule"],"pairs":[(x["pair_id"],x["conditions"]) for x in entries]})
    return {**core,"digest":canonical_hash(core)}

def validate_manifest(value: Mapping[str,Any]) -> None:
    expected=build_manifest(); candidate=dict(value); digest=candidate.pop("digest",None)
    if digest != canonical_hash(candidate) or candidate != {k:v for k,v in expected.items() if k!="digest"}: raise ValueError("calibration manifest mismatch")

def persist_manifest(path: Path) -> dict[str,Any]:
    value=build_manifest(); path.write_text(canonical_json(value)+"\n",encoding="utf-8"); return value

def load_manifest(path: Path) -> dict[str,Any]:
    value=json.loads(path.read_text(encoding="utf-8")); validate_manifest(value); return value

def require_manifest(value: Mapping[str,Any] | None) -> None:
    if value is None: raise ValueError("calibration manifest is required")
    validate_manifest(value)
    raise PermissionError("provider execution remains unauthorized after manifest freeze")
