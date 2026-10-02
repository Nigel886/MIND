"""Isolated, fake-only M20 real-provider contract diagnostic infrastructure.

This module defines the prospective diagnostic identity and persistence boundary.
It deliberately exposes no live-provider execution entry point.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from src.evaluation.m20_deepseek_execution import (
    M20DeepSeekProposalAdapter, M20ResponseRejection, Transport, live_deepseek_transport,
)
from src.evaluation.m20_harness import (
    M20AdaptiveAdapter, M20Condition, M20ConditionRegistry, M20EvidenceStore,
    M20ExecutionSpec, M20FixedAdapter, M20Harness, M20Manifest,
    M20Namespace, M20PairingMetadata, M20ResourceCeiling, canonical_hash,
)
from src.evaluation.m20_real_case_source import (
    M20_REAL_CASE_SOURCE_VERSION, M20RealEnvironment, M20RealEvaluator,
    real_case_definitions, real_case_source_digest,
)
from src.evaluation.m20_real_execution_configuration import (
    M20_REAL_PROVIDER_CONFIGURATION, M20_REAL_RESOURCE_CEILING,
)


M20_REAL_PROVIDER_DIAGNOSTIC_PROTOCOL = "m20_real_provider_diagnostic_v1"
M20_REAL_PROVIDER_DIAGNOSTIC_PATH = Path("evaluation/results/m20_real_provider_diagnostic_v1")
M20_POST_ENVELOPE_DIAGNOSTIC_PROTOCOL = "m20_real_provider_diagnostic_v2"
M20_POST_ENVELOPE_DIAGNOSTIC_PATH = Path("evaluation/results/m20_real_provider_diagnostic_v2")
M20_POST_ENVELOPE_DIAGNOSTIC_V3_PROTOCOL = "m20_real_provider_diagnostic_v3"
M20_POST_ENVELOPE_DIAGNOSTIC_V3_PATH = Path("evaluation/results/m20_real_provider_diagnostic_v3")
M20_POST_ENVELOPE_DIAGNOSTIC_V4_PROTOCOL = "m20_real_provider_diagnostic_v4"
M20_POST_ENVELOPE_DIAGNOSTIC_V4_PATH = Path("evaluation/results/m20_real_provider_diagnostic_v4")
M20_POST_ENVELOPE_DIAGNOSTIC_V5_PROTOCOL = "m20_real_provider_diagnostic_v5"
M20_POST_ENVELOPE_DIAGNOSTIC_V5_PATH = Path("evaluation/results/m20_real_provider_diagnostic_v5")
M20_RESPONSE_TELEMETRY_SCHEMA = "m20_deepseek_response_shape_telemetry_v1"
M20_DIAGNOSTIC_CASE_ID = "m20.real.multi_step_stateful.01"
M20_DIAGNOSTIC_COHORT = "multi_step_stateful"
M20_DIAGNOSTIC_PAYLOAD_DIGEST = "b977a2170893e1c1cfc7d7571e275df3f47d95259b29415e2d1bdea1202069be"
M20_LIVE_DIAGNOSTIC_AUTHORIZATION_VERSION = "m20_live_diagnostic_authorization_v1"


@dataclass(frozen=True)
class M20DiagnosticGeneration:
    protocol: str
    result_path: Path
    authorization_version: str
    namespace: M20Namespace


M20_DIAGNOSTIC_GENERATION_V1 = M20DiagnosticGeneration(
    M20_REAL_PROVIDER_DIAGNOSTIC_PROTOCOL, M20_REAL_PROVIDER_DIAGNOSTIC_PATH,
    M20_LIVE_DIAGNOSTIC_AUTHORIZATION_VERSION, M20Namespace.DIAGNOSTIC,
)
M20_DIAGNOSTIC_GENERATION_V2 = M20DiagnosticGeneration(
    M20_POST_ENVELOPE_DIAGNOSTIC_PROTOCOL, M20_POST_ENVELOPE_DIAGNOSTIC_PATH,
    "m20_post_envelope_live_diagnostic_authorization_v1", M20Namespace.DIAGNOSTIC,
)
M20_DIAGNOSTIC_GENERATION_V3 = M20DiagnosticGeneration(
    M20_POST_ENVELOPE_DIAGNOSTIC_V3_PROTOCOL, M20_POST_ENVELOPE_DIAGNOSTIC_V3_PATH,
    "m20_post_envelope_v3_live_diagnostic_authorization_v1", M20Namespace.DIAGNOSTIC_V3,
)
M20_DIAGNOSTIC_GENERATION_V4 = M20DiagnosticGeneration(
    M20_POST_ENVELOPE_DIAGNOSTIC_V4_PROTOCOL, M20_POST_ENVELOPE_DIAGNOSTIC_V4_PATH,
    "m20_post_envelope_v4_live_diagnostic_authorization_v1", M20Namespace.DIAGNOSTIC_V4,
)
M20_DIAGNOSTIC_GENERATION_V5 = M20DiagnosticGeneration(
    M20_POST_ENVELOPE_DIAGNOSTIC_V5_PROTOCOL, M20_POST_ENVELOPE_DIAGNOSTIC_V5_PATH,
    "m20_post_envelope_v5_live_diagnostic_authorization_v1", M20Namespace.DIAGNOSTIC_V5,
)


def _expected_protocol(generation: M20DiagnosticGeneration = M20_DIAGNOSTIC_GENERATION_V1) -> dict[str, Any]:
    return {
        "protocol": generation.protocol,
        "case_source": M20_REAL_CASE_SOURCE_VERSION,
        "case_source_digest": real_case_source_digest(),
        "case_id": M20_DIAGNOSTIC_CASE_ID,
        "cohort": M20_DIAGNOSTIC_COHORT,
        "payload_digest": M20_DIAGNOSTIC_PAYLOAD_DIGEST,
        "conditions": [M20Condition.MIND_ADAPTIVE.value, M20Condition.MIND_FIXED.value],
        "repetition": 1,
        "provider_hash": M20_REAL_PROVIDER_CONFIGURATION.identity_hash,
        "resource_ceiling_identity": M20_REAL_RESOURCE_CEILING.identity,
        "telemetry_schema": M20_RESPONSE_TELEMETRY_SCHEMA,
        "namespace": generation.namespace.value,
        "result_path": generation.result_path.as_posix(),
    }


def build_diagnostic_protocol() -> dict[str, Any]:
    return _build_protocol(M20_DIAGNOSTIC_GENERATION_V1)


def build_post_envelope_diagnostic_protocol() -> dict[str, Any]:
    return _build_protocol(M20_DIAGNOSTIC_GENERATION_V2)


def build_post_envelope_v3_diagnostic_protocol() -> dict[str, Any]:
    return _build_protocol(M20_DIAGNOSTIC_GENERATION_V3)


def build_post_envelope_v4_diagnostic_protocol() -> dict[str, Any]:
    return _build_protocol(M20_DIAGNOSTIC_GENERATION_V4)


def build_post_envelope_v5_diagnostic_protocol() -> dict[str, Any]:
    return _build_protocol(M20_DIAGNOSTIC_GENERATION_V5)


def _build_protocol(generation: M20DiagnosticGeneration) -> dict[str, Any]:
    value = _expected_protocol(generation)
    return {**value, "digest": canonical_hash(value)}


def validate_diagnostic_protocol(value: Mapping[str, Any],
                                 generation: M20DiagnosticGeneration = M20_DIAGNOSTIC_GENERATION_V1) -> None:
    candidate = dict(value)
    digest = candidate.pop("digest", None)
    expected = _expected_protocol(generation)
    if digest != canonical_hash(expected) or candidate != expected:
        raise ValueError("diagnostic protocol identity mismatch")
    selected = real_case_definitions()[0]
    if (selected.case_id, selected.cohort, selected.payload_digest) != (
        M20_DIAGNOSTIC_CASE_ID, M20_DIAGNOSTIC_COHORT, M20_DIAGNOSTIC_PAYLOAD_DIGEST,
    ):
        raise ValueError("canonical diagnostic representative mismatch")


def _authorization_payload(generation: M20DiagnosticGeneration = M20_DIAGNOSTIC_GENERATION_V1) -> dict[str, Any]:
    protocol = _build_protocol(generation)
    return {"version": generation.authorization_version,
            "protocol_digest": protocol["digest"], "provider_hash": protocol["provider_hash"],
            "resource_ceiling_identity": protocol["resource_ceiling_identity"],
            "telemetry_schema": protocol["telemetry_schema"], "namespace": protocol["namespace"],
            "work_ids": [item.work_id for item in M20RealProviderDiagnosticRunner(generation=generation).work_items()],
            "decision": "REAL-PROVIDER CONTRACT DIAGNOSTIC AUTHORIZED"}


def expected_live_authorization_artifact(
        generation: M20DiagnosticGeneration = M20_DIAGNOSTIC_GENERATION_V1) -> dict[str, Any]:
    payload = _authorization_payload(generation)
    return {**payload, "identity": canonical_hash(payload)}


def load_live_authorization_artifact(
        path: Path, generation: M20DiagnosticGeneration = M20_DIAGNOSTIC_GENERATION_V1) -> dict[str, Any]:
    if not path.is_file():
        raise PermissionError("live diagnostic authorization artifact is absent")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PermissionError("live diagnostic authorization artifact is invalid") from error
    expected = expected_live_authorization_artifact(generation)
    if value != expected:
        raise PermissionError("live diagnostic authorization identity mismatch")
    return value


@dataclass(frozen=True)
class M20DiagnosticWorkItem:
    protocol_digest: str
    spec: M20ExecutionSpec

    @property
    def work_id(self) -> str:
        return self.spec.execution_id


@dataclass(frozen=True)
class M20FakeDiagnosticTransport:
    """Explicit test-only transport wrapper; real execution has no API here."""

    responder: Callable[[Mapping[str, Any], int], Mapping[str, Any]]

    def __call__(self, body: Mapping[str, Any], timeout_seconds: int) -> Mapping[str, Any]:
        return self.responder(body, timeout_seconds)


@dataclass(frozen=True)
class M20LiveDiagnosticTransport:
    """Typed live boundary; only constructed after execution-time credential admission."""

    responder: Transport
    credential_ready: bool

    @classmethod
    def from_environment(cls) -> "M20LiveDiagnosticTransport":
        # Credential material is checked only here and never stored in the object.
        if not isinstance(os.environ.get("DEEPSEEK_API_KEY"), str) or not os.environ["DEEPSEEK_API_KEY"].strip():
            raise PermissionError("live diagnostic credential is not ready")
        return cls(live_deepseek_transport, True)

    def __call__(self, body: Mapping[str, Any], timeout_seconds: int) -> Mapping[str, Any]:
        return self.responder(body, timeout_seconds)


class M20DiagnosticEvidenceStore(M20EvidenceStore):
    """Append-only isolated store; it rejects every non-diagnostic namespace."""

    def __init__(self, root: Path, manifest: M20Manifest, protocol_digest: str,
                 namespace: M20Namespace) -> None:
        if manifest.execution_manifest_digest != protocol_digest:
            raise ValueError("diagnostic store protocol binding mismatch")
        super().__init__(root, manifest, namespace)


class M20RealProviderDiagnosticRunner:
    """Two-work-item diagnostic contract, deliberately restricted to fake transports."""

    def __init__(self, protocol: Mapping[str, Any] | None = None,
                 generation: M20DiagnosticGeneration = M20_DIAGNOSTIC_GENERATION_V1) -> None:
        if generation not in (M20_DIAGNOSTIC_GENERATION_V1, M20_DIAGNOSTIC_GENERATION_V2,
                              M20_DIAGNOSTIC_GENERATION_V3, M20_DIAGNOSTIC_GENERATION_V4,
                              M20_DIAGNOSTIC_GENERATION_V5):
            raise ValueError("unsupported diagnostic generation")
        self.generation = generation
        self.protocol = dict(_build_protocol(generation) if protocol is None else protocol)
        validate_diagnostic_protocol(self.protocol, generation)
        definition = real_case_definitions()[0]
        case = definition.to_case()
        ceiling = M20ResourceCeiling(M20_REAL_RESOURCE_CEILING.identity, 8, 4, 4, 8)
        pairing = (M20PairingMetadata(case.public.case_id, case.cluster_id, case.payload_digest,
                                      case.environment_id, case.evaluator_id, ceiling.identity),)
        self.manifest = M20Manifest(self.generation.protocol,
                                    "m20_environment_v1", "m20_evaluator_v1", (case,),
                                    M20_REAL_CASE_SOURCE_VERSION, pairing, ceiling,
                                    execution_manifest_digest=self.protocol["digest"])
        self.harness = M20Harness(
            self.manifest, M20ConditionRegistry(M20_REAL_PROVIDER_CONFIGURATION.identity_hash),
            M20RealEnvironment(), M20RealEvaluator(),
            {"diagnostic_protocol": self.generation.protocol,
             "response_telemetry_schema": M20_RESPONSE_TELEMETRY_SCHEMA},
        )

    def work_items(self) -> tuple[M20DiagnosticWorkItem, ...]:
        case = self.manifest.cases[0]
        pair_id = canonical_hash({"protocol": self.protocol["digest"], "case": case.public.case_id,
                                  "repetition": 1, "conditions": self.protocol["conditions"]})
        items = tuple(M20DiagnosticWorkItem(
            self.protocol["digest"],
            M20ExecutionSpec(self.generation.protocol, case.public.case_id, 1, condition,
                             self.generation.namespace, self.protocol["digest"],
                             M20_REAL_PROVIDER_CONFIGURATION.identity_hash, case.cluster_id,
                             case.payload_digest, case.environment_id, case.evaluator_id,
                             M20_REAL_RESOURCE_CEILING.identity, frozen_pair_id=pair_id),
        ) for condition in (M20Condition.MIND_ADAPTIVE, M20Condition.MIND_FIXED))
        if (len(items) != 2 or len({item.work_id for item in items}) != 2 or
                {item.spec.condition for item in items} != {M20Condition.MIND_ADAPTIVE, M20Condition.MIND_FIXED}):
            raise ValueError("diagnostic work enumeration mismatch")
        for item in items:
            self.harness.preflight(item.spec)
        return items

    def store(self, root: Path) -> M20DiagnosticEvidenceStore:
        return M20DiagnosticEvidenceStore(root, self.manifest, self.protocol["digest"], self.generation.namespace)

    def run_fake(self, item: M20DiagnosticWorkItem, transport: M20FakeDiagnosticTransport,
                 store: M20DiagnosticEvidenceStore, interrupt_before_execution: bool = False) -> Any:
        if not isinstance(transport, M20FakeDiagnosticTransport):
            raise PermissionError("real diagnostic execution is not authorized")
        if not isinstance(store, M20DiagnosticEvidenceStore) or store.manifest.digest != self.manifest.digest:
            raise ValueError("diagnostic store identity mismatch")
        return self._run(item, transport, store, interrupt_before_execution)

    def run_live(self, item: M20DiagnosticWorkItem, transport: M20LiveDiagnosticTransport,
                 store: M20DiagnosticEvidenceStore, authorization_artifact: Path) -> Any:
        """Future-only, artifact-gated live path; #256 creates no authorization artifact."""
        if not isinstance(transport, M20LiveDiagnosticTransport):
            raise PermissionError("unsupported arbitrary live transport")
        if not transport.credential_ready:
            raise PermissionError("live diagnostic credential is not ready")
        if not isinstance(store, M20DiagnosticEvidenceStore) or store.manifest.digest != self.manifest.digest:
            raise ValueError("diagnostic store identity mismatch")
        load_live_authorization_artifact(authorization_artifact, self.generation)
        return self._run(item, transport, store, False)

    def _run(self, item: M20DiagnosticWorkItem, transport: Transport,
             store: M20DiagnosticEvidenceStore, interrupt_before_execution: bool) -> Any:
        expected = {candidate.work_id: candidate for candidate in self.work_items()}
        if item.work_id not in expected or expected[item.work_id] != item:
            raise ValueError("caller-added or altered diagnostic work is rejected")
        provider = M20DeepSeekProposalAdapter(transport)
        adapter = (M20AdaptiveAdapter(provider) if item.spec.condition is M20Condition.MIND_ADAPTIVE
                   else M20FixedAdapter(provider))
        return self.harness.run(item.spec, adapter, store, interrupt_before_execution)

    @staticmethod
    def namespace_accounting(store: M20DiagnosticEvidenceStore) -> dict[str, int]:
        if store.namespace not in (M20Namespace.DIAGNOSTIC, M20Namespace.DIAGNOSTIC_V3,
                                   M20Namespace.DIAGNOSTIC_V4, M20Namespace.DIAGNOSTIC_V5):
            raise ValueError("diagnostic accounting requires diagnostic namespace")
        return {"diagnostic": len(store.records()), "pilot": 0, "calibration": 0, "formal": 0}


