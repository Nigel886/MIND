"""Offline-only implementation of the frozen M20 task/evaluator feasibility study."""
from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from tempfile import NamedTemporaryFile
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.evaluation.m20_deepseek_execution import M20DeepSeekProposalAdapter, Transport
from src.evaluation.m20_evaluator_failure_diagnostics import M20EvaluatorDiagnosticStore, diagnose_after_evaluator_handoff
from src.evaluation.m20_financial_control import (M20FeasibilityFinancialLedger, M20FeasibilityFinancialPolicy,
    M20OwnerRiskAcceptedFinancialPolicy, require_verified_production_tokenizer)
from src.evaluation.m20_harness import (M20Condition, M20ConditionRegistry, M20EvidenceStore,
    M20ExecutionRecord, M20ExecutionSpec, M20FixedAdapter, M20Harness, M20Manifest,
    M20Namespace, M20PairingMetadata, M20ResourceCeiling, M20_HARNESS_ID,
    derive_first_replacement_spec, canonical_hash)
from src.evaluation.m20_real_case_source import M20RealEnvironment, M20RealEvaluator, real_cases, real_case_source_digest
from src.evaluation.m20_real_execution_configuration import M20_REAL_PROVIDER_CONFIGURATION, M20_REAL_RESOURCE_CEILING_V2

M20_FEASIBILITY_PROTOCOL = "m20_task_evaluator_feasibility_v1"
M20_FEASIBILITY_NAMESPACE = "m20_task_evaluator_feasibility_v1"
M20_FEASIBILITY_RESULT_PATH = "evaluation/results/m20_task_evaluator_feasibility_v1"
M20_FEASIBILITY_MANIFEST_VERSION = "m20_feasibility_manifest_v1"
M20_FEASIBILITY_RUNTIME = "m20_feasibility_runtime_generation_v1"
M20_FEASIBILITY_AUTHORIZATION_SCHEMA = "m20_feasibility_synthetic_authorization_v1"
M20_FEASIBILITY_LIVE_AUTHORIZATION_SCHEMA = "m20_feasibility_owner_live_authorization_v1"
M20_FEASIBILITY_OWNER_RISK_LIVE_AUTHORIZATION_SCHEMA = "m20_feasibility_owner_risk_live_authorization_v2"
M20_FEASIBILITY_OWNER_RISK_LIVE_AUTHORIZATION_SCHEMA_V3 = "m20_feasibility_owner_risk_live_authorization_v3"
M20_FEASIBILITY_SIGNED_AUTHORIZATION_SCHEMA = "m20_feasibility_signed_authorization_v1"
M20_FEASIBILITY_TRUST_ANCHOR_SCHEMA = "m20_feasibility_issuer_trust_anchor_v1"
M20_FEASIBILITY_LIVE_BUDGET_SCHEMA = "m20_feasibility_live_budget_ledger_v1"
M20_FEASIBILITY_OWNER_AUTHORITY = "owner_controlled_authorization"


@dataclass(frozen=True)
class M20FeasibilityGeneration:
    """Immutable execution identity; it does not change the scientific protocol."""
    generation_id: str
    namespace: M20Namespace
    result_path: str
    manifest_version: str
    runtime_version: str
    harness_generation_identity: str
    owner_risk_authorization_schema: str


M20_FEASIBILITY_GENERATION_V1 = M20FeasibilityGeneration(
    "m20_task_evaluator_feasibility_generation_v1", M20Namespace.FEASIBILITY,
    M20_FEASIBILITY_RESULT_PATH, M20_FEASIBILITY_MANIFEST_VERSION,
    M20_FEASIBILITY_RUNTIME, "m20_real_case_source_v1",
    M20_FEASIBILITY_OWNER_RISK_LIVE_AUTHORIZATION_SCHEMA,
)
M20_FEASIBILITY_GENERATION_V2 = M20FeasibilityGeneration(
    "m20_task_evaluator_feasibility_generation_v2", M20Namespace.FEASIBILITY_V2,
    "evaluation/results/m20_task_evaluator_feasibility_v2", "m20_feasibility_manifest_v2",
    "m20_feasibility_runtime_generation_v2", "m20_task_evaluator_feasibility_generation_v2",
    M20_FEASIBILITY_OWNER_RISK_LIVE_AUTHORIZATION_SCHEMA_V3,
)


