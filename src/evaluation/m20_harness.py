"""Deterministic, provider-free M20 evaluation harness infrastructure.

This module owns case validation, environment/evaluator admission, evidence,
and namespace protections.  Adapters may propose public actions only; they
cannot construct outcomes, telemetry, or completed records.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping, Protocol

from src.core.meta_control_policy import MetaControlPolicy
from src.core.resource_accounting import ResourceAllocation, ResourceDimension, ResourceState


M20_HARNESS_ID = "m20_evaluation_harness_v1"
M20_RECORD_SCHEMA = "m20_execution_record_v1"
M20_PROVENANCE_SCHEMA = "m20_execution_provenance_v1"
M20_MANIFEST_SCHEMA = "m20_suite_manifest_v1"
M20_FIXED_SCHEDULE_ID = "m20_fixed_cycle_schedule_v1"
M20_METRIC_VERSION = "m20_resource_metrics_v1"
M20_PROTOCOL_ID = "m20_statistical_protocol_v1"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


class M20Condition(str, Enum):
    MIND_ADAPTIVE = "m20_mind_adaptive_v1"
    MIND_FIXED = "m20_mind_fixed_v1"
    DIRECT = "m20_direct_v1"
    REACT = "m20_react_v1"
    PLAN = "m20_plan_v1"


class M20Namespace(str, Enum):
    FAKE = "m20_fake_v1"
    PILOT = "m20_pilot_v1"
    CALIBRATION = "m20_calibration_v1"
    FORMAL = "m20_formal_v1"


class M20Outcome(str, Enum):
    SUCCESS = "success"
    FAILURE_OR_INCORRECT = "failure_or_incorrect"
    INCOMPLETE = "incomplete"
    INVALID_ANSWER = "invalid_answer"
    INVALID_INTERACTION = "invalid_interaction"
    PROVIDER_FAILURE = "provider_failure"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"


class M20ProposalKind(str, Enum):
    ACT = "act"
    OBSERVE = "observe"
    ANSWER = "answer"


class M20IntegrityError(RuntimeError):
    """A contract breach, never an ordinary task outcome."""


@dataclass(frozen=True)
class M20ProviderConfiguration:
    provider: str
    endpoint_identity: str
    model: str
    temperature: float
    top_p: float
    output_token_ceiling: int
    response_format: str
    timeout_seconds: int
    retry_ceiling: int
    reasoning_mode: str

    def __post_init__(self) -> None:
        if any(not isinstance(getattr(self, name), str) or not getattr(self, name) for name in ("provider", "endpoint_identity", "model", "response_format", "reasoning_mode")):
            raise ValueError("provider identity fields must be non-empty")
        if self.output_token_ceiling < 1 or self.timeout_seconds < 1 or self.retry_ceiling < 0:
            raise ValueError("provider ceilings are invalid")

    @property
    def identity_hash(self) -> str:
        return canonical_hash(asdict(self))


@dataclass(frozen=True)
class M20PublicCase:
    case_id: str
    cohort: str
    task_text: str
    initial_state: Mapping[str, Any]
    actions: Mapping[str, Mapping[str, Any]]

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value for value in (self.case_id, self.cohort, self.task_text)):
            raise ValueError("public case identity is invalid")
        if not isinstance(self.initial_state, Mapping) or not isinstance(self.actions, Mapping) or not self.actions:
            raise ValueError("public case state/actions are invalid")
        if any(not isinstance(key, str) or not key or not isinstance(value, Mapping) for key, value in self.actions.items()):
            raise ValueError("public action contract is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"case_id": self.case_id, "cohort": self.cohort, "task_text": self.task_text,
                "initial_state": dict(self.initial_state), "actions": {key: dict(value) for key, value in self.actions.items()}}


@dataclass(frozen=True)
class M20PrivateCase:
    target: Any
    reference_witness: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.reference_witness, tuple) or not self.reference_witness:
            raise ValueError("private reference witness is required")


@dataclass(frozen=True)
class M20Case:
    public: M20PublicCase
    private: M20PrivateCase
    environment_id: str = "m20_environment_v1"
    evaluator_id: str = "m20_evaluator_v1"
    generation_identity: str = "m20_generation_v1"

    @property
    def payload_digest(self) -> str:
        return canonical_hash(self.public.to_dict())


@dataclass(frozen=True)
class M20Manifest:
    suite_id: str
    environment_id: str
    evaluator_id: str
    cases: tuple[M20Case, ...]
    generation_identity: str
    schema_version: str = M20_MANIFEST_SCHEMA

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value for value in (self.suite_id, self.environment_id, self.evaluator_id, self.generation_identity, self.schema_version)):
            raise ValueError("manifest identity is invalid")
        if not isinstance(self.cases, tuple) or not self.cases:
            raise ValueError("manifest requires cases")
        ids = [case.public.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate case id")
        for case in self.cases:
            if case.environment_id != self.environment_id or case.evaluator_id != self.evaluator_id:
                raise ValueError("case environment/evaluator mismatch")

    @property
    def digest(self) -> str:
        return canonical_hash({"suite_id": self.suite_id, "environment_id": self.environment_id,
                               "evaluator_id": self.evaluator_id, "generation_identity": self.generation_identity,
                               "schema_version": self.schema_version,
                               "cases": [{"case_id": item.public.case_id, "cohort": item.public.cohort,
                                          "payload_digest": item.payload_digest} for item in self.cases]})

    def case(self, case_id: str) -> M20Case:
        for item in self.cases:
            if item.public.case_id == case_id:
                return item
        raise ValueError("case is absent from manifest")


@dataclass(frozen=True)
class M20Proposal:
    kind: M20ProposalKind
    action_id: str | None = None
    payload: Any = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, M20ProposalKind):
            raise TypeError("proposal kind is invalid")
        if self.kind is M20ProposalKind.ANSWER:
            if self.action_id is not None:
                raise ValueError("answer has no action id")
        elif not isinstance(self.action_id, str) or not self.action_id:
            raise ValueError("action/observation requires public action id")


@dataclass(frozen=True)
class M20EnvironmentResult:
    state: Mapping[str, Any]
    feedback: str
    recoverable: bool = False
    terminal: bool = False
    infrastructure_failure: bool = False


class M20Environment(Protocol):
    environment_id: str
    def initial_public_state(self, case: M20PublicCase) -> Mapping[str, Any]: ...
    def apply(self, case: M20PublicCase, state: Mapping[str, Any], proposal: M20Proposal) -> M20EnvironmentResult: ...


class M20Evaluator(Protocol):
    evaluator_id: str
    def evaluate(self, case: M20Case, state: Mapping[str, Any], answer: Any) -> M20Outcome: ...


class M20ProposalProvider(Protocol):
    def propose(self, public_case: M20PublicCase, public_state: Mapping[str, Any]) -> M20Proposal: ...


@dataclass(frozen=True)
class M20ConditionBinding:
    condition: M20Condition
    adapter_id: str
    provider_hash: str
    resource_contract_id: str = M20_METRIC_VERSION


class M20ConditionRegistry:
    """Closed production condition registry; free-form condition names are rejected."""

    def __init__(self, provider_hash: str) -> None:
        if not isinstance(provider_hash, str) or len(provider_hash) != 64:
            raise ValueError("provider hash must be SHA-256")
        self._bindings = {
            M20Condition.MIND_ADAPTIVE: M20ConditionBinding(M20Condition.MIND_ADAPTIVE, "m20_m19_adaptive_adapter_v1", provider_hash),
            M20Condition.MIND_FIXED: M20ConditionBinding(M20Condition.MIND_FIXED, "m20_fixed_cycle_adapter_v1", provider_hash),
        }

    def binding(self, condition: M20Condition) -> M20ConditionBinding:
        if not isinstance(condition, M20Condition) or condition not in self._bindings:
            raise ValueError("condition is not frozen for M20 primary execution")
        return self._bindings[condition]


class M20AdaptiveAdapter:
    """Public-only adapter whose control identity is the delivered M19 policy."""

    condition = M20Condition.MIND_ADAPTIVE
    policy = MetaControlPolicy
    adapter_id = "m20_m19_adaptive_adapter_v1"

    def __init__(self, provider: M20ProposalProvider) -> None:
        if not hasattr(provider, "propose"):
            raise TypeError("proposal provider is required")
        self._provider = provider

    def propose(self, public_case: M20PublicCase, public_state: Mapping[str, Any]) -> M20Proposal:
        return self._provider.propose(public_case, public_state)


class M20FixedAdapter:
    """Exact #223 fixed controller: one reason, one commit, fixed recovery."""

    condition = M20Condition.MIND_FIXED
    adapter_id = "m20_fixed_cycle_adapter_v1"
    schedule_id = M20_FIXED_SCHEDULE_ID
    reasoning_transitions_per_state = 1
    commit_slots_per_state = 1
    proposal_attempts_per_slot = 1
    replans_per_recoverable_feedback = 1

    def __init__(self, provider: M20ProposalProvider) -> None:
        if not hasattr(provider, "propose"):
            raise TypeError("proposal provider is required")
        self._provider = provider

    def schedule(self, recoverable_feedback: bool = False) -> tuple[str, ...]:
        return (("replan",) if recoverable_feedback else ()) + ("continue_reasoning", "commit")

    def propose(self, public_case: M20PublicCase, public_state: Mapping[str, Any]) -> M20Proposal:
        return self._provider.propose(public_case, public_state)


