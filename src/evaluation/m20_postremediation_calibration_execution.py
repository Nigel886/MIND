"""Fail-closed v3 calibration execution infrastructure; no implicit transport."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from src.evaluation.m20_calibration_manifest import build_postremediation_manifest, validate_postremediation_manifest
from src.evaluation.m20_deepseek_execution import M20DeepSeekProposalAdapter, Transport
from src.evaluation.m20_harness import (M20AdaptiveAdapter, M20Condition, M20ConditionRegistry,
    M20EvidenceStore, M20ExecutionRecord, M20ExecutionSpec, M20FixedAdapter, M20Harness,
    M20Manifest, M20PairingMetadata, M20ResourceCeiling, M20Namespace, canonical_hash)
from src.evaluation.m20_real_case_source import M20RealEnvironment, M20RealEvaluator, real_cases
from src.evaluation.m20_real_execution_configuration import M20_REAL_RESOURCE_CEILING

M20_POSTREMEDIATION_AUTHORIZATION_SCHEMA = "m20_postremediation_calibration_authorization_v1"


def authorization_payload(manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Canonical payload which a future independent authority must issue.

    This function does not persist, sign, or authorize a live artifact.  It
    only makes the precise object that the verifier will accept testable.
    """
    frozen = dict(build_postremediation_manifest() if manifest is None else manifest)
    validate_postremediation_manifest(frozen)
    return {
        "schema": M20_POSTREMEDIATION_AUTHORIZATION_SCHEMA,
        "protocol": frozen["protocol"], "namespace": frozen["namespace"],
        "result_path": frozen["result_path"], "manifest_version": frozen["version"],
        "manifest_digest": frozen["digest"], "pair_work_binding_digest": frozen["manifest_digest"],
        "runtime_identity": frozen["runtime_generation"]["identity"],
        "ordering_rule": frozen["ordering_rule"], "ordering_identity": frozen["ordering_identity"],
        "pair_ids": [pair["pair_id"] for pair in frozen["pairs"]],
        "work_ids": [item["work_id"] for item in frozen["work_items"]],
        "case_source_digest": frozen["case_source_digest"], "provider_hash": frozen["provider_hash"],
        "resource_ceiling_identity": frozen["resource_ceiling_identity"],
        "statistical_protocol": frozen["statistical_protocol"],
    }


def verify_authorization(value: Mapping[str, Any] | None, manifest: Mapping[str, Any] | None = None) -> None:
    """Reject every missing, stale, partial, extra, or altered authorization."""
    if value is None or not isinstance(value, Mapping):
        raise PermissionError("post-remediation calibration authorization is required")
    expected = authorization_payload(manifest)
    if dict(value) != expected:
        raise PermissionError("post-remediation calibration authorization mismatch")


@dataclass(frozen=True)
class M20PostRemediationWorkItem:
    work_id: str
    pair_id: str
    spec: M20ExecutionSpec


