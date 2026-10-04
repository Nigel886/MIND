"""Canonical M20 calibration manifests; validation only, never execution."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.evaluation.m20_harness import M20Condition, M20_METRIC_VERSION, M20_PROTOCOL_ID, canonical_hash, canonical_json
from src.evaluation.m20_real_case_source import M20_REAL_CASE_REPETITIONS, real_case_definitions, real_case_source_digest
from src.evaluation.m20_real_execution_configuration import M20_REAL_PROVIDER_CONFIGURATION, M20_REAL_RESOURCE_CEILING

M20_CALIBRATION_MANIFEST_VERSION = "m20_calibration_manifest_v1"
M20_DEEPSEEK_CALIBRATION_MANIFEST_VERSION = "m20_calibration_manifest_v2"
M20_POSTREMEDIATION_CALIBRATION_PROTOCOL = "m20_calibration_postremediation_v1"
M20_POSTREMEDIATION_CALIBRATION_NAMESPACE = "m20_calibration_postremediation_v1"
M20_POSTREMEDIATION_CALIBRATION_RESULT_PATH = "evaluation/results/m20_calibration_postremediation_v1"
M20_POSTREMEDIATION_CALIBRATION_MANIFEST_VERSION = "m20_calibration_manifest_v3"
M20_POSTREMEDIATION_ORDERING_RULE = "m20_pair_counterbalance_v2"
M20_POSTREMEDIATION_RUNTIME_VERSION = "m20_postremediation_runtime_generation_v1"
M20_OPENAI_PROVIDER_HASH = "910b2b5bf28308d6491af4010e3cc108a38e6dbb49613e27bbc9e4493d41c8f1"
M20_CALIBRATION_RETRY_FAILURE_ID = "m20_provider_client_retry_v1"
M20_DEEPSEEK_RETRY_FAILURE_ID = "m20_deepseek_provider_client_retry_v1"
M20_CALIBRATION_REPLACEMENT_RULE = "m20_one_linked_infrastructure_provider_replacement_v1"


def _postremediation_runtime() -> dict[str, str]:
    """Canonical identity for the production path validated by diagnostic v5."""
    return {
        "version": M20_POSTREMEDIATION_RUNTIME_VERSION,
        "envelope_normalization": "m20_deepseek_envelope_normalization_v1",
        "retry_persistence": "m20_provider_operation_retry_persistence_v1",
        "resource_admission": "m20_pretransport_provider_admission_v1",
        "response_telemetry_schema": "m20_deepseek_response_shape_telemetry_v1",
        "canonical_evidence_validation": "m20_execution_record_v1",
        "harness": "m20_evaluation_harness_v1",
        "provider_request_contract": "m20_deepseek_public_proposal_v1",
    }


def _postremediation_scientific_contract() -> dict[str, Any]:
    return {
        "primary_contrast": [M20Condition.MIND_ADAPTIVE.value, M20Condition.MIND_FIXED.value],
        "quality_estimand": "adaptive_minus_fixed_success_probability",
        "quality_noninferiority_margin": 0.05,
        "resource_endpoint": "logical_provider_interactions_per_attempted_episode",
        "resource_mre": -0.25,
        "gate_1": "quality_noninferiority",
        "gate_2": "resource_reduction",
        "inference": "paired_case_cluster_bootstrap",
        "one_sided_alpha_per_gate": 0.025,
        "joint_power_target": 0.90,
        "statistical_protocol": M20_PROTOCOL_ID,
    }


def _postremediation_comparator_contract() -> dict[str, str]:
    return {
        "adaptive": "m20_m19_adaptive_adapter_v1",
        "fixed": "m20_fixed_cycle_adapter_v1",
        "fixed_schedule": "m20_fixed_cycle_schedule_v1",
        "shared_provider_request_parser": "m20_deepseek_public_proposal_v1",
        "shared_evaluator": "m20_evaluator_v1",
        "shared_persistence": "m20_execution_record_v1",
    }


def _postremediation_failure_contract() -> dict[str, Any]:
    return {
        "replacement_rule": M20_CALIBRATION_REPLACEMENT_RULE,
        "maximum_linked_replacements": 1,
        "eligible_replacement_outcomes": ["provider_failure", "infrastructure_failure"],
        "performance_rerun": "prohibited",
        "original_execution": "immutable",
        "replacement_link": "required",
        "provider_protocol_failure": "typed_provider_failure",
        "infrastructure_failure": "typed_infrastructure_failure",
        "performance_outcome": "never_repaired",
    }


def _pair_id(case_id: str, repetition: int) -> str:
    return canonical_hash({"suite": "m20_suite_v1", "case": case_id, "repetition": repetition,
                           "conditions": [M20Condition.MIND_ADAPTIVE.value, M20Condition.MIND_FIXED.value]})


def _pairs() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for case_index, case in enumerate(real_case_definitions()):
        for repetition in range(1, M20_REAL_CASE_REPETITIONS + 1):
            order = ((M20Condition.MIND_ADAPTIVE.value, M20Condition.MIND_FIXED.value)
                     if (case_index + repetition) % 2 else
                     (M20Condition.MIND_FIXED.value, M20Condition.MIND_ADAPTIVE.value))
            entries.append({"pair_id": _pair_id(case.case_id, repetition), "case_id": case.case_id,
                            "payload_digest": case.payload_digest, "cohort": case.cohort,
                            "cluster_id": case.cluster_id, "repetition": repetition,
                            "conditions": list(order)})
    return entries


def _build_manifest(*, version: str, provider_hash: str, retry_failure_identity: str) -> dict[str, Any]:
    pairs = _pairs()
    core = {"version": version, "suite_id": "m20_suite_v1", "environment_id": "m20_environment_v1",
            "evaluator_id": "m20_evaluator_v1", "metric_version": M20_METRIC_VERSION,
            "statistical_protocol": M20_PROTOCOL_ID, "case_source_version": "m20_real_case_source_v1",
            "case_source_digest": real_case_source_digest(), "provider_hash": provider_hash,
            "resource_ceiling_identity": M20_REAL_RESOURCE_CEILING.identity,
            "retry_failure_identity": retry_failure_identity,
            "replacement_rule": M20_CALIBRATION_REPLACEMENT_RULE,
            "repetitions": M20_REAL_CASE_REPETITIONS, "ordering_rule": "m20_pair_counterbalance_v1", "pairs": pairs}
    core["ordering_identity"] = canonical_hash({"rule": core["ordering_rule"],
                                                 "pairs": [(pair["pair_id"], pair["conditions"]) for pair in pairs]})
    return {**core, "digest": canonical_hash(core)}


def build_manifest() -> dict[str, Any]:
    """Reconstruct superseded OpenAI-bound v1 only as historical evidence."""
    return _build_manifest(version=M20_CALIBRATION_MANIFEST_VERSION, provider_hash=M20_OPENAI_PROVIDER_HASH,
                           retry_failure_identity=M20_CALIBRATION_RETRY_FAILURE_ID)


def build_deepseek_manifest() -> dict[str, Any]:
    """Build the sole prospective v2 manifest bound to frozen DeepSeek identity."""
    return _build_manifest(version=M20_DEEPSEEK_CALIBRATION_MANIFEST_VERSION,
                           provider_hash=M20_REAL_PROVIDER_CONFIGURATION.identity_hash,
                           retry_failure_identity=M20_DEEPSEEK_RETRY_FAILURE_ID)


def _postremediation_case_membership() -> list[dict[str, str]]:
    cases = real_case_definitions()
    if len(cases) != 12 or any(not case.eligible for case in cases):
        raise ValueError("post-remediation calibration requires exactly 12 eligible cases")
    return [{"case_id": case.case_id, "cohort": case.cohort,
             "payload_digest": case.payload_digest, "cluster_id": case.cluster_id}
            for case in cases]


def _postremediation_ordering(membership: list[dict[str, str]]) -> tuple[str, dict[tuple[str, int], list[str]]]:
    keys = [(canonical_hash({"ordering_rule": M20_POSTREMEDIATION_ORDERING_RULE,
                             "case_id": item["case_id"], "repetition": repetition}),
             item["case_id"], repetition)
            for item in membership for repetition in range(1, M20_REAL_CASE_REPETITIONS + 1)]
    keys.sort()
    if len(keys) != 60:
        raise ValueError("post-remediation calibration ordering cardinality mismatch")
    adaptive_first = [M20Condition.MIND_ADAPTIVE.value, M20Condition.MIND_FIXED.value]
    fixed_first = list(reversed(adaptive_first))
    assignment = {(case_id, repetition): (adaptive_first if index < len(keys) // 2 else fixed_first)
                  for index, (_, case_id, repetition) in enumerate(keys)}
    identity = canonical_hash({"rule": M20_POSTREMEDIATION_ORDERING_RULE,
                               "ranked_pairs": [(key, case_id, repetition)
                                                for key, case_id, repetition in keys],
                               "assignments": [(case_id, repetition, assignment[(case_id, repetition)])
                                               for _, case_id, repetition in keys]})
    return identity, assignment


def _postremediation_core() -> dict[str, Any]:
    membership = _postremediation_case_membership()
    ordering_identity, _ = _postremediation_ordering(membership)
    runtime = _postremediation_runtime()
    return {
        "protocol": M20_POSTREMEDIATION_CALIBRATION_PROTOCOL,
        "namespace": M20_POSTREMEDIATION_CALIBRATION_NAMESPACE,
        "result_path": M20_POSTREMEDIATION_CALIBRATION_RESULT_PATH,
        "version": M20_POSTREMEDIATION_CALIBRATION_MANIFEST_VERSION,
        "suite_id": "m20_suite_v1",
        "environment_id": "m20_environment_v1",
        "evaluator_id": "m20_evaluator_v1",
        "metric_version": M20_METRIC_VERSION,
        "statistical_protocol": M20_PROTOCOL_ID,
        "scientific_contract": _postremediation_scientific_contract(),
        "comparator_contract": _postremediation_comparator_contract(),
        "case_source_version": "m20_real_case_source_v1",
        "case_source_digest": real_case_source_digest(),
        "case_membership": membership,
        "repetitions": M20_REAL_CASE_REPETITIONS,
        "provider_hash": M20_REAL_PROVIDER_CONFIGURATION.identity_hash,
        "resource_ceiling_identity": M20_REAL_RESOURCE_CEILING.identity,
        "runtime_generation": {**runtime, "identity": canonical_hash(runtime)},
        "ordering_rule": M20_POSTREMEDIATION_ORDERING_RULE,
        "ordering_identity": ordering_identity,
        "failure_replacement_contract": _postremediation_failure_contract(),
    }


def build_postremediation_manifest() -> dict[str, Any]:
    """Build a new non-executable calibration generation after #259/#269/#273."""
    core = _postremediation_core()
    manifest_digest = canonical_hash(core)
    _, assignment = _postremediation_ordering(core["case_membership"])
    pairs: list[dict[str, Any]] = []
    work_items: list[dict[str, Any]] = []
    for case in core["case_membership"]:
        for repetition in range(1, core["repetitions"] + 1):
            conditions = assignment[(case["case_id"], repetition)]
            pair_id = canonical_hash({"protocol": core["protocol"], "manifest_digest": manifest_digest,
                                      "ordering_identity": core["ordering_identity"], "case": case,
                                      "repetition": repetition, "provider_hash": core["provider_hash"],
                                      "resource_ceiling_identity": core["resource_ceiling_identity"],
                                      "runtime_generation": core["runtime_generation"]["identity"]})
            pair = {"pair_id": pair_id, "manifest_digest": manifest_digest, **case,
                    "repetition": repetition, "conditions": list(conditions),
                    "ordering_identity": core["ordering_identity"],
                    "provider_hash": core["provider_hash"],
                    "resource_ceiling_identity": core["resource_ceiling_identity"],
                    "runtime_generation": core["runtime_generation"]["identity"]}
            pairs.append(pair)
            for condition in conditions:
                work_items.append({"work_id": canonical_hash({"pair_id": pair_id, "condition": condition,
                                                                 "manifest_digest": manifest_digest,
                                                                 "namespace": core["namespace"]}),
                                   "pair_id": pair_id, "condition": condition,
                                   "manifest_digest": manifest_digest, "namespace": core["namespace"]})
    if len(pairs) != 60 or len({pair["pair_id"] for pair in pairs}) != 60:
        raise ValueError("post-remediation calibration pair identity mismatch")
    if len(work_items) != 120 or len({item["work_id"] for item in work_items}) != 120:
        raise ValueError("post-remediation calibration work identity mismatch")
    return {**core, "manifest_digest": manifest_digest, "pairs": pairs, "work_items": work_items,
            "digest": canonical_hash({**core, "manifest_digest": manifest_digest,
                                       "pairs": pairs, "work_items": work_items})}


