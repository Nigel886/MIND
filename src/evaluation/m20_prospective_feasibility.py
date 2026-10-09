"""Offline-only implementation of the frozen M20 task/evaluator feasibility study."""
from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import os
from pathlib import Path
from typing import Any, Mapping
from tempfile import NamedTemporaryFile
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.evaluation.m20_deepseek_execution import M20DeepSeekProposalAdapter, Transport
from src.evaluation.m20_evaluator_failure_diagnostics import M20EvaluatorDiagnosticStore, diagnose_after_evaluator_handoff
from src.evaluation.m20_financial_control import (M20FeasibilityFinancialLedger, M20FeasibilityFinancialPolicy,
    require_verified_production_tokenizer)
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
M20_FEASIBILITY_LIVE_AUTHORIZATION_SCHEMA = "m20_feasibility_owner_live_authorization_v1"
M20_FEASIBILITY_SIGNED_AUTHORIZATION_SCHEMA = "m20_feasibility_signed_authorization_v1"
M20_FEASIBILITY_TRUST_ANCHOR_SCHEMA = "m20_feasibility_issuer_trust_anchor_v1"
M20_FEASIBILITY_LIVE_BUDGET_SCHEMA = "m20_feasibility_live_budget_ledger_v1"
M20_FEASIBILITY_OWNER_AUTHORITY = "owner_controlled_authorization"


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


def feasibility_live_authorization_payload(manifest: Mapping[str, Any] | None = None,
                                           financial_policy: M20FeasibilityFinancialPolicy | None = None) -> dict[str, Any]:
    """Exact future artifact contract; this function does not issue an artifact."""
    frozen = build_feasibility_manifest() if manifest is None else dict(manifest)
    validate_feasibility_manifest(frozen)
    original_limit = len(frozen["work_items"]) * 8
    replacement_limit = original_limit
    payload = {"schema": M20_FEASIBILITY_LIVE_AUTHORIZATION_SCHEMA, "authority": M20_FEASIBILITY_OWNER_AUTHORITY,
             "purpose": "m20_fixed_only_task_evaluator_feasibility", "protocol": frozen["protocol"],
            "manifest_version": frozen["version"], "manifest_digest": frozen["digest"],
            "membership_digest": frozen["manifest_digest"], "namespace": frozen["namespace"],
            "condition": frozen["condition"], "work_ids": [item["work_id"] for item in frozen["work_items"]],
             "case_source_digest": frozen["case_source_digest"], "provider_hash": frozen["provider_hash"],
             "runtime_identity": frozen["runtime_identity"], "resource_ceiling_identity": frozen["resource_ceiling_identity"],
             "diagnostic_identity": frozen["diagnostic_identity"],
             "original_logical_provider_interaction_limit": original_limit,
             "replacement_logical_provider_interaction_limit": replacement_limit,
             "maximum_logical_provider_interactions": original_limit + replacement_limit,
             "operator_stop_required": True}
    if financial_policy is not None:
        payload["financial_policy"] = financial_policy.canonical()
    return payload


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def load_feasibility_live_authorization(path: Path, trust_anchor: Path, manifest: Mapping[str, Any] | None = None,
                                        financial_policy: M20FeasibilityFinancialPolicy | None = None) -> dict[str, Any]:
    try:
        value, anchors = json.loads(path.read_text(encoding="utf-8")), json.loads(trust_anchor.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PermissionError("prospective feasibility live authorization is absent or invalid") from error
    if not isinstance(value, Mapping) or not isinstance(anchors, Mapping) or anchors.get("schema") != M20_FEASIBILITY_TRUST_ANCHOR_SCHEMA:
        raise PermissionError("prospective feasibility live authorization/trust anchor invalid")
    payload, issuer, algorithm, signature = value.get("payload"), value.get("issuer"), value.get("algorithm"), value.get("signature")
    trusted = anchors.get("issuers", {}).get(issuer) if isinstance(anchors.get("issuers"), Mapping) else None
    if (not isinstance(payload, Mapping) or algorithm != "Ed25519" or not isinstance(signature, str) or
            not isinstance(trusted, Mapping) or trusted.get("algorithm") != "Ed25519" or not isinstance(trusted.get("public_key_b64"), str)):
        raise PermissionError("prospective feasibility issuer/signature is invalid")
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(trusted["public_key_b64"], validate=True)).verify(base64.b64decode(signature, validate=True), _canonical_bytes(payload))
    except (ValueError, InvalidSignature) as error:
        raise PermissionError("prospective feasibility signature verification failed") from error
    if financial_policy is None:
        raise PermissionError("financial policy is required for live authorization")
    expected = feasibility_live_authorization_payload(manifest, financial_policy)
    if dict(payload) != expected:
        raise PermissionError("prospective feasibility live authorization mismatch")
    return dict(payload)