@dataclass(frozen=True)
class M20ExecutionSpec:
    suite_id: str
    case_id: str
    repetition: int
    condition: M20Condition
    namespace: M20Namespace
    manifest_digest: str
    provider_hash: str
    replacement_of: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.condition, M20Condition) or not isinstance(self.namespace, M20Namespace):
            raise TypeError("execution condition or namespace invalid")
        if self.repetition < 1:
            raise ValueError("repetition must be positive")
        if any(not isinstance(value, str) or not value for value in (self.suite_id, self.case_id, self.manifest_digest, self.provider_hash)):
            raise ValueError("execution identity is invalid")
        if self.replacement_of is not None and (not isinstance(self.replacement_of, str) or not self.replacement_of):
            raise ValueError("replacement identity is invalid")

    @property
    def execution_id(self) -> str:
        return canonical_hash({"suite": self.suite_id, "case": self.case_id, "repetition": self.repetition,
                               "condition": self.condition.value, "namespace": self.namespace.value,
                               "manifest": self.manifest_digest, "provider": self.provider_hash,
                               "replacement_of": self.replacement_of, "schema": M20_RECORD_SCHEMA,
                               "harness": M20_HARNESS_ID})

    @property
    def pair_id(self) -> str:
        return canonical_hash({"suite": self.suite_id, "case": self.case_id, "repetition": self.repetition,
                               "manifest": self.manifest_digest})