__all__ = [
    "M20DiagnosticEvidenceStore", "M20DiagnosticGeneration", "M20DiagnosticWorkItem", "M20FakeDiagnosticTransport",
    "M20_DIAGNOSTIC_GENERATION_V1", "M20_DIAGNOSTIC_GENERATION_V2", "M20_DIAGNOSTIC_GENERATION_V3", "M20_DIAGNOSTIC_GENERATION_V4", "M20_DIAGNOSTIC_GENERATION_V5",
    "M20LiveDiagnosticTransport", "M20_LIVE_DIAGNOSTIC_AUTHORIZATION_VERSION",
    "M20_POST_ENVELOPE_DIAGNOSTIC_PATH", "M20_POST_ENVELOPE_DIAGNOSTIC_PROTOCOL",
    "M20_POST_ENVELOPE_DIAGNOSTIC_V3_PATH", "M20_POST_ENVELOPE_DIAGNOSTIC_V3_PROTOCOL",
    "M20_POST_ENVELOPE_DIAGNOSTIC_V4_PATH", "M20_POST_ENVELOPE_DIAGNOSTIC_V4_PROTOCOL",
    "M20_POST_ENVELOPE_DIAGNOSTIC_V5_PATH", "M20_POST_ENVELOPE_DIAGNOSTIC_V5_PROTOCOL",
    "M20_REAL_PROVIDER_DIAGNOSTIC_PATH", "M20_REAL_PROVIDER_DIAGNOSTIC_PROTOCOL",
    "M20_RESPONSE_TELEMETRY_SCHEMA", "M20RealProviderDiagnosticRunner",
    "M20ResponseRejection", "build_diagnostic_protocol", "build_post_envelope_diagnostic_protocol",
    "build_post_envelope_v3_diagnostic_protocol", "build_post_envelope_v4_diagnostic_protocol", "build_post_envelope_v5_diagnostic_protocol", "expected_live_authorization_artifact",
    "load_live_authorization_artifact", "validate_diagnostic_protocol",
]
