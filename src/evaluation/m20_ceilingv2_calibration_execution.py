"""Fail-closed manifest-v4 / ceiling-v2 calibration bridge; no live transport."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.evaluation.m20_calibration_manifest import build_ceilingv2_manifest, validate_ceilingv2_manifest
from src.evaluation.m20_deepseek_execution import M20DeepSeekProposalAdapter, Transport
from src.evaluation.m20_harness import (
    M20AdaptiveAdapter, M20Condition, M20ConditionRegistry, M20EvidenceStore,
    M20ExecutionRecord, M20ExecutionSpec, M20FixedAdapter, M20Harness,
    M20Manifest, M20PairingMetadata, M20ResourceCeiling, M20Namespace,
)
from src.evaluation.m20_real_case_source import M20RealEnvironment, M20RealEvaluator, real_cases
from src.evaluation.m20_real_execution_configuration import (
    M20_REAL_RESOURCE_CEILING_V2, validate_m20_real_resource_ceiling_v2,
)

M20_CEILINGV2_AUTHORIZATION_SCHEMA = "m20_ceilingv2_calibration_authorization_v1"


def ceilingv2_authorization_payload(manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Exact testable v4 authorization shape; issuing an artifact is external."""
    frozen = dict(build_ceilingv2_manifest() if manifest is None else manifest)
    validate_ceilingv2_manifest(frozen)
    return {
        "schema": M20_CEILINGV2_AUTHORIZATION_SCHEMA,
        "protocol": frozen["protocol"], "namespace": frozen["namespace"],
        "result_path": frozen["result_path"], "manifest_version": frozen["version"],
        "manifest_digest": frozen["digest"], "pair_work_binding_digest": frozen["manifest_digest"],
        "runtime_identity": frozen["runtime_generation"]["identity"],
        "ordering_rule": frozen["ordering_rule"], "ordering_identity": frozen["ordering_identity"],
        "pair_ids": [pair["pair_id"] for pair in frozen["pairs"]],
        "work_ids": [item["work_id"] for item in frozen["work_items"]],
        "case_source_digest": frozen["case_source_digest"], "provider_hash": frozen["provider_hash"],
        "resource_ceiling_version": M20_REAL_RESOURCE_CEILING_V2.version,
        "resource_ceiling_digest": M20_REAL_RESOURCE_CEILING_V2.identity_hash,
        "resource_ceiling_identity": frozen["resource_ceiling_identity"],
        "statistical_protocol": frozen["statistical_protocol"],
    }


def verify_ceilingv2_authorization(value: Mapping[str, Any] | None,
                                   manifest: Mapping[str, Any] | None = None) -> None:
    """Reject absent, stale, partial, altered, or expanded v4 authority before transport."""
    if value is None or not isinstance(value, Mapping):
        raise PermissionError("ceiling-v2 calibration authorization is required")
    try:
        expected = ceilingv2_authorization_payload(manifest)
    except ValueError as error:
        raise PermissionError("ceiling-v2 calibration authorization manifest mismatch") from error
    if dict(value) != expected:
        raise PermissionError("ceiling-v2 calibration authorization mismatch")


@dataclass(frozen=True)
class M20CeilingV2WorkItem:
    work_id: str
    pair_id: str
    spec: M20ExecutionSpec