@dataclass(frozen=True)
class M20ResourceTelemetry:
    reasoning_steps: int = 0
    tool_attempts: int = 0
    provider_interactions: int = 0
    decision_cycles: int = 0
    provider_transport_attempts: int = 0
    token_status: str = "TOKEN_USAGE_UNAVAILABLE"
    cost_status: str = "COST_NOT_COMPUTABLE"
    latency_status: str = "LATENCY_NOT_RELIABLE"

    def __post_init__(self) -> None:
        if any(not isinstance(getattr(self, key), int) or getattr(self, key) < 0 for key in
               ("reasoning_steps", "tool_attempts", "provider_interactions", "decision_cycles", "provider_transport_attempts")):
            raise ValueError("resource counts must be non-negative ints")


@dataclass(frozen=True)
class M20ExecutionRecord:
    execution_id: str
    pair_id: str
    spec: M20ExecutionSpec
    outcome: M20Outcome
    telemetry: M20ResourceTelemetry
    environment_id: str
    evaluator_id: str
    adapter_id: str
    provenance: Mapping[str, str]
    replacement_reason: str | None = None
    schema: str = M20_RECORD_SCHEMA

    def canonical(self) -> dict[str, Any]:
        return {"execution_id": self.execution_id, "pair_id": self.pair_id,
                "spec": {"suite_id": self.spec.suite_id, "case_id": self.spec.case_id,
                         "repetition": self.spec.repetition, "condition": self.spec.condition.value,
                         "namespace": self.spec.namespace.value, "manifest_digest": self.spec.manifest_digest,
                         "provider_hash": self.spec.provider_hash, "replacement_of": self.spec.replacement_of},
                "outcome": self.outcome.value, "telemetry": asdict(self.telemetry),
                "environment_id": self.environment_id, "evaluator_id": self.evaluator_id,
                "adapter_id": self.adapter_id, "provenance": dict(self.provenance),
                "replacement_reason": self.replacement_reason, "schema": self.schema}

    @property
    def digest(self) -> str:
        return canonical_hash(self.canonical())


