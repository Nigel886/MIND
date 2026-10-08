"""Offline-only implementation of the frozen M20 task/evaluator feasibility study."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.evaluation.m20_deepseek_execution import M20DeepSeekProposalAdapter, Transport
from src.evaluation.m20_evaluator_failure_diagnostics import M20EvaluatorDiagnosticStore, diagnose_after_evaluator_handoff
from src.evaluation.m20_harness import (M20Condition, M20ConditionRegistry, M20EvidenceStore,
    M20ExecutionRecord, M20ExecutionSpec, M20FixedAdapter, M20Harness, M20Manifest,
    M20Namespace, M20PairingMetadata, M20ResourceCeiling, canonical_hash)
from src.evaluation.m20_real_case_source import M20RealEnvironment, M20RealEvaluator, real_cases, real_case_source_digest
from src.evaluation.m20_real_execution_configuration import M20_REAL_PROVIDER_CONFIGURATION, M20_REAL_RESOURCE_CEILING_V2

M20_FEASIBILITY_PROTOCOL = "m20_task_evaluator_feasibility_v1"
M20_FEASIBILITY_NAMESPACE = "m20_task_evaluator_feasibility_v1"
M20_FEASIBILITY_RESULT_PATH = "evaluation/results/m20_task_evaluator_feasibility_v1"
M20_FEASIBILITY_MANIFEST_VERSION = "m20_feasibility_manifest_v1"
M20_FEASIBILITY_RUNTIME = "m20_feasibility_runtime_generation_v1"
M20_FEASIBILITY_AUTHORIZATION_SCHEMA = "m20_feasibility_synthetic_authorization_v1"


def build_feasibility_manifest() -> dict[str, Any]:
    """Deterministically freeze the 24 Fixed-only original work identities."""
    cases = real_cases()
    membership = [{"case_id": case.public.case_id, "cohort": case.public.cohort,
                   "cluster_id": case.cluster_id, "payload_digest": case.payload_digest} for case in cases]
    core = {"protocol": M20_FEASIBILITY_PROTOCOL, "namespace": M20_FEASIBILITY_NAMESPACE,
            "result_path": M20_FEASIBILITY_RESULT_PATH, "version": M20_FEASIBILITY_MANIFEST_VERSION,
            "suite_id": "m20_suite_v1", "environment_id": "m20_environment_v1", "evaluator_id": "m20_evaluator_v1",
            "case_source_version": "m20_real_case_source_v1", "case_source_digest": real_case_source_digest(),
            "provider_hash": M20_REAL_PROVIDER_CONFIGURATION.identity_hash,
            "resource_ceiling_identity": M20_REAL_RESOURCE_CEILING_V2.identity,
            "runtime_identity": canonical_hash({"version": M20_FEASIBILITY_RUNTIME, "answer_readiness": "m20_public_answer_readiness_v1", "diagnostic": "m20_evaluator_failure_diagnostic_v1"}),
            "diagnostic_identity": "m20_evaluator_failure_diagnostic_v1", "condition": M20Condition.MIND_FIXED.value,
            "repetitions": 2, "case_membership": membership}
    identity = canonical_hash(core)
    works = []
    for case in membership:
        for repetition in range(1, 3):
            work_id = canonical_hash({"manifest": identity, "namespace": M20_FEASIBILITY_NAMESPACE,
                                      "case": case, "repetition": repetition, "condition": M20Condition.MIND_FIXED.value})
            works.append({"work_id": work_id, **case, "repetition": repetition, "condition": M20Condition.MIND_FIXED.value})
    result = {**core, "manifest_digest": identity, "work_items": works}
    return {**result, "digest": canonical_hash(result)}


def validate_feasibility_manifest(value: Mapping[str, Any]) -> None:
    expected = build_feasibility_manifest()
    if not isinstance(value, Mapping) or dict(value) != expected:
        raise ValueError("prospective feasibility manifest mismatch")
    if len(value["case_membership"]) != 12 or len(value["work_items"]) != 24 or len({x["work_id"] for x in value["work_items"]}) != 24:
        raise ValueError("prospective feasibility membership mismatch")


def feasibility_authorization_payload(manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    frozen = build_feasibility_manifest() if manifest is None else dict(manifest)
    validate_feasibility_manifest(frozen)
    return {"schema": M20_FEASIBILITY_AUTHORIZATION_SCHEMA, "protocol": frozen["protocol"],
            "manifest_digest": frozen["digest"], "namespace": frozen["namespace"],
            "work_ids": [item["work_id"] for item in frozen["work_items"]],
            "provider_hash": frozen["provider_hash"], "resource_ceiling_identity": frozen["resource_ceiling_identity"]}


def verify_feasibility_authorization(value: Mapping[str, Any] | None, manifest: Mapping[str, Any] | None = None) -> None:
    if not isinstance(value, Mapping) or dict(value) != feasibility_authorization_payload(manifest):
        raise PermissionError("prospective feasibility synthetic authorization mismatch")


@dataclass(frozen=True)
class M20FeasibilityWorkItem:
    work_id: str
    spec: M20ExecutionSpec


class M20ProspectiveFeasibilityRunner:
    """Dedicated Fixed-only runner. `run_fake` is the sole executable entry point."""
    def __init__(self, manifest: Mapping[str, Any] | None = None) -> None:
        self.frozen = build_feasibility_manifest() if manifest is None else dict(manifest)
        validate_feasibility_manifest(self.frozen)
        cases = real_cases(); ceiling = M20ResourceCeiling(M20_REAL_RESOURCE_CEILING_V2.identity, 16, 8, 8, 8)
        pairing = tuple(M20PairingMetadata(case.public.case_id, case.cluster_id, case.payload_digest,
                         case.environment_id, case.evaluator_id, ceiling.identity) for case in cases)
        model = M20Manifest("m20_suite_v1", "m20_environment_v1", "m20_evaluator_v1", cases,
                            "m20_real_case_source_v1", pairing, ceiling, execution_manifest_digest=self.frozen["digest"])
        self._diagnostic_store: M20EvaluatorDiagnosticStore | None = None
        def diagnostic(spec, case, state, answer, outcome):
            if self._diagnostic_store is not None:
                self._diagnostic_store.persist(diagnose_after_evaluator_handoff(spec.execution_id, case, state, answer, "m20_evaluator_v1", outcome))
        self.harness = M20Harness(model, M20ConditionRegistry(self.frozen["provider_hash"]), M20RealEnvironment(), M20RealEvaluator(),
            {"feasibility_protocol": M20_FEASIBILITY_PROTOCOL, "runtime_identity": self.frozen["runtime_identity"], "diagnostic_identity": self.frozen["diagnostic_identity"]},
            answer_termination_enabled=True, evaluator_handoff_hook=diagnostic)
        self._items = tuple(M20FeasibilityWorkItem(value["work_id"], M20ExecutionSpec("m20_suite_v1", value["case_id"], value["repetition"], M20Condition.MIND_FIXED,
            M20Namespace.FEASIBILITY, self.frozen["digest"], self.frozen["provider_hash"], value["cluster_id"], value["payload_digest"],
            "m20_environment_v1", "m20_evaluator_v1", M20_REAL_RESOURCE_CEILING_V2.identity,
            frozen_pair_id=canonical_hash({"protocol": M20_FEASIBILITY_PROTOCOL, "case": value["case_id"], "repetition": value["repetition"]})) ) for value in self.frozen["work_items"])

    def work_items(self) -> tuple[M20FeasibilityWorkItem, ...]: return self._items
    def store(self, root: Path) -> M20EvidenceStore: return M20EvidenceStore(root, self.harness.manifest, M20Namespace.FEASIBILITY)
    def diagnostic_store(self, root: Path) -> M20EvaluatorDiagnosticStore: return M20EvaluatorDiagnosticStore(root / "private_evaluator_diagnostics")
    def run_fake(self, authorization: Mapping[str, Any] | None, transport: Transport, root: Path) -> tuple[M20ExecutionRecord, ...]:
        verify_feasibility_authorization(authorization, self.frozen)
        if not callable(transport): raise TypeError("fake transport is required")
        store = self.store(root); self._diagnostic_store = self.diagnostic_store(root)
        try:
            result = []
            for item in self._items:
                self.harness._provenance_overrides["work_id"] = item.work_id
                result.append(self.harness.run(item.spec, M20FixedAdapter(M20DeepSeekProposalAdapter(transport, answer_termination_enabled=True)), store))
            return tuple(result)
        finally:
            self._diagnostic_store = None

    def run_live(self, *_: Any, **__: Any) -> None:
        raise PermissionError("prospective feasibility live execution is not authorized")


def descriptive_projection(records: tuple[Mapping[str, Any], ...], diagnostics: tuple[Any, ...]) -> dict[str, Any]:
    if len(records) != 24 or len({item["execution_id"] for item in records}) != 24:
        raise ValueError("feasibility evidence membership is incomplete")
    outcomes = {key: sum(item["outcome"] == key for item in records) for key in ("success", "failure_or_incorrect", "incomplete")}
    classifications = {key: sum(getattr(item, "classification", None) == key for item in diagnostics) for key in ("success", "answer_payload_failure", "prerequisite_failure", "combined_failure", "unknown_other")}
    return {"original_works": len(records), "outcomes": outcomes, "diagnostic_classifications": classifications,
            "unknown_rate": classifications["unknown_other"] / len(records),
            "provider_interactions": [item["telemetry"]["provider_interactions"] for item in records],
            "ceiling_exhaustion": sum(item["outcome"] == "incomplete" for item in records)}
