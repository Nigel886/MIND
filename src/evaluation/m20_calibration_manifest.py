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
M20_OPENAI_PROVIDER_HASH = "910b2b5bf28308d6491af4010e3cc108a38e6dbb49613e27bbc9e4493d41c8f1"
M20_CALIBRATION_RETRY_FAILURE_ID = "m20_provider_client_retry_v1"
M20_DEEPSEEK_RETRY_FAILURE_ID = "m20_deepseek_provider_client_retry_v1"
M20_CALIBRATION_REPLACEMENT_RULE = "m20_one_linked_infrastructure_provider_replacement_v1"


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


def persist_manifest(path: Path) -> dict[str, Any]:
    value = build_manifest()
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")
    return value


def persist_deepseek_manifest(path: Path) -> dict[str, Any]:
    value = build_deepseek_manifest()
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


def require_manifest(value: Mapping[str, Any] | None) -> None:
    """Only v2 reaches this authority gate, which remains closed for #243."""
    if value is None:
        raise ValueError("calibration manifest is required")
    validate_deepseek_manifest(value)
    raise PermissionError("provider execution remains unauthorized after manifest freeze")
