"""Frozen, fake-auditable identity for the post-#291 termination diagnostic.

This module deliberately has no live transport or execution entry point.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.evaluation.m20_deepseek_execution import M20DeepSeekProposalAdapter, Transport
from src.evaluation.m20_harness import (
    M20_ANSWER_READINESS_VERSION, M20AdaptiveAdapter, M20Condition, M20ConditionRegistry,
    M20EvidenceStore, M20ExecutionSpec, M20FixedAdapter, M20Harness, M20Manifest,
    M20Namespace, M20PairingMetadata, M20ResourceCeiling, canonical_hash, m20_answer_ready,
)
from src.evaluation.m20_real_case_source import (
    M20_REAL_CASE_SOURCE_VERSION, M20RealEnvironment, M20RealEvaluator,
    real_case_definitions, real_case_source_digest,
)
from src.evaluation.m20_real_execution_configuration import (
    M20_REAL_PROVIDER_CONFIGURATION, M20_REAL_RESOURCE_CEILING_V2,
)


M20_ANSWER_TERMINATION_DIAGNOSTIC_PROTOCOL = "m20_answer_termination_diagnostic_v1"
M20_ANSWER_TERMINATION_DIAGNOSTIC_PATH = Path("evaluation/results/m20_answer_termination_diagnostic_v1")
M20_ANSWER_TERMINATION_RUNTIME_IDENTITY = canonical_hash({
    "harness": "m20_evaluation_harness_v1",
    "answer_readiness": M20_ANSWER_READINESS_VERSION,
    "answer_termination_policy": "m20_answer_termination_policy_v1",
    "adaptive": "m20_m19_adaptive_adapter_v1",
    "fixed": "m20_fixed_cycle_adapter_v1",
})
M20_ANSWER_TERMINATION_AUTHORIZATION_SCHEMA = "m20_answer_termination_diagnostic_authorization_v1"
M20_ANSWER_TERMINATION_CASE_A = "m20.real.answer_ready_early_stop.01"
M20_ANSWER_TERMINATION_CASE_B = "m20.real.multi_step_stateful.01"


@dataclass(frozen=True)
class M20AnswerTerminationWorkItem:
    work_id: str
    spec: M20ExecutionSpec


def _definitions() -> tuple[Any, Any]:
    values = {item.case_id: item for item in real_case_definitions()}
    try:
        return values[M20_ANSWER_TERMINATION_CASE_A], values[M20_ANSWER_TERMINATION_CASE_B]
    except KeyError as error:
        raise ValueError("frozen answer-termination cases are absent") from error


def _core_protocol() -> dict[str, Any]:
    case_a, case_b = _definitions()
    return {
        "protocol": M20_ANSWER_TERMINATION_DIAGNOSTIC_PROTOCOL,
        "namespace": M20Namespace.DIAGNOSTIC_ANSWER_TERMINATION.value,
        "result_path": M20_ANSWER_TERMINATION_DIAGNOSTIC_PATH.as_posix(),
        "case_source": M20_REAL_CASE_SOURCE_VERSION,
        "case_source_digest": real_case_source_digest(),
        "cases": [
            {"case_id": case_a.case_id, "cohort": case_a.cohort, "payload_digest": case_a.payload_digest,
             "witness_action_count": 0, "initial_answer_ready": True},
            {"case_id": case_b.case_id, "cohort": case_b.cohort, "payload_digest": case_b.payload_digest,
             "witness_action_count": 2, "initial_answer_ready": False},
        ],
        "conditions": [M20Condition.MIND_ADAPTIVE.value, M20Condition.MIND_FIXED.value],
        "repetitions": 1,
        "answer_readiness_policy": M20_ANSWER_READINESS_VERSION,
        "runtime_identity": M20_ANSWER_TERMINATION_RUNTIME_IDENTITY,
        "provider_hash": M20_REAL_PROVIDER_CONFIGURATION.identity_hash,
        "resource_ceiling_version": M20_REAL_RESOURCE_CEILING_V2.version,
        "resource_ceiling_digest": M20_REAL_RESOURCE_CEILING_V2.identity_hash,
        "resource_ceiling_identity": M20_REAL_RESOURCE_CEILING_V2.identity,
    }


def build_answer_termination_protocol() -> dict[str, Any]:
    core = _core_protocol()
    digest = canonical_hash(core)
    runner = M20AnswerTerminationDiagnosticRunner({**core, "digest": digest}, _validated=True)
    return {**core, "digest": digest, "work_ids": [item.work_id for item in runner.work_items()]}


def validate_answer_termination_protocol(value: Mapping[str, Any]) -> None:
    candidate = dict(value)
    work_ids = candidate.pop("work_ids", None)
    digest = candidate.pop("digest", None)
    core = _core_protocol()
    if candidate != core or digest != canonical_hash(core):
        raise ValueError("answer-termination diagnostic protocol mismatch")
    runner = M20AnswerTerminationDiagnosticRunner({**core, "digest": digest}, _validated=True)
    if work_ids != [item.work_id for item in runner.work_items()]:
        raise ValueError("answer-termination diagnostic work identity mismatch")


def answer_termination_authorization_payload(protocol: Mapping[str, Any] | None = None) -> dict[str, Any]:
    frozen = build_answer_termination_protocol() if protocol is None else dict(protocol)
    validate_answer_termination_protocol(frozen)
    return {
        "schema": M20_ANSWER_TERMINATION_AUTHORIZATION_SCHEMA,
        "protocol": frozen["protocol"], "protocol_digest": frozen["digest"],
        "namespace": frozen["namespace"], "result_path": frozen["result_path"],
        "case_ids": [item["case_id"] for item in frozen["cases"]],
        "case_payload_digests": [item["payload_digest"] for item in frozen["cases"]],
        "work_ids": list(frozen["work_ids"]),
        "answer_readiness_policy": frozen["answer_readiness_policy"],
        "runtime_identity": frozen["runtime_identity"], "provider_hash": frozen["provider_hash"],
        "resource_ceiling_version": frozen["resource_ceiling_version"],
        "resource_ceiling_digest": frozen["resource_ceiling_digest"],
        "decision": "M20 ANSWER-TERMINATION DIAGNOSTIC AUTHORIZED",
    }


def verify_answer_termination_authorization(value: Mapping[str, Any] | None,
                                            protocol: Mapping[str, Any] | None = None) -> None:
    if not isinstance(value, Mapping) or dict(value) != answer_termination_authorization_payload(protocol):
        raise PermissionError("answer-termination diagnostic authorization mismatch")


class M20AnswerTerminationDiagnosticRunner:
    """Four-item fake-only runner; future live execution requires a separate issue."""
    def __init__(self, protocol: Mapping[str, Any] | None = None, _validated: bool = False) -> None:
        if protocol is None:
            protocol = build_answer_termination_protocol()
        self.protocol = dict(protocol)
        if not _validated:
            validate_answer_termination_protocol(self.protocol)
        case_a, case_b = (item.to_case() for item in _definitions())
        ceiling = M20ResourceCeiling(M20_REAL_RESOURCE_CEILING_V2.identity, 16, 8, 8, 8)
        pairing = tuple(M20PairingMetadata(case.public.case_id, case.cluster_id, case.payload_digest,
                                            case.environment_id, case.evaluator_id, ceiling.identity)
                        for case in (case_a, case_b))
        self.manifest = M20Manifest(self.protocol["protocol"], "m20_environment_v1", "m20_evaluator_v1",
                                    (case_a, case_b), M20_REAL_CASE_SOURCE_VERSION, pairing, ceiling,
                                    execution_manifest_digest=self.protocol["digest"])
        self.harness = M20Harness(self.manifest, M20ConditionRegistry(M20_REAL_PROVIDER_CONFIGURATION.identity_hash),
                                  M20RealEnvironment(), M20RealEvaluator(),
                                  {"diagnostic_protocol": self.protocol["protocol"],
                                   "answer_readiness_policy": M20_ANSWER_READINESS_VERSION,
                                   "runtime_identity": M20_ANSWER_TERMINATION_RUNTIME_IDENTITY},
                                  answer_termination_enabled=True)

    def work_items(self) -> tuple[M20AnswerTerminationWorkItem, ...]:
        result = []
        for case in self.manifest.cases:
            pair_id = canonical_hash({"protocol": self.protocol["digest"], "case": case.public.case_id,
                                      "conditions": self.protocol["conditions"]})
            for condition in (M20Condition.MIND_ADAPTIVE, M20Condition.MIND_FIXED):
                spec = M20ExecutionSpec(self.protocol["protocol"], case.public.case_id, 1, condition,
                    M20Namespace.DIAGNOSTIC_ANSWER_TERMINATION, self.protocol["digest"],
                    M20_REAL_PROVIDER_CONFIGURATION.identity_hash, case.cluster_id, case.payload_digest,
                    case.environment_id, case.evaluator_id, M20_REAL_RESOURCE_CEILING_V2.identity,
                    frozen_pair_id=pair_id)
                result.append(M20AnswerTerminationWorkItem(spec.execution_id, spec))
        if len(result) != 4 or len({item.work_id for item in result}) != 4:
            raise ValueError("answer-termination diagnostic work enumeration mismatch")
        return tuple(result)

    def run_fake(self, authorization: Mapping[str, Any] | None, item: M20AnswerTerminationWorkItem,
                 transport: Transport, root: Path) -> Any:
        verify_answer_termination_authorization(authorization, self.protocol)
        expected = {candidate.work_id: candidate for candidate in self.work_items()}
        if item.work_id not in expected or expected[item.work_id] != item or not callable(transport):
            raise PermissionError("answer-termination diagnostic work admission mismatch")
        store = M20EvidenceStore(root, self.manifest, M20Namespace.DIAGNOSTIC_ANSWER_TERMINATION)
        provider = M20DeepSeekProposalAdapter(transport, answer_termination_enabled=True)
        adapter = M20AdaptiveAdapter(provider) if item.spec.condition is M20Condition.MIND_ADAPTIVE else M20FixedAdapter(provider)
        return self.harness.run(item.spec, adapter, store)

    @staticmethod
    def credential_ready() -> bool:
        return isinstance(os.environ.get("DEEPSEEK_API_KEY"), str) and bool(os.environ["DEEPSEEK_API_KEY"].strip())


__all__ = [
    "M20_ANSWER_TERMINATION_AUTHORIZATION_SCHEMA", "M20_ANSWER_TERMINATION_CASE_A",
    "M20_ANSWER_TERMINATION_CASE_B", "M20_ANSWER_TERMINATION_DIAGNOSTIC_PATH",
    "M20_ANSWER_TERMINATION_DIAGNOSTIC_PROTOCOL", "M20_ANSWER_TERMINATION_RUNTIME_IDENTITY",
    "M20AnswerTerminationDiagnosticRunner", "M20AnswerTerminationWorkItem",
    "answer_termination_authorization_payload", "build_answer_termination_protocol",
    "validate_answer_termination_protocol", "verify_answer_termination_authorization",
]