def _validate(value: Mapping[str, Any], expected: Mapping[str, Any], label: str) -> None:
    candidate = dict(value)
    digest = candidate.pop("digest", None)
    if digest != canonical_hash(candidate) or candidate != {key: item for key, item in expected.items() if key != "digest"}:
        raise ValueError(f"{label} calibration manifest mismatch")


def validate_manifest(value: Mapping[str, Any]) -> None:
    """Validate the superseded v1 record only; it is never prospectively executable."""
    _validate(value, build_manifest(), "historical")


def validate_deepseek_manifest(value: Mapping[str, Any]) -> None:
    _validate(value, build_deepseek_manifest(), "DeepSeek")


def validate_postremediation_manifest(value: Mapping[str, Any]) -> None:
    """Fail closed unless the complete post-remediation v3 identity matches."""
    _validate(value, build_postremediation_manifest(), "post-remediation")


def postremediation_work_item(value: Mapping[str, Any], work_id: str) -> dict[str, Any]:
    """Admit only one exact v3 work identity; execution authorization remains external."""
    validate_postremediation_manifest(value)
    item = next((dict(candidate) for candidate in value["work_items"] if candidate["work_id"] == work_id), None)
    if item is None:
        raise ValueError("post-remediation calibration work identity is rejected")
    return item


def persist_manifest(path: Path) -> dict[str, Any]:
    value = build_manifest()
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")
    return value


def persist_deepseek_manifest(path: Path) -> dict[str, Any]:
    value = build_deepseek_manifest()
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")
    return value


def persist_postremediation_manifest(path: Path) -> dict[str, Any]:
    value = build_postremediation_manifest()
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")
    return value


def load_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    validate_manifest(value)
    return value


def load_deepseek_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    validate_deepseek_manifest(value)
    return value


def load_postremediation_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    validate_postremediation_manifest(value)
    return value


def require_manifest(value: Mapping[str, Any] | None) -> None:
    """Only v2 reaches this authority gate, which remains closed for #243."""
    if value is None:
        raise ValueError("calibration manifest is required")
    validate_deepseek_manifest(value)
    raise PermissionError("provider execution remains unauthorized after manifest freeze")