class M20EvidenceStore:
    """Append-only, atomic completed evidence with resume reconciliation."""

    def __init__(self, root: Path, manifest: M20Manifest, namespace: M20Namespace) -> None:
        if namespace is M20Namespace.FORMAL:
            raise PermissionError("formal namespace is closed under #222")
        self.root, self.manifest, self.namespace = root, manifest, namespace
        root.mkdir(parents=True, exist_ok=True)
        marker = root / "manifest.json"
        expected = {"digest": manifest.digest, "namespace": namespace.value, "harness": M20_HARNESS_ID}
        if marker.exists():
            if json.loads(marker.read_text(encoding="utf-8")) != expected:
                raise M20IntegrityError("evidence-store configuration drift")
        else:
            self._atomic(marker, expected)

    def _atomic(self, path: Path, value: Mapping[str, Any]) -> None:
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=self.root, suffix=".tmp") as handle:
            handle.write(canonical_json(value) + "\n")
            temporary = Path(handle.name)
        temporary.replace(path)

    def persist(self, record: M20ExecutionRecord) -> None:
        if record.spec.namespace is not self.namespace or record.spec.manifest_digest != self.manifest.digest:
            raise M20IntegrityError("record/store identity mismatch")
        if record.execution_id != record.spec.execution_id or record.schema != M20_RECORD_SCHEMA:
            raise M20IntegrityError("record identity/schema mismatch")
        if not record.provenance or any(not value for value in record.provenance.values()):
            raise M20IntegrityError("critical provenance is missing")
        path = self.root / (record.execution_id + ".json")
        if path.exists():
            raise FileExistsError("completed execution already exists")
        self._atomic(path, {**record.canonical(), "digest": record.digest})

    def records(self) -> tuple[dict[str, Any], ...]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for path in sorted(self.root.glob("*.json")):
            if path.name == "manifest.json":
                continue
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("execution_id") in seen or path.stem != value.get("execution_id"):
                raise M20IntegrityError("duplicate or malformed completed evidence")
            digest = value.pop("digest", None)
            if digest != canonical_hash(value):
                raise M20IntegrityError("evidence digest mismatch")
            seen.add(value["execution_id"])
            result.append(value)
        return tuple(result)

    def completed_ids(self) -> frozenset[str]:
        return frozenset(item["execution_id"] for item in self.records())

    def reconcile(self, expected: tuple[M20ExecutionSpec, ...]) -> dict[str, int]:
        ids = self.completed_ids()
        expected_ids = {item.execution_id for item in expected}
        return {"expected": len(expected_ids), "completed": len(ids & expected_ids),
                "missing": len(expected_ids - ids), "incomplete": 0, "invalid": 0,
                "duplicates": 0, "replacement_linked": sum(item.replacement_of is not None for item in expected),
                "namespace_contamination": 0}