class M20CeilingV2CalibrationRunner:
    """Exact v4 work admission -> shared harness; never creates a live transport."""
    def __init__(self, manifest: Mapping[str, Any] | None = None) -> None:
        self.frozen = dict(build_ceilingv2_manifest() if manifest is None else manifest)
        validate_ceilingv2_manifest(self.frozen)
        validate_m20_real_resource_ceiling_v2(M20_REAL_RESOURCE_CEILING_V2)
        if self.frozen["resource_ceiling_identity"] != M20_REAL_RESOURCE_CEILING_V2.identity:
            raise ValueError("ceiling-v2 resource ceiling mismatch")
        cases = real_cases()
        ceiling = M20ResourceCeiling(
            M20_REAL_RESOURCE_CEILING_V2.identity,
            M20_REAL_RESOURCE_CEILING_V2.reasoning_steps,
            M20_REAL_RESOURCE_CEILING_V2.tool_attempts,
            M20_REAL_RESOURCE_CEILING_V2.logical_provider_interactions,
            M20_REAL_RESOURCE_CEILING_V2.decision_cycles,
        )
        pairing = tuple(M20PairingMetadata(case.public.case_id, case.cluster_id, case.payload_digest,
                         case.environment_id, case.evaluator_id, ceiling.identity) for case in cases)
        manifest_model = M20Manifest("m20_suite_v1", "m20_environment_v1", "m20_evaluator_v1", cases,
                                     "m20_real_case_source_v1", pairing, ceiling,
                                     execution_manifest_digest=self.frozen["digest"])
        overrides = {"ceilingv2_protocol": self.frozen["protocol"],
                     "runtime_identity": self.frozen["runtime_generation"]["identity"],
                     "ordering_identity": self.frozen["ordering_identity"],
                     "pair_work_binding_digest": self.frozen["manifest_digest"]}
        self.harness = M20Harness(manifest_model, M20ConditionRegistry(self.frozen["provider_hash"]),
                                  M20RealEnvironment(), M20RealEvaluator(), overrides)
        pairs = {pair["pair_id"]: pair for pair in self.frozen["pairs"]}
        result: list[M20CeilingV2WorkItem] = []
        for item in self.frozen["work_items"]:
            pair = pairs.get(item["pair_id"])
            if pair is None or item["namespace"] != self.frozen["namespace"]:
                raise ValueError("ceiling-v2 work/pair binding mismatch")
            condition = M20Condition(item["condition"])
            spec = M20ExecutionSpec("m20_suite_v1", pair["case_id"], pair["repetition"], condition,
                M20Namespace.CALIBRATION_CEILINGV2, self.frozen["digest"], self.frozen["provider_hash"],
                pair["cluster_id"], pair["payload_digest"], "m20_environment_v1", "m20_evaluator_v1",
                self.frozen["resource_ceiling_identity"], frozen_pair_id=pair["pair_id"])
            result.append(M20CeilingV2WorkItem(item["work_id"], pair["pair_id"], spec))
        if len(result) != 120 or len({item.work_id for item in result}) != 120:
            raise ValueError("ceiling-v2 work membership mismatch")
        self._items = tuple(result)

    def work_items(self) -> tuple[M20CeilingV2WorkItem, ...]:
        return self._items

    def _store(self, root: Path) -> M20EvidenceStore:
        return M20EvidenceStore(root, self.harness.manifest, M20Namespace.CALIBRATION_CEILINGV2)

    def run(self, authorization: Mapping[str, Any] | None, transport: Transport,
            root: Path) -> tuple[M20ExecutionRecord, ...]:
        verify_ceilingv2_authorization(authorization, self.frozen)
        if not callable(transport):
            raise TypeError("explicit transport is required")
        store = self._store(root)
        records = [self._run_item(item, transport, store) for item in self._items]
        self._assert_terminal(store, records)
        return tuple(records)

    def run_prefix_for_testing(self, authorization: Mapping[str, Any] | None, transport: Transport,
                               root: Path, count: int) -> tuple[M20ExecutionRecord, ...]:
        verify_ceilingv2_authorization(authorization, self.frozen)
        if not isinstance(count, int) or count < 0 or count > len(self._items):
            raise ValueError("invalid deterministic test prefix")
        if not callable(transport):
            raise TypeError("explicit transport is required")
        store = self._store(root)
        return tuple(self._run_item(item, transport, store) for item in self._items[:count])

    def _run_item(self, item: M20CeilingV2WorkItem, transport: Transport,
                  store: M20EvidenceStore) -> M20ExecutionRecord:
        self.harness._provenance_overrides["work_id"] = item.work_id
        provider = M20DeepSeekProposalAdapter(transport)
        adapter = (M20AdaptiveAdapter(provider) if item.spec.condition is M20Condition.MIND_ADAPTIVE
                   else M20FixedAdapter(provider))
        return self.harness.run(item.spec, adapter, store)

    def _assert_terminal(self, store: M20EvidenceStore, records: list[M20ExecutionRecord]) -> None:
        report = store.reconcile(tuple(item.spec for item in self._items))
        if report["completed"] != 120 or report["missing"] or report["incomplete"]:
            raise ValueError("ceiling-v2 calibration lifecycle is not terminal")
        pairs: dict[str, list[Mapping[str, Any]]] = {}
        for record in store.records():
            pairs.setdefault(record["pair_id"], []).append(record)
        if len(pairs) != 60 or any(len(value) != 2 for value in pairs.values()):
            raise ValueError("ceiling-v2 pair lifecycle mismatch")
        for records_for_pair in pairs.values():
            M20EvidenceStore.reconstruct_pair(tuple(records_for_pair))