class M20FeasibilityLiveBudget:
    """Durable, restrictive-only aggregate provider-operation admission."""
    def __init__(self, root: Path, authorization: Mapping[str, Any], operator_stop_path: Path) -> None:
        if not isinstance(operator_stop_path, Path):
            raise TypeError("operator stop path is required")
        self.root, self.authorization, self.operator_stop_path = root, dict(authorization), operator_stop_path
        self.path = root / ".m20_execution_control" / "live_budget.json"
        self.authorization_digest = canonical_hash(self.authorization)
        self.limits = {
            "original": self.authorization["original_logical_provider_interaction_limit"],
            "replacement": self.authorization["replacement_logical_provider_interaction_limit"],
            "total": self.authorization["maximum_logical_provider_interactions"],
        }
        if (not all(isinstance(value, int) and value >= 0 for value in self.limits.values()) or
                self.limits["total"] != self.limits["original"] + self.limits["replacement"]):
            raise PermissionError("prospective feasibility live budget is invalid")

    def _expected(self) -> dict[str, Any]:
        return {"schema": M20_FEASIBILITY_LIVE_BUDGET_SCHEMA,
                "authorization_digest": self.authorization_digest, "limits": self.limits}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {**self._expected(), "consumed": {"original": 0, "replacement": 0, "total": 0}}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise PermissionError("prospective feasibility live budget is unreadable") from error
        if (not isinstance(value, Mapping) or {key: value.get(key) for key in self._expected()} != self._expected() or
                not isinstance(value.get("consumed"), Mapping)):
            raise PermissionError("prospective feasibility live budget binding mismatch")
        consumed = value["consumed"]
        if (set(consumed) != {"original", "replacement", "total"} or
                not all(isinstance(consumed[key], int) and consumed[key] >= 0 for key in consumed) or
                consumed["total"] != consumed["original"] + consumed["replacement"]):
            raise PermissionError("prospective feasibility live budget state is invalid")
        return dict(value)

    def _persist(self, value: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=self.path.parent, suffix=".tmp") as handle:
            handle.write(json.dumps(dict(value), sort_keys=True, separators=(",", ":")) + "\n")
            temporary = Path(handle.name)
        os.replace(temporary, self.path)

    def admit(self, replacement: bool = False) -> None:
        if self.operator_stop_path.exists():
            raise M20FeasibilityExecutionBlocked("prospective feasibility operator stop requested")
        bucket = "replacement" if replacement else "original"
        value = self._load(); consumed = dict(value["consumed"])
        if consumed[bucket] >= self.limits[bucket] or consumed["total"] >= self.limits["total"]:
            raise M20FeasibilityExecutionBlocked("prospective feasibility live budget exhausted")
        consumed[bucket] += 1; consumed["total"] += 1
        self._persist({**self._expected(), "consumed": consumed})

    def ensure_not_stopped(self) -> None:
        if self.operator_stop_path.exists():
            raise M20FeasibilityExecutionBlocked("prospective feasibility operator stop requested")


