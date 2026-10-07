"""Fail-closed fake-only bridge for the frozen answer-termination v5 generation."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from src.evaluation.m20_calibration_manifest import build_answerterm_manifest, validate_answerterm_manifest
from src.evaluation.m20_deepseek_execution import M20DeepSeekProposalAdapter, Transport
from src.evaluation.m20_harness import (
    M20AdaptiveAdapter, M20Condition, M20ConditionRegistry, M20EvidenceStore,
    M20ExecutionRecord, M20ExecutionSpec, M20FixedAdapter, M20Harness, M20Manifest,
    M20Namespace, M20PairingMetadata, M20ResourceCeiling,
)
from src.evaluation.m20_real_case_source import M20RealEnvironment, M20RealEvaluator, real_cases
from src.evaluation.m20_real_execution_configuration import M20_REAL_RESOURCE_CEILING_V2


M20_ANSWERTERM_AUTHORIZATION_SCHEMA = "m20_answerterm_calibration_authorization_v1"
M20_ANSWERTERM_LIVE_AUTHORIZATION_SCHEMA = "m20_answerterm_calibration_live_authorization_v1"


def answerterm_authorization_payload(manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Exact testable v5 authority; creating a real artifact remains external."""
    frozen = dict(build_answerterm_manifest() if manifest is None else manifest)
    validate_answerterm_manifest(frozen)
    return {
        "schema": M20_ANSWERTERM_AUTHORIZATION_SCHEMA,
        "protocol": frozen["protocol"], "namespace": frozen["namespace"], "result_path": frozen["result_path"],
        "manifest_version": frozen["version"], "manifest_digest": frozen["digest"],
        "pair_work_binding_digest": frozen["manifest_digest"],
        "runtime_identity": frozen["runtime_generation"]["identity"],
        "answer_readiness_identity": frozen["answer_readiness_identity"],
        "ordering_rule": frozen["ordering_rule"], "ordering_identity": frozen["ordering_identity"],
        "pair_ids": [item["pair_id"] for item in frozen["pairs"]],
        "work_ids": [item["work_id"] for item in frozen["work_items"]],
        "case_source_digest": frozen["case_source_digest"], "provider_hash": frozen["provider_hash"],
        "resource_ceiling_version": frozen["resource_ceiling_version"],
        "resource_ceiling_digest": frozen["resource_ceiling_digest"],
        "statistical_protocol": frozen["statistical_protocol"],
    }


def verify_answerterm_authorization(value: Mapping[str, Any] | None,
                                    manifest: Mapping[str, Any] | None = None) -> None:
    if not isinstance(value, Mapping) or dict(value) != answerterm_authorization_payload(manifest):
        raise PermissionError("answer-termination calibration authorization mismatch")