class M20Harness:
    """Official adapter -> environment -> evaluator -> evidence path."""

    def __init__(self, manifest: M20Manifest, registry: M20ConditionRegistry,
                 environment: M20Environment, evaluator: M20Evaluator) -> None:
        if environment.environment_id != manifest.environment_id or evaluator.evaluator_id != manifest.evaluator_id:
            raise M20IntegrityError("environment/evaluator identity mismatch")
        self.manifest, self.registry, self.environment, self.evaluator = manifest, registry, environment, evaluator

    def validate_reachability(self, case: M20Case) -> bool:
        state = self.environment.initial_public_state(case.public)
        for raw in case.private.reference_witness:
            proposal = M20Proposal(M20ProposalKind(raw["kind"]), raw.get("action_id"), raw.get("payload"))
            if proposal.kind is M20ProposalKind.ANSWER:
                return self.evaluator.evaluate(case, state, proposal.payload) is M20Outcome.SUCCESS
            if proposal.action_id not in case.public.actions:
                return False
            state = self.environment.apply(case.public, state, proposal).state
        return False

    def preflight(self, spec: M20ExecutionSpec) -> M20Case:
        if spec.namespace is M20Namespace.FORMAL:
            raise PermissionError("formal execution is not authorized")
        if spec.suite_id != self.manifest.suite_id or spec.manifest_digest != self.manifest.digest:
            raise M20IntegrityError("manifest binding mismatch")
        binding = self.registry.binding(spec.condition)
        if spec.provider_hash != binding.provider_hash:
            raise M20IntegrityError("provider binding mismatch")
        case = self.manifest.case(spec.case_id)
        if not self.validate_reachability(case):
            raise M20IntegrityError("case reference witness is not reachable")
        return case

    def run(self, spec: M20ExecutionSpec, adapter: M20AdaptiveAdapter | M20FixedAdapter) -> M20ExecutionRecord:
        case = self.preflight(spec)
        binding = self.registry.binding(spec.condition)
        if adapter.condition is not spec.condition or adapter.adapter_id != binding.adapter_id:
            raise M20IntegrityError("adapter/condition binding mismatch")
        state = self.environment.initial_public_state(case.public)
        telemetry = M20ResourceTelemetry()
        resources = ResourceState(tuple(ResourceAllocation(kind, 32) for kind in ResourceDimension),
                                  "m20:" + spec.execution_id, "m19_resource_v1", "initial")
        recoverable = False
        for _ in range(32):
            if isinstance(adapter, M20FixedAdapter):
                if recoverable:
                    resources = resources.consume(ResourceDimension.REASONING_STEP, 1, "replan")
                    telemetry = M20ResourceTelemetry(telemetry.reasoning_steps + 1, telemetry.tool_attempts,
                                                     telemetry.provider_interactions, telemetry.decision_cycles,
                                                     telemetry.provider_transport_attempts)
                resources = resources.consume(ResourceDimension.REASONING_STEP, 1, "reason")
                telemetry = M20ResourceTelemetry(telemetry.reasoning_steps + 1, telemetry.tool_attempts,
                                                 telemetry.provider_interactions, telemetry.decision_cycles,
                                                 telemetry.provider_transport_attempts)
            try:
                proposal = adapter.propose(case.public, state)
            except Exception:
                return self._record(spec, M20Outcome.PROVIDER_FAILURE, telemetry, binding.adapter_id)
            telemetry = M20ResourceTelemetry(telemetry.reasoning_steps, telemetry.tool_attempts,
                                             telemetry.provider_interactions + 1, telemetry.decision_cycles + 1,
                                             telemetry.provider_transport_attempts + 1)
            resources = resources.consume(ResourceDimension.PROVIDER_INTERACTION, 1, "proposal")
            if proposal.kind is M20ProposalKind.ANSWER:
                outcome = self.evaluator.evaluate(case, state, proposal.payload)
                return self._record(spec, outcome, telemetry, binding.adapter_id)
            if proposal.action_id not in case.public.actions:
                return self._record(spec, M20Outcome.INVALID_INTERACTION, telemetry, binding.adapter_id)
            resources = resources.consume(ResourceDimension.TOOL_ATTEMPT, 1, "action")
            telemetry = M20ResourceTelemetry(telemetry.reasoning_steps, telemetry.tool_attempts + 1,
                                             telemetry.provider_interactions, telemetry.decision_cycles,
                                             telemetry.provider_transport_attempts)
            result = self.environment.apply(case.public, state, proposal)
            if result.infrastructure_failure:
                return self._record(spec, M20Outcome.INFRASTRUCTURE_FAILURE, telemetry, binding.adapter_id)
            state, recoverable = result.state, result.recoverable
            if result.terminal:
                return self._record(spec, M20Outcome.FAILURE_OR_INCORRECT, telemetry, binding.adapter_id)
        return self._record(spec, M20Outcome.INCOMPLETE, telemetry, binding.adapter_id)

    def replacement(self, failed: M20ExecutionRecord) -> M20ExecutionSpec:
        if failed.outcome not in {M20Outcome.PROVIDER_FAILURE, M20Outcome.INFRASTRUCTURE_FAILURE}:
            raise PermissionError("performance outcomes cannot be rerun")
        if failed.spec.replacement_of is not None:
            raise PermissionError("replacement chains are prohibited")
        return M20ExecutionSpec(failed.spec.suite_id, failed.spec.case_id, failed.spec.repetition,
                                failed.spec.condition, failed.spec.namespace, failed.spec.manifest_digest,
                                failed.spec.provider_hash, failed.execution_id)

    def _record(self, spec: M20ExecutionSpec, outcome: M20Outcome, telemetry: M20ResourceTelemetry,
                adapter_id: str) -> M20ExecutionRecord:
        provenance = {"harness": M20_HARNESS_ID, "provenance_schema": M20_PROVENANCE_SCHEMA,
                      "suite": self.manifest.suite_id, "environment": self.manifest.environment_id,
                      "evaluator": self.manifest.evaluator_id, "condition": spec.condition.value,
                      "provider_hash": spec.provider_hash, "metrics": M20_METRIC_VERSION,
                      "protocol": M20_PROTOCOL_ID, "manifest": self.manifest.digest, "adapter": adapter_id}
        return M20ExecutionRecord(spec.execution_id, spec.pair_id, spec, outcome, telemetry,
                                  self.manifest.environment_id, self.manifest.evaluator_id, adapter_id, provenance)