def _generation(generation: M20FeasibilityGeneration | None) -> M20FeasibilityGeneration:
    value = M20_FEASIBILITY_GENERATION_V1 if generation is None else generation
    if value is not M20_FEASIBILITY_GENERATION_V1 and value is not M20_FEASIBILITY_GENERATION_V2:
        raise PermissionError("unrecognized feasibility generation")
    return value


def build_feasibility_manifest(generation: M20FeasibilityGeneration | None = None) -> dict[str, Any]:
    """Deterministically freeze the 24 Fixed-only original work identities."""
    generation = _generation(generation)
    cases = real_cases()
    membership = [{"case_id": case.public.case_id, "cohort": case.public.cohort,
                   "cluster_id": case.cluster_id, "payload_digest": case.payload_digest} for case in cases]
    core = {"protocol": M20_FEASIBILITY_PROTOCOL, "namespace": generation.namespace.value,
            "result_path": generation.result_path, "version": generation.manifest_version,
            "suite_id": "m20_suite_v1", "environment_id": "m20_environment_v1", "evaluator_id": "m20_evaluator_v1",
            "case_source_version": "m20_real_case_source_v1", "case_source_digest": real_case_source_digest(),
            "provider_hash": M20_REAL_PROVIDER_CONFIGURATION.identity_hash,
            "resource_ceiling_identity": M20_REAL_RESOURCE_CEILING_V2.identity,
            "runtime_identity": canonical_hash({"version": generation.runtime_version, "answer_readiness": "m20_public_answer_readiness_v1", "diagnostic": "m20_evaluator_failure_diagnostic_v1"}),
            "diagnostic_identity": "m20_evaluator_failure_diagnostic_v1", "condition": M20Condition.MIND_FIXED.value,
            "repetitions": 2, "case_membership": membership}
    if generation is M20_FEASIBILITY_GENERATION_V2:
        core["generation_id"] = generation.generation_id
    identity = canonical_hash(core)
    works = []
    for case in membership:
        for repetition in range(1, 3):
            work_input = {"manifest": identity, "namespace": generation.namespace.value,
                          "case": case, "repetition": repetition, "condition": M20Condition.MIND_FIXED.value}
            if generation is M20_FEASIBILITY_GENERATION_V2:
                work_input["generation_id"] = generation.generation_id
            work_id = canonical_hash(work_input)
            works.append({"work_id": work_id, **case, "repetition": repetition, "condition": M20Condition.MIND_FIXED.value})
    result = {**core, "manifest_digest": identity, "work_items": works}
    return {**result, "digest": canonical_hash(result)}


def validate_feasibility_manifest(value: Mapping[str, Any], generation: M20FeasibilityGeneration | None = None) -> None:
    expected = build_feasibility_manifest(generation)
    if not isinstance(value, Mapping) or dict(value) != expected:
        raise ValueError("prospective feasibility manifest mismatch")
    if len(value["case_membership"]) != 12 or len(value["work_items"]) != 24 or len({x["work_id"] for x in value["work_items"]}) != 24:
        raise ValueError("prospective feasibility membership mismatch")


def feasibility_authorization_payload(manifest: Mapping[str, Any] | None = None,
                                      generation: M20FeasibilityGeneration | None = None) -> dict[str, Any]:
    generation = _generation(generation)
    frozen = build_feasibility_manifest(generation) if manifest is None else dict(manifest)
    validate_feasibility_manifest(frozen, generation)
    return {"schema": M20_FEASIBILITY_AUTHORIZATION_SCHEMA, "protocol": frozen["protocol"],
            "manifest_digest": frozen["digest"], "namespace": frozen["namespace"],
            "work_ids": [item["work_id"] for item in frozen["work_items"]],
            "provider_hash": frozen["provider_hash"], "resource_ceiling_identity": frozen["resource_ceiling_identity"]}


def verify_feasibility_authorization(value: Mapping[str, Any] | None, manifest: Mapping[str, Any] | None = None,
                                     generation: M20FeasibilityGeneration | None = None) -> None:
    if not isinstance(value, Mapping) or dict(value) != feasibility_authorization_payload(manifest, generation):
        raise PermissionError("prospective feasibility synthetic authorization mismatch")