def answerterm_live_authorization_payload(manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Exact future live artifact shape; issuance remains an audit decision."""
    payload = answerterm_authorization_payload(manifest)
    return {**payload, "schema": M20_ANSWERTERM_LIVE_AUTHORIZATION_SCHEMA, "authority": "live"}


def load_answerterm_live_authorization(path: Path, manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PermissionError("live v5 authorization artifact is absent or invalid") from error
    expected = answerterm_live_authorization_payload(manifest)
    if not isinstance(value, Mapping) or dict(value) != expected:
        raise PermissionError("live v5 authorization artifact mismatch")
    return dict(value)


@dataclass(frozen=True)
class M20AnswerTermWorkItem:
    work_id: str
    pair_id: str
    spec: M20ExecutionSpec


class M20AnswerTerminationCalibrationRunner:
    """Exact v5 admission into the shared harness; it never exposes live transport."""
    def __init__(self, manifest: Mapping[str, Any] | None = None) -> None:
        self.frozen = dict(build_answerterm_manifest() if manifest is None else manifest)
        validate_answerterm_manifest(self.frozen)
        cases = real_cases()
        ceiling = M20ResourceCeiling(M20_REAL_RESOURCE_CEILING_V2.identity, 16, 8, 8, 8)
        pairing = tuple(M20PairingMetadata(case.public.case_id, case.cluster_id, case.payload_digest,
                         case.environment_id, case.evaluator_id, ceiling.identity) for case in cases)
        model = M20Manifest("m20_suite_v1", "m20_environment_v1", "m20_evaluator_v1", cases,
                            "m20_real_case_source_v1", pairing, ceiling,
                            execution_manifest_digest=self.frozen["digest"])
        overrides = {"answerterm_protocol": self.frozen["protocol"],
                     "runtime_identity": self.frozen["runtime_generation"]["identity"],
                     "answer_readiness_identity": self.frozen["answer_readiness_identity"],
                     "ordering_identity": self.frozen["ordering_identity"],
                     "pair_work_binding_digest": self.frozen["manifest_digest"]}
        self.harness = M20Harness(model, M20ConditionRegistry(self.frozen["provider_hash"]),
                                  M20RealEnvironment(), M20RealEvaluator(), overrides,
                                  answer_termination_enabled=True)
        pairs = {value["pair_id"]: value for value in self.frozen["pairs"]}
        items = []
        for value in self.frozen["work_items"]:
            pair = pairs.get(value["pair_id"])
            if pair is None or value["namespace"] != self.frozen["namespace"]:
                raise ValueError("v5 work/pair binding mismatch")
            spec = M20ExecutionSpec("m20_suite_v1", pair["case_id"], pair["repetition"],
                M20Condition(value["condition"]), M20Namespace.CALIBRATION_ANSWERTERM,
                self.frozen["digest"], self.frozen["provider_hash"], pair["cluster_id"], pair["payload_digest"],
                "m20_environment_v1", "m20_evaluator_v1", M20_REAL_RESOURCE_CEILING_V2.identity,
                frozen_pair_id=pair["pair_id"])
            items.append(M20AnswerTermWorkItem(value["work_id"], pair["pair_id"], spec))
        if len(items) != 120 or len({item.work_id for item in items}) != 120:
            raise ValueError("v5 work membership mismatch")
        self._items = tuple(items)

    def work_items(self) -> tuple[M20AnswerTermWorkItem, ...]:
        return self._items

    def store(self, root: Path) -> M20EvidenceStore:
        return M20EvidenceStore(root, self.harness.manifest, M20Namespace.CALIBRATION_ANSWERTERM)

    def run_fake_prefix(self, authorization: Mapping[str, Any] | None, transport: Transport,
                        root: Path, count: int, *, interrupt_before_execution: bool = False) -> tuple[M20ExecutionRecord, ...]:
        verify_answerterm_authorization(authorization, self.frozen)
        if not callable(transport) or not isinstance(count, int) or count < 0 or count > 120:
            raise PermissionError("fake v5 execution admission mismatch")
        store = self.store(root)
        result = []
        for index, item in enumerate(self._items[:count]):
            result.append(self._run(item, transport, store,
                                    interrupt_before_execution=interrupt_before_execution and index == 0))
        return tuple(result)

    def run_live(self, authorization_artifact: Path, transport: Transport, root: Path) -> tuple[M20ExecutionRecord, ...]:
        """Artifact-gated production path; no caller is authorized by this method."""
        load_answerterm_live_authorization(authorization_artifact, self.frozen)
        store = self.store(root)
        return tuple(self._run(item, transport, store) for item in self._items)

    def replacement_item(self, original: M20ExecutionRecord) -> M20AnswerTermWorkItem:
        """Derive the sole permitted replacement from immutable persisted original evidence."""
        known = next((item for item in self._items if item.spec.execution_id == original.execution_id), None)
        if known is None:
            raise PermissionError("replacement original is not an authorized v5 work")
        replacement = self.harness.replacement(original)
        return M20AnswerTermWorkItem(replacement.execution_id, known.pair_id, replacement)

    def run_live_replacement(self, authorization_artifact: Path, original_work_id: str,
                             transport: Transport, root: Path,
                             *, interrupt_before_execution: bool = False) -> M20ExecutionRecord:
        load_answerterm_live_authorization(authorization_artifact, self.frozen)
        original = next((item for item in self._items if item.work_id == original_work_id), None)
        if original is None:
            raise PermissionError("replacement original is unknown")
        store = self.store(root)
        persisted = store.completed_record(original.spec)
        item = self.replacement_item(persisted)
        self.harness._provenance_overrides.update({"work_id": item.work_id,
            "original_work_id": original.work_id, "replacement_work_id": item.work_id,
            "replacement_index": "1", "replacement_eligibility": persisted.outcome.value})
        provider = M20DeepSeekProposalAdapter(transport, answer_termination_enabled=True)
        adapter = M20AdaptiveAdapter(provider) if item.spec.condition is M20Condition.MIND_ADAPTIVE else M20FixedAdapter(provider)
        return self.harness.run(item.spec, adapter, store, interrupt_before_execution=interrupt_before_execution)

    def _run(self, item: M20AnswerTermWorkItem, transport: Transport, store: M20EvidenceStore,
             *, interrupt_before_execution: bool = False) -> M20ExecutionRecord:
        expected = {candidate.work_id: candidate for candidate in self._items}
        if expected.get(item.work_id) != item:
            raise PermissionError("unrecognized v5 work item")
        self.harness._provenance_overrides["work_id"] = item.work_id
        provider = M20DeepSeekProposalAdapter(transport, answer_termination_enabled=True)
        adapter = M20AdaptiveAdapter(provider) if item.spec.condition is M20Condition.MIND_ADAPTIVE else M20FixedAdapter(provider)
        return self.harness.run(item.spec, adapter, store, interrupt_before_execution=interrupt_before_execution)