class M20PostRemediationCalibrationRunner:
    """The sole v3 bridge: authorization -> exact work membership -> harness.

    There is intentionally no default transport and no method which creates a
    live transport.  A future execution owner must first supply an independently
    issued exact artifact and an explicitly selected transport.
    """
    def __init__(self, manifest: Mapping[str, Any] | None = None) -> None:
        self.frozen = dict(build_postremediation_manifest() if manifest is None else manifest)
        validate_postremediation_manifest(self.frozen)
        if self.frozen["resource_ceiling_identity"] != M20_REAL_RESOURCE_CEILING.identity:
            raise ValueError("post-remediation resource ceiling mismatch")
        cases = real_cases()
        self._cases = {case.public.case_id: case for case in cases}
        ceiling = M20ResourceCeiling(M20_REAL_RESOURCE_CEILING.identity, 8, 4, 4, 8)
        pairing = tuple(M20PairingMetadata(case.public.case_id, case.cluster_id, case.payload_digest,
                         case.environment_id, case.evaluator_id, ceiling.identity) for case in cases)
        manifest_model = M20Manifest("m20_suite_v1", "m20_environment_v1", "m20_evaluator_v1", cases,
                                     "m20_real_case_source_v1", pairing, ceiling,
                                     execution_manifest_digest=self.frozen["digest"])
        overrides = {"postremediation_protocol": self.frozen["protocol"],
                     "runtime_identity": self.frozen["runtime_generation"]["identity"],
                     "ordering_identity": self.frozen["ordering_identity"],
                     "pair_work_binding_digest": self.frozen["manifest_digest"]}
        self.harness = M20Harness(manifest_model, M20ConditionRegistry(self.frozen["provider_hash"]),
                                  M20RealEnvironment(), M20RealEvaluator(), overrides)
        pairs = {pair["pair_id"]: pair for pair in self.frozen["pairs"]}
        result: list[M20PostRemediationWorkItem] = []
        for item in self.frozen["work_items"]:
            pair = pairs.get(item["pair_id"])
            if pair is None or item["namespace"] != self.frozen["namespace"]:
                raise ValueError("post-remediation work/pair binding mismatch")
            condition = M20Condition(item["condition"])
            spec = M20ExecutionSpec("m20_suite_v1", pair["case_id"], pair["repetition"], condition,
                M20Namespace.CALIBRATION_POSTREMEDIATION, self.frozen["digest"], self.frozen["provider_hash"],
                pair["cluster_id"], pair["payload_digest"], "m20_environment_v1", "m20_evaluator_v1",
                self.frozen["resource_ceiling_identity"], frozen_pair_id=pair["pair_id"])
            result.append(M20PostRemediationWorkItem(item["work_id"], pair["pair_id"], spec))
        if len(result) != 120 or len({item.work_id for item in result}) != 120:
            raise ValueError("post-remediation work membership mismatch")
        self._items = tuple(result)

    def work_items(self) -> tuple[M20PostRemediationWorkItem, ...]:
        return self._items

    def _store(self, root: Path) -> M20EvidenceStore:
        return M20EvidenceStore(root, self.harness.manifest, M20Namespace.CALIBRATION_POSTREMEDIATION)

    def run(self, authorization: Mapping[str, Any] | None, transport: Transport, root: Path) -> tuple[M20ExecutionRecord, ...]:
        verify_authorization(authorization, self.frozen)
        if not callable(transport):
            raise TypeError("explicit transport is required")
        store = self._store(root)
        records: list[M20ExecutionRecord] = []
        for item in self._items:
            records.append(self._run_item(item, transport, store))
        self._assert_terminal(store, records)
        return tuple(records)

    def run_prefix_for_testing(self, authorization: Mapping[str, Any] | None, transport: Transport,
                               root: Path, count: int) -> tuple[M20ExecutionRecord, ...]:
        """Test-only interrupted prefix; production membership has no subset API."""
        verify_authorization(authorization, self.frozen)
        if not isinstance(count, int) or count < 0 or count > len(self._items):
            raise ValueError("invalid deterministic test prefix")
        store = self._store(root); records: list[M20ExecutionRecord] = []
        for item in self._items[:count]:
            records.append(self._run_item(item, transport, store))
        return tuple(records)

    def _run_item(self, item: M20PostRemediationWorkItem, transport: Transport,
                  store: M20EvidenceStore) -> M20ExecutionRecord:
        # Provenance is part of the canonical persisted record.  The base
        # harness owns every lifecycle/resource transition; this bridge only
        # supplies the frozen v3 work identity immediately before that path.
        self.harness._provenance_overrides["work_id"] = item.work_id
        provider = M20DeepSeekProposalAdapter(transport)
        adapter = M20AdaptiveAdapter(provider) if item.spec.condition is M20Condition.MIND_ADAPTIVE else M20FixedAdapter(provider)
        return self.harness.run(item.spec, adapter, store)

    def _assert_terminal(self, store: M20EvidenceStore, records: list[M20ExecutionRecord]) -> None:
        expected = tuple(item.spec for item in self._items)
        report = store.reconcile(expected)
        if report["completed"] != 120 or report["missing"] or report["incomplete"]:
            raise ValueError("post-remediation calibration lifecycle is not terminal")
        pairs: dict[str, list[Mapping[str, Any]]] = {}
        for record in store.records():
            pairs.setdefault(record["pair_id"], []).append(record)
        if len(pairs) != 60 or any(len(value) != 2 for value in pairs.values()):
            raise ValueError("post-remediation pair lifecycle mismatch")
        for value in pairs.values():
            M20EvidenceStore.reconstruct_pair(tuple(value))