class M20FeasibilityExecutionBlocked(InterruptedError):
    """A pre-transport operator or aggregate-budget stop; never a provider failure."""


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
            return tuple(self._run(item, transport, store) for item in self._items)
        finally:
            self._diagnostic_store = None

    def run_live(self, authorization_artifact: Path, trust_anchor: Path, transport: Transport, root: Path,
                 *, operator_stop_path: Path | None = None, financial_policy: M20FeasibilityFinancialPolicy | None = None,
                 token_counter: Any | None = None) -> tuple[M20ExecutionRecord, ...]:
        """Future live path: exact artifact validation always precedes adapter creation."""
        authorization = load_feasibility_live_authorization(authorization_artifact, trust_anchor, self.frozen, financial_policy)
        if not callable(transport):
            raise TypeError("transport is required")
        if operator_stop_path is None:
            raise PermissionError("operator stop path is required")
        if financial_policy is None or not callable(token_counter):
            raise PermissionError("provider-compatible financial token control is required")
        require_verified_production_tokenizer(financial_policy, token_counter)
        control = M20FeasibilityLiveBudget(root, authorization, operator_stop_path)
        financial = M20FeasibilityFinancialLedger(root, authorization, financial_policy, token_counter, operator_stop_path)
        control.ensure_not_stopped()
        store = self.store(root); self._diagnostic_store = self.diagnostic_store(root)
        try:
            return tuple(self._run(item, transport, store, control, financial) for item in self._items)
        finally:
            self._diagnostic_store = None

    def replacement_item(self, original: M20ExecutionRecord) -> M20FeasibilityWorkItem:
        known = next((item for item in self._items if item.spec.execution_id == original.execution_id), None)
        if known is None:
            raise PermissionError("replacement original is not an authorized feasibility work")
        return M20FeasibilityWorkItem( self.harness.replacement(original).execution_id,
            self.harness.replacement(original))

    def run_live_replacement(self, authorization_artifact: Path, trust_anchor: Path, original_work_id: str, transport: Transport, root: Path,
                             *, operator_stop_path: Path | None = None, financial_policy: M20FeasibilityFinancialPolicy | None = None,
                             token_counter: Any | None = None, interrupt_before_execution: bool = False) -> M20ExecutionRecord:
        authorization = load_feasibility_live_authorization(authorization_artifact, trust_anchor, self.frozen, financial_policy)
        if operator_stop_path is None:
            raise PermissionError("operator stop path is required")
        if financial_policy is None or not callable(token_counter):
            raise PermissionError("provider-compatible financial token control is required")
        require_verified_production_tokenizer(financial_policy, token_counter)
        original_item = next((item for item in self._items if item.work_id == original_work_id), None)
        if original_item is None:
            raise PermissionError("replacement original is unknown")
        store = self.store(root); original = store.completed_record(original_item.spec); replacement = self.replacement_item(original)
        control = M20FeasibilityLiveBudget(root, authorization, operator_stop_path)
        financial = M20FeasibilityFinancialLedger(root, authorization, financial_policy, token_counter, operator_stop_path)
        control.ensure_not_stopped()
        self.harness._provenance_overrides.update({"work_id": replacement.work_id, "original_work_id": original_item.work_id,
            "replacement_work_id": replacement.work_id, "replacement_index": "1", "replacement_eligibility": original.outcome.value})
        self._diagnostic_store = self.diagnostic_store(root)
        try:
            return self.harness.run(replacement.spec, M20FixedAdapter(M20DeepSeekProposalAdapter(
                transport, answer_termination_enabled=True, admit_logical_operation=lambda: control.admit(True),
                financial_ledger=financial, execution_id=replacement.spec.execution_id)), store,
                                    interrupt_before_execution=interrupt_before_execution)
        finally:
            self._diagnostic_store = None

    def _run(self, item: M20FeasibilityWorkItem, transport: Transport, store: M20EvidenceStore,
             control: M20FeasibilityLiveBudget | None = None,
             financial: M20FeasibilityFinancialLedger | None = None) -> M20ExecutionRecord:
        if item not in self._items:
            raise PermissionError("unrecognized feasibility work")
        self.harness._provenance_overrides["work_id"] = item.work_id
        admission = None if control is None else control.admit
        return self.harness.run(item.spec, M20FixedAdapter(M20DeepSeekProposalAdapter(
            transport, answer_termination_enabled=True, admit_logical_operation=admission,
            financial_ledger=financial, execution_id=(item.spec.execution_id if financial is not None else None))), store)


def descriptive_projection(records: tuple[Mapping[str, Any], ...], diagnostics: tuple[Any, ...]) -> dict[str, Any]:
    if len(records) != 24 or len({item["execution_id"] for item in records}) != 24:
        raise ValueError("feasibility evidence membership is incomplete")
    outcomes = {key: sum(item["outcome"] == key for item in records) for key in ("success", "failure_or_incorrect", "incomplete")}
    classifications = {key: sum(getattr(item, "classification", None) == key for item in diagnostics) for key in ("success", "answer_payload_failure", "prerequisite_failure", "combined_failure", "unknown_other")}
    return {"original_works": len(records), "outcomes": outcomes, "diagnostic_classifications": classifications,
            "unknown_rate": classifications["unknown_other"] / len(records),
            "provider_interactions": [item["telemetry"]["provider_interactions"] for item in records],
            "ceiling_exhaustion": sum(item["outcome"] == "incomplete" for item in records)}