def feasibility_live_authorization_payload(manifest: Mapping[str, Any] | None = None,
                                           financial_policy: M20FeasibilityFinancialPolicy | None = None,
                                           owner_risk_policy: M20OwnerRiskAcceptedFinancialPolicy | None = None,
                                           generation: M20FeasibilityGeneration | None = None) -> dict[str, Any]:
    """Exact future artifact contract; this function does not issue an artifact."""
    generation = _generation(generation)
    frozen = build_feasibility_manifest(generation) if manifest is None else dict(manifest)
    validate_feasibility_manifest(frozen, generation)
    original_limit = len(frozen["work_items"]) * 8
    replacement_limit = original_limit
    payload = {"schema": (generation.owner_risk_authorization_schema if owner_risk_policy is not None else M20_FEASIBILITY_LIVE_AUTHORIZATION_SCHEMA), "authority": M20_FEASIBILITY_OWNER_AUTHORITY,
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
    if generation is M20_FEASIBILITY_GENERATION_V2:
        payload.update({"generation_id": generation.generation_id, "result_path": generation.result_path})
    if financial_policy is not None and owner_risk_policy is not None:
        raise ValueError("financial and owner-risk admission policies are mutually exclusive")
    if financial_policy is not None:
        payload["financial_policy"] = financial_policy.canonical()
    if owner_risk_policy is not None:
        # This is signed scope, not a live authorization artifact or a tokenizer policy.
        payload["owner_risk_policy"] = owner_risk_policy.canonical()
    return payload


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def load_feasibility_live_authorization(path: Path, trust_anchor: Path, manifest: Mapping[str, Any] | None = None,
                                        financial_policy: M20FeasibilityFinancialPolicy | None = None,
                                        owner_risk_policy: M20OwnerRiskAcceptedFinancialPolicy | None = None,
                                        generation: M20FeasibilityGeneration | None = None) -> dict[str, Any]:
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
    if (financial_policy is None) == (owner_risk_policy is None):
        raise PermissionError("exactly one admission policy is required for live authorization")
    expected = feasibility_live_authorization_payload(manifest, financial_policy, owner_risk_policy, generation)
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
    def __init__(self, manifest: Mapping[str, Any] | None = None,
                 generation: M20FeasibilityGeneration | None = None) -> None:
        self.generation = _generation(generation)
        self.frozen = build_feasibility_manifest(self.generation) if manifest is None else dict(manifest)
        validate_feasibility_manifest(self.frozen, self.generation)
        cases = real_cases(); ceiling = M20ResourceCeiling(M20_REAL_RESOURCE_CEILING_V2.identity, 16, 8, 8, 8)
        pairing = tuple(M20PairingMetadata(case.public.case_id, case.cluster_id, case.payload_digest,
                         case.environment_id, case.evaluator_id, ceiling.identity) for case in cases)
        model = M20Manifest("m20_suite_v1", "m20_environment_v1", "m20_evaluator_v1", cases,
                            self.generation.harness_generation_identity, pairing, ceiling,
                            execution_manifest_digest=self.frozen["digest"])
        self._diagnostic_store: M20EvaluatorDiagnosticStore | None = None
        def diagnostic(spec, case, state, answer, outcome):
            if self._diagnostic_store is not None:
                self._diagnostic_store.persist(diagnose_after_evaluator_handoff(spec.execution_id, case, state, answer, "m20_evaluator_v1", outcome))
        context = {"feasibility_protocol": M20_FEASIBILITY_PROTOCOL, "runtime_identity": self.frozen["runtime_identity"],
                   "diagnostic_identity": self.frozen["diagnostic_identity"]}
        if self.generation is M20_FEASIBILITY_GENERATION_V2:
            context["generation_id"] = self.generation.generation_id
        self.harness = M20Harness(model, M20ConditionRegistry(self.frozen["provider_hash"]), M20RealEnvironment(), M20RealEvaluator(),
            context,
            answer_termination_enabled=True, evaluator_handoff_hook=diagnostic)
        self._items = tuple(M20FeasibilityWorkItem(value["work_id"], M20ExecutionSpec("m20_suite_v1", value["case_id"], value["repetition"], M20Condition.MIND_FIXED,
            self.generation.namespace, self.frozen["digest"], self.frozen["provider_hash"], value["cluster_id"], value["payload_digest"],
            "m20_environment_v1", "m20_evaluator_v1", M20_REAL_RESOURCE_CEILING_V2.identity,
            frozen_pair_id=self._frozen_pair_id(value["case_id"], value["repetition"])) ) for value in self.frozen["work_items"])

    def work_items(self) -> tuple[M20FeasibilityWorkItem, ...]: return self._items
    def store(self, root: Path) -> M20EvidenceStore: return M20EvidenceStore(root, self.harness.manifest, self.generation.namespace)
    def diagnostic_store(self, root: Path) -> M20EvaluatorDiagnosticStore: return M20EvaluatorDiagnosticStore(root / "private_evaluator_diagnostics")

    def _frozen_pair_id(self, case_id: str, repetition: int) -> str:
        value: dict[str, Any] = {"protocol": M20_FEASIBILITY_PROTOCOL, "case": case_id, "repetition": repetition}
        if self.generation is M20_FEASIBILITY_GENERATION_V2:
            value["generation_id"] = self.generation.generation_id
        return canonical_hash(value)

    @staticmethod
    def _reparse_point(path: Path) -> bool:
        try:
            attributes = os.lstat(path).st_file_attributes
        except AttributeError:
            attributes = 0
        return path.is_symlink() or bool(attributes & 0x400)

    def _v2_destination(self, repository_root: Path) -> Path:
        """Derive, never accept, the v2 destination from a trusted repository root."""
        if not isinstance(repository_root, Path) or not repository_root.is_dir():
            raise PermissionError("a trusted repository root is required")
        relative = PurePosixPath(self.generation.result_path)
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise PermissionError("feasibility result path is not a safe relative path")
        root = repository_root.resolve(strict=True)
        candidate = root.joinpath(*relative.parts)
        current = root
        for part in relative.parts:
            current = current / part
            if current.exists() and self._reparse_point(current):
                raise PermissionError("reparse point is forbidden in feasibility destination")
        results_root = root / "evaluation" / "results"
        resolved = candidate.resolve(strict=False)
        if results_root.resolve(strict=False) not in (resolved, *resolved.parents):
            raise PermissionError("feasibility destination escapes repository results root")
        if resolved == (root / M20_FEASIBILITY_RESULT_PATH).resolve(strict=False):
            raise PermissionError("historical v1 feasibility root is not writable")
        return resolved

    def _admit_destination(self, repository_root: Path, authorization: Mapping[str, Any] | None = None) -> Path:
        """Fail closed before any v2 store, ledger, budget, or transport operation."""
        if self.generation is not M20_FEASIBILITY_GENERATION_V2:
            raise PermissionError("destination admission is only defined for generation v2")
        destination = self._v2_destination(repository_root)
        if not destination.exists():
            return destination
        if not destination.is_dir() or self._reparse_point(destination):
            raise PermissionError("feasibility destination is not a regular directory")
        entries = tuple(destination.iterdir())
        if not entries:
            return destination
        marker = destination / "manifest.json"
        expected = {"digest": self.harness.manifest.digest, "namespace": self.generation.namespace.value,
                    "harness": M20_HARNESS_ID}
        try:
            marker_value = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise PermissionError("nonempty v2 destination has no valid marker") from error
        if marker_value != expected:
            raise PermissionError("v2 destination marker drift")
        original_ids = {item.spec.execution_id for item in self._items}
        replacement_ids = {derive_first_replacement_spec(item.spec, item.spec.execution_id).execution_id for item in self._items}
        allowed_ids = original_ids | replacement_ids
        completed: list[Mapping[str, Any]] = []
        permitted = {"manifest.json", ".m20_execution_control", "private_evaluator_diagnostics"}
        for entry in entries:
            if self._reparse_point(entry):
                raise PermissionError("reparse point is forbidden in v2 destination")
            if entry.name in permitted:
                continue
            partial_name = entry.name.removesuffix(".partial.resolved.json").removesuffix(".partial.json")
            if entry.name.endswith((".partial.json", ".partial.resolved.json")):
                if not entry.is_file() or partial_name not in allowed_ids:
                    raise PermissionError("v2 destination contains an unknown partial artifact")
                try:
                    partial = json.loads(entry.read_text(encoding="utf-8"))
                    if partial.get("execution_id") != partial_name or partial.get("spec") != partial_name or not isinstance(partial.get("telemetry"), Mapping):
                        raise ValueError("partial identity")
                except (OSError, ValueError) as error:
                    raise PermissionError("v2 destination partial evidence is invalid") from error
                continue
            if not entry.is_file() or not entry.name.endswith(".json") or entry.stem not in allowed_ids:
                raise PermissionError("v2 destination contains an unknown artifact")
            try:
                value = json.loads(entry.read_text(encoding="utf-8")); digest = value.pop("digest", None)
                if digest != canonical_hash(value): raise ValueError("digest")
                M20EvidenceStore.validate_persisted(value)
            except Exception as error:
                raise PermissionError("v2 destination completed evidence is invalid") from error
            spec = value.get("spec", {})
            if (value.get("execution_id") != entry.stem or spec.get("namespace") != self.generation.namespace.value or
                    spec.get("manifest_digest") != self.frozen["digest"] or spec.get("condition") != M20Condition.MIND_FIXED.value or
                    spec.get("provider_hash") != self.frozen["provider_hash"]):
                raise PermissionError("v2 destination completed evidence binding mismatch")
            completed.append(value)
        try:
            M20EvidenceStore._validate_replacement_linkage(tuple(completed))
        except Exception as error:
            raise PermissionError("v2 destination replacement linkage is invalid") from error
        for directory_name in (".m20_execution_control", "private_evaluator_diagnostics"):
            child = destination / directory_name
            if child.exists() and (not child.is_dir() or self._reparse_point(child)):
                raise PermissionError("v2 destination control directory is invalid")
        control = destination / ".m20_execution_control"
        if control.exists() and any(not entry.is_file() or self._reparse_point(entry) or
                                    entry.name not in {"financial_ledger.json", "live_budget.json", "physical_dispatch.lock"}
                                    for entry in control.iterdir()):
            raise PermissionError("v2 destination contains an unknown control artifact")
        diagnostics = destination / "private_evaluator_diagnostics"
        completed_ids = {value.get("execution_id") for value in completed}
        if diagnostics.exists() and any(not entry.is_file() or self._reparse_point(entry) or
                                        not entry.name.endswith(".json") or entry.stem not in completed_ids
                                        for entry in diagnostics.iterdir()):
            raise PermissionError("v2 destination contains an unknown diagnostic artifact")
        if authorization is not None:
            digest = canonical_hash(dict(authorization))
            for name in ("financial_ledger.json", "live_budget.json", "physical_dispatch.lock"):
                path = control / name
                if not path.exists(): continue
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError) as error:
                    raise PermissionError("v2 control artifact is unreadable") from error
                if value.get("authorization_digest") != digest:
                    raise PermissionError("v2 control authorization binding mismatch")
        return destination

    def _live_root(self, root: Path | None, repository_root: Path | None,
                   authorization: Mapping[str, Any] | None = None) -> Path:
        if self.generation is M20_FEASIBILITY_GENERATION_V2:
            if root is not None:
                raise PermissionError("generation v2 forbids caller-selected result roots")
            if repository_root is None:
                raise PermissionError("generation v2 requires repository-root destination admission")
            return self._admit_destination(repository_root, authorization)
        if root is None:
            raise TypeError("result root is required")
        return root
    def run_fake(self, authorization: Mapping[str, Any] | None, transport: Transport, root: Path | None = None,
                 *, repository_root: Path | None = None) -> tuple[M20ExecutionRecord, ...]:
        verify_feasibility_authorization(authorization, self.frozen, self.generation)
        if not callable(transport): raise TypeError("fake transport is required")
        root = self._live_root(root, repository_root, authorization)
        store = self.store(root); self._diagnostic_store = self.diagnostic_store(root)
        try:
            return tuple(self._run(item, transport, store) for item in self._items)
        finally:
            self._diagnostic_store = None

    def run_live(self, authorization_artifact: Path, trust_anchor: Path, transport: Transport, root: Path | None = None,
                 *, operator_stop_path: Path | None = None, financial_policy: M20FeasibilityFinancialPolicy | None = None,
                 token_counter: Any | None = None, repository_root: Path | None = None) -> tuple[M20ExecutionRecord, ...]:
        """Future live path: exact artifact validation always precedes adapter creation."""
        if self.generation is M20_FEASIBILITY_GENERATION_V2:
            raise PermissionError("generation v2 accepts only the owner-risk authorization schema v3")
        authorization = load_feasibility_live_authorization(authorization_artifact, trust_anchor, self.frozen, financial_policy,
                                                            generation=self.generation)
        if not callable(transport):
            raise TypeError("transport is required")
        if operator_stop_path is None:
            raise PermissionError("operator stop path is required")
        if financial_policy is None or not callable(token_counter):
            raise PermissionError("provider-compatible financial token control is required")
        require_verified_production_tokenizer(financial_policy, token_counter)
        root = self._live_root(root, repository_root, authorization)
        control = M20FeasibilityLiveBudget(root, authorization, operator_stop_path)
        financial = M20FeasibilityFinancialLedger(root, authorization, financial_policy, token_counter, operator_stop_path)
        control.ensure_not_stopped()
        store = self.store(root); self._diagnostic_store = self.diagnostic_store(root)
        try:
            return tuple(self._run(item, transport, store, control, financial) for item in self._items)
        finally:
            self._diagnostic_store = None

    def run_owner_risk_accepted_live(self, authorization_artifact: Path, trust_anchor: Path, transport: Transport,
                                     root: Path | None = None, *, operator_stop_path: Path | None = None,
                                     owner_risk_policy: M20OwnerRiskAcceptedFinancialPolicy | None = None,
                                     repository_root: Path | None = None) -> tuple[M20ExecutionRecord, ...]:
        """Future owner-risk path; it is distinct from tokenizer-backed live admission.

        A valid artifact is still required. This method does not issue one and is
        exercised only with fake transport in offline tests.
        """
        authorization = load_feasibility_live_authorization(
            authorization_artifact, trust_anchor, self.frozen, owner_risk_policy=owner_risk_policy,
            generation=self.generation)
        if not callable(transport):
            raise TypeError("transport is required")
        if operator_stop_path is None or owner_risk_policy is None:
            raise PermissionError("owner-risk policy and operator stop path are required")
        root = self._live_root(root, repository_root, authorization)
        control = M20FeasibilityLiveBudget(root, authorization, operator_stop_path)
        financial = M20FeasibilityFinancialLedger(root, authorization, owner_risk_policy, None, operator_stop_path)
        control.ensure_not_stopped(); financial.ensure_replacement_allowed()
        store = self.store(root); self._diagnostic_store = self.diagnostic_store(root)
        try:
            records = []
            for item in self._items:
                # Recheck immediately before every scheduled original.  A
                # financial ambiguity is an interruption, never a result.
                control.ensure_not_stopped(); financial.ensure_dispatch_allowed()
                records.append(self._run(item, transport, store, control, financial))
            return tuple(records)
        finally:
            self._diagnostic_store = None

    def replacement_item(self, original: M20ExecutionRecord) -> M20FeasibilityWorkItem:
        known = next((item for item in self._items if item.spec.execution_id == original.execution_id), None)
        if known is None:
            raise PermissionError("replacement original is not an authorized feasibility work")
        return M20FeasibilityWorkItem( self.harness.replacement(original).execution_id,
            self.harness.replacement(original))

    def run_live_replacement(self, authorization_artifact: Path, trust_anchor: Path, original_work_id: str, transport: Transport, root: Path | None = None,
                             *, operator_stop_path: Path | None = None, financial_policy: M20FeasibilityFinancialPolicy | None = None,
                             token_counter: Any | None = None, interrupt_before_execution: bool = False,
                             repository_root: Path | None = None) -> M20ExecutionRecord:
        if self.generation is M20_FEASIBILITY_GENERATION_V2:
            raise PermissionError("generation v2 accepts only the owner-risk authorization schema v3")
        authorization = load_feasibility_live_authorization(authorization_artifact, trust_anchor, self.frozen, financial_policy,
                                                            generation=self.generation)
        if operator_stop_path is None:
            raise PermissionError("operator stop path is required")
        if financial_policy is None or not callable(token_counter):
            raise PermissionError("provider-compatible financial token control is required")
        require_verified_production_tokenizer(financial_policy, token_counter)
        root = self._live_root(root, repository_root, authorization)
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
        previous_validator = getattr(self.harness, "_pre_persist_validator", None)
        self.harness._pre_persist_validator = lambda record: financial.reconcile_telemetry(record.execution_id, record.telemetry.retries)
        try:
            financial.ensure_dispatch_allowed()
            return self.harness.run(replacement.spec, M20FixedAdapter(M20DeepSeekProposalAdapter(
                transport, answer_termination_enabled=True, admit_logical_operation=lambda: control.admit(True),
                financial_ledger=financial, execution_id=replacement.spec.execution_id, work_id=replacement.work_id)), store,
                                    interrupt_before_execution=interrupt_before_execution)
        finally:
            self.harness._pre_persist_validator = previous_validator
            self._diagnostic_store = None

    def run_owner_risk_accepted_replacement(self, authorization_artifact: Path, trust_anchor: Path,
                                             original_work_id: str, transport: Transport, root: Path | None = None, *,
                                             operator_stop_path: Path | None = None,
                                             owner_risk_policy: M20OwnerRiskAcceptedFinancialPolicy | None = None,
                                             interrupt_before_execution: bool = False,
                                             repository_root: Path | None = None) -> M20ExecutionRecord:
        authorization = load_feasibility_live_authorization(
            authorization_artifact, trust_anchor, self.frozen, owner_risk_policy=owner_risk_policy,
            generation=self.generation)
        if operator_stop_path is None or owner_risk_policy is None:
            raise PermissionError("owner-risk policy and operator stop path are required")
        root = self._live_root(root, repository_root, authorization)
        original_item = next((item for item in self._items if item.work_id == original_work_id), None)
        if original_item is None:
            raise PermissionError("replacement original is unknown")
        store = self.store(root); original = store.completed_record(original_item.spec); replacement = self.replacement_item(original)
        control = M20FeasibilityLiveBudget(root, authorization, operator_stop_path)
        financial = M20FeasibilityFinancialLedger(root, authorization, owner_risk_policy, None, operator_stop_path)
        control.ensure_not_stopped(); financial.ensure_replacement_allowed()
        self.harness._provenance_overrides.update({"work_id": replacement.work_id, "original_work_id": original_item.work_id,
            "replacement_work_id": replacement.work_id, "replacement_index": "1", "replacement_eligibility": original.outcome.value})
        self._diagnostic_store = self.diagnostic_store(root)
        previous_validator = getattr(self.harness, "_pre_persist_validator", None)
        self.harness._pre_persist_validator = lambda record: financial.reconcile_telemetry(record.execution_id, record.telemetry.retries)
        try:
            return self.harness.run(replacement.spec, M20FixedAdapter(M20DeepSeekProposalAdapter(
                transport, answer_termination_enabled=True, admit_logical_operation=lambda: control.admit(True),
                financial_ledger=financial, execution_id=replacement.spec.execution_id, work_id=replacement.work_id)), store,
                                    interrupt_before_execution=interrupt_before_execution)
        finally:
            self.harness._pre_persist_validator = previous_validator
            self._diagnostic_store = None

    def _run(self, item: M20FeasibilityWorkItem, transport: Transport, store: M20EvidenceStore,
             control: M20FeasibilityLiveBudget | None = None,
             financial: M20FeasibilityFinancialLedger | None = None) -> M20ExecutionRecord:
        if item not in self._items:
            raise PermissionError("unrecognized feasibility work")
        self.harness._provenance_overrides["work_id"] = item.work_id
        admission = None if control is None else control.admit
        previous = getattr(self.harness, "_pre_persist_validator", None)
        if financial is not None:
            self.harness._pre_persist_validator = lambda record: financial.reconcile_telemetry(record.execution_id, record.telemetry.retries)
        try:
            return self.harness.run(item.spec, M20FixedAdapter(M20DeepSeekProposalAdapter(
                transport, answer_termination_enabled=True, admit_logical_operation=admission,
                financial_ledger=financial, execution_id=(item.spec.execution_id if financial is not None else None),
                work_id=(item.work_id if financial is not None else None))), store)
        finally:
            self.harness._pre_persist_validator = previous


def descriptive_projection(records: tuple[Mapping[str, Any], ...], diagnostics: tuple[Any, ...]) -> dict[str, Any]:
    if len(records) != 24 or len({item["execution_id"] for item in records}) != 24:
        raise ValueError("feasibility evidence membership is incomplete")
    outcomes = {key: sum(item["outcome"] == key for item in records) for key in ("success", "failure_or_incorrect", "incomplete")}
    classifications = {key: sum(getattr(item, "classification", None) == key for item in diagnostics) for key in ("success", "answer_payload_failure", "prerequisite_failure", "combined_failure", "unknown_other")}
    return {"original_works": len(records), "outcomes": outcomes, "diagnostic_classifications": classifications,
            "unknown_rate": classifications["unknown_other"] / len(records),
            "provider_interactions": [item["telemetry"]["provider_interactions"] for item in records],
            "ceiling_exhaustion": sum(item["outcome"] == "incomplete" for item in records)}
