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

from src.core.deliberation_state import DeliberationState, EpistemicSignal, EpistemicState, FailureRecoveryProjection, SignalAvailability, SignalSource
from src.core.meta_control_policy import MetaControlPolicy, MetaControlPolicyConfig, MetaControlPolicyInput, MetaControlRuntimeProjection, RuntimeTerminalState
from src.core.meta_control_runtime import MetaControlExecutionContext, MetaControlRuntimeIntegrator, MetaControlRuntimePhase, MetaControlRuntimeState
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
    CALIBRATION_POSTREMEDIATION = "m20_calibration_postremediation_v1"
    CALIBRATION_CEILINGV2 = "m20_calibration_ceilingv2_v1"
    DIAGNOSTIC = "m20_real_provider_diagnostic_v1"
    DIAGNOSTIC_V3 = "m20_real_provider_diagnostic_v3"
    DIAGNOSTIC_V4 = "m20_real_provider_diagnostic_v4"
    DIAGNOSTIC_V5 = "m20_real_provider_diagnostic_v5"
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
    STOP = "stop"


class M20LifecycleState(str, Enum):
    NOT_STARTED = "not_started"
    ZERO_COMMIT_PARTIAL = "zero_commit_partial"
    CHARGED_PARTIAL = "charged_partial"
    COMPLETED = "completed"
    INVALID = "invalid"


class M20RetryOwner(str, Enum):
    PROVIDER_CLIENT = "provider_client"
    TOOL_EXECUTOR = "tool_executor"


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
class M20ResourceCeiling:
    """Explicit #220 resource allocation; never a harness default."""

    identity: str
    reasoning_steps: int
    tool_attempts: int
    provider_interactions: int
    decision_cycles: int

    def __post_init__(self) -> None:
        if not isinstance(self.identity, str) or not self.identity:
            raise ValueError("resource ceiling identity is required")
        if any(not isinstance(getattr(self, key), int) or getattr(self, key) < 1 for key in
               ("reasoning_steps", "tool_attempts", "provider_interactions", "decision_cycles")):
            raise ValueError("resource ceilings must be positive ints")

    def resource_state(self, execution_id: str) -> ResourceState:
        return ResourceState((
            ResourceAllocation(ResourceDimension.REASONING_STEP, self.reasoning_steps),
            ResourceAllocation(ResourceDimension.TOOL_ATTEMPT, self.tool_attempts),
            ResourceAllocation(ResourceDimension.PROVIDER_INTERACTION, self.provider_interactions),
        ), self.identity + ":" + execution_id, "m19_resource_v1", "m20_initial")


@dataclass(frozen=True)
class M20PairingMetadata:
    case_id: str
    cluster_id: str
    payload_digest: str
    environment_id: str
    evaluator_id: str
    resource_ceiling_identity: str

    def __post_init__(self) -> None:
        if any(not isinstance(getattr(self, key), str) or not getattr(self, key) for key in
               ("case_id", "cluster_id", "payload_digest", "environment_id", "evaluator_id", "resource_ceiling_identity")):
            raise ValueError("pairing metadata is incomplete")


@dataclass(frozen=True)
class M20ResourceDelta:
    transition_id: str
    reasoning_steps: int = 0
    tool_attempts: int = 0
    provider_interactions: int = 0
    decision_cycles: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.transition_id, str) or not self.transition_id:
            raise ValueError("resource delta transition identity is required")
        if any(not isinstance(getattr(self, key), int) or getattr(self, key) < 0 for key in
               ("reasoning_steps", "tool_attempts", "provider_interactions", "decision_cycles")):
            raise ValueError("resource deltas must be non-negative ints")


@dataclass(frozen=True)
class M20RetryAttempt:
    logical_operation_id: str
    physical_attempt_id: str
    retry_index: int
    owner: M20RetryOwner
    reason: str | None
    terminal: bool

    def __post_init__(self) -> None:
        if any(not isinstance(getattr(self, key), str) or not getattr(self, key) for key in
               ("logical_operation_id", "physical_attempt_id")):
            raise ValueError("retry identities are required")
        if not isinstance(self.retry_index, int) or self.retry_index < 0 or not isinstance(self.owner, M20RetryOwner):
            raise ValueError("retry metadata is invalid")


@dataclass(frozen=True)
class M20ProviderOperation:
    """One logical provider interaction and its provider-client attempts.

    The operation is allocated once by the harness before the transport is
    entered.  A retry may only derive a new physical-attempt identity from
    this object; it may not allocate a new logical interaction.
    """
    logical_operation_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.logical_operation_id, str) or not self.logical_operation_id:
            raise ValueError("logical provider operation identity is required")

    def attempt(self, retry_index: int, reason: str | None, terminal: bool) -> M20RetryAttempt:
        if not isinstance(retry_index, int) or retry_index < 0:
            raise ValueError("provider retry index is invalid")
        return M20RetryAttempt(
            self.logical_operation_id,
            canonical_hash({"logical_operation_id": self.logical_operation_id, "retry_index": retry_index}),
            retry_index,
            M20RetryOwner.PROVIDER_CLIENT,
            reason,
            terminal,
        )


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
    cluster_id: str = "m20_cluster_v1"
    frozen_payload_digest: str | None = None

    @property
    def payload_digest(self) -> str:
        if self.frozen_payload_digest is not None:
            return self.frozen_payload_digest
        return canonical_hash(self.public.to_dict())


@dataclass(frozen=True)
class M20Manifest:
    suite_id: str
    environment_id: str
    evaluator_id: str
    cases: tuple[M20Case, ...]
    generation_identity: str
    pairing: tuple[M20PairingMetadata, ...]
    resource_ceiling: M20ResourceCeiling
    schema_version: str = M20_MANIFEST_SCHEMA
    execution_manifest_digest: str | None = None

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
        if not isinstance(self.pairing, tuple) or len(self.pairing) != len(self.cases):
            raise ValueError("manifest pairing metadata is required for every case")
        indexed = {item.case_id: item for item in self.pairing}
        if set(indexed) != set(ids) or len(indexed) != len(self.pairing):
            raise ValueError("pairing case identities are invalid")
        for case in self.cases:
            metadata = indexed[case.public.case_id]
            if (metadata.cluster_id, metadata.payload_digest, metadata.environment_id, metadata.evaluator_id,
                metadata.resource_ceiling_identity) != (case.cluster_id, case.payload_digest,
                                                         self.environment_id, self.evaluator_id,
                                                         self.resource_ceiling.identity):
                raise ValueError("pairing metadata mismatch")
        if self.execution_manifest_digest is not None and (not isinstance(self.execution_manifest_digest, str) or len(self.execution_manifest_digest) != 64):
            raise ValueError("external execution manifest digest is invalid")

    @property
    def digest(self) -> str:
        if self.execution_manifest_digest is not None:
            return self.execution_manifest_digest
        return canonical_hash({"suite_id": self.suite_id, "environment_id": self.environment_id,
                               "evaluator_id": self.evaluator_id, "generation_identity": self.generation_identity,
                               "schema_version": self.schema_version,
                               "resource_ceiling": asdict(self.resource_ceiling),
                               "cases": [{"case_id": item.public.case_id, "cohort": item.public.cohort,
                                          "payload_digest": item.payload_digest,
                                          "cluster_id": item.cluster_id} for item in self.cases],
                               "pairing": [asdict(item) for item in self.pairing]})

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
        if self.kind in {M20ProposalKind.ANSWER, M20ProposalKind.STOP}:
            if self.action_id is not None:
                raise ValueError("terminal proposal has no action id")
            if self.kind is M20ProposalKind.STOP and self.payload is not None:
                raise ValueError("stop has no payload")
        elif not isinstance(self.action_id, str) or not self.action_id:
            raise ValueError("action/observation requires public action id")


M20_ANSWER_READINESS_VERSION = "m20_public_answer_readiness_v1"


def m20_answer_ready(public_state: Mapping[str, Any], task_contract: M20PublicCase) -> bool:
    """Public, non-evaluative completion predicate shared by both M20 conditions.

    It activates only for the explicit real-case public contract.  It uses
    public transition facts (progress/observation/recovery) and never sees a
    private target, witness, evaluator result, or proposed answer payload.
    """
    if not isinstance(public_state, Mapping) or task_contract is None:
        raise TypeError("public answer-readiness inputs are required")
    required = ("required_progress", "requires_observation", "requires_recovery")
    if any(key not in public_state for key in required):
        return False
    progress = public_state.get("progress")
    required_progress = public_state.get("required_progress")
    if (not isinstance(progress, int) or isinstance(progress, bool)
            or not isinstance(required_progress, int) or isinstance(required_progress, bool)
            or required_progress < 0):
        return False
    if progress < required_progress:
        return False
    if bool(public_state["requires_observation"]) and public_state.get("observed") is not True:
        return False
    if bool(public_state["requires_recovery"]) and public_state.get("recovered") is not True:
        return False
    return True


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


class M20ProviderAttemptError(RuntimeError):
    """Typed deterministic provider-boundary failure; provider client owns retry."""
    def __init__(self, reason: str, retryable: bool = True,
                 diagnostic: Mapping[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason, self.retryable = reason, retryable
        self.diagnostic = dict(diagnostic or {})


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
        self.native_decision_count = 0

    def native_propose(self, public_case: M20PublicCase, public_state: Mapping[str, Any],
                       resources: ResourceState, provider_call: Any = None) -> tuple[M20Proposal, object]:
        """The only Adaptive proposal path: native M19 admits the provider call."""
        if not isinstance(resources, ResourceState):
            raise TypeError("Adaptive execution requires the harness ResourceState")
        proposal: M20Proposal | None = None

        def observe() -> None:
            nonlocal proposal
            proposal = (provider_call() if provider_call is not None
                        else self._provider.propose(public_case, public_state))

        available = EpistemicSignal(SignalAvailability.AVAILABLE, 1.0, SignalSource.RUNTIME_DERIVED, "m20_fake", "v1")
        deliberation = DeliberationState(
            "m20:" + public_case.case_id,
            EpistemicState(available, available, available, available, available, "m19_epistemic_v1", "m20_epistemic"),
            FailureRecoveryProjection((), "m19_history_v1", "m20_history"),
            "m19_deliberation_v1", "m20_deliberation",
        )
        projection = MetaControlRuntimeProjection("m20:" + public_case.case_id, RuntimeTerminalState.ACTIVE,
                                                  False, False, True, False)
        config = MetaControlPolicyConfig("m19_policy_v1", "m19_formalism_v1", 0, 0, 0, 0, 0, 0, 1)
        decision = self.policy.decide(MetaControlPolicyInput(deliberation, resources, projection), config)
        runtime = MetaControlRuntimeState(deliberation, resources, MetaControlRuntimePhase.ACTIVE, "m20_native_initial")
        result = MetaControlRuntimeIntegrator.execute(
            decision, runtime, MetaControlExecutionContext("m20_native_execute", acquire_observation=observe),
        )
        if result.outcome_code != "executed" or proposal is None:
            raise M20IntegrityError("native M19 adaptive execution rejected")
        self.native_decision_count += 1
        return proposal, result

    def propose(self, public_case: M20PublicCase, public_state: Mapping[str, Any]) -> M20Proposal:
        raise M20IntegrityError("Adaptive proposals must traverse the harness-owned native M19 path")


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
    cluster_id: str
    payload_digest: str
    environment_id: str
    evaluator_id: str
    resource_ceiling_identity: str
    replacement_of: str | None = None
    frozen_pair_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.condition, M20Condition) or not isinstance(self.namespace, M20Namespace):
            raise TypeError("execution condition or namespace invalid")
        if self.repetition < 1:
            raise ValueError("repetition must be positive")
        if any(not isinstance(value, str) or not value for value in
               (self.suite_id, self.case_id, self.manifest_digest, self.provider_hash, self.cluster_id,
                self.payload_digest, self.environment_id, self.evaluator_id, self.resource_ceiling_identity)):
            raise ValueError("execution identity is invalid")
        if self.replacement_of is not None and (not isinstance(self.replacement_of, str) or not self.replacement_of):
            raise ValueError("replacement identity is invalid")
        if self.frozen_pair_id is not None and (not isinstance(self.frozen_pair_id, str) or len(self.frozen_pair_id) != 64):
            raise ValueError("frozen pair identity is invalid")

    @property
    def execution_id(self) -> str:
        return canonical_hash({"suite": self.suite_id, "case": self.case_id, "repetition": self.repetition,
                               "condition": self.condition.value, "namespace": self.namespace.value,
                               "manifest": self.manifest_digest, "provider": self.provider_hash,
                               "cluster": self.cluster_id, "payload": self.payload_digest,
                               "environment": self.environment_id, "evaluator": self.evaluator_id,
                               "ceiling": self.resource_ceiling_identity,
                               "replacement_of": self.replacement_of, "frozen_pair_id": self.frozen_pair_id, "schema": M20_RECORD_SCHEMA,
                               "harness": M20_HARNESS_ID})

    @property
    def pair_id(self) -> str:
        if self.frozen_pair_id is not None:
            return self.frozen_pair_id
        return canonical_hash({"suite": self.suite_id, "case": self.case_id, "repetition": self.repetition,
                               "manifest": self.manifest_digest, "cluster": self.cluster_id,
                               "payload": self.payload_digest, "environment": self.environment_id,
                               "evaluator": self.evaluator_id, "ceiling": self.resource_ceiling_identity})


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
    deltas: tuple[M20ResourceDelta, ...] = ()
    retries: tuple[M20RetryAttempt, ...] = ()
    response_diagnostics: tuple[Mapping[str, Any], ...] = ()
    answer_ready_first_cycle: int | None = None
    answer_phase_entered: bool = False
    proposal_kinds: tuple[str, ...] = ()
    answer_proposed: bool = False
    stop_proposed: bool = False
    illegal_act_in_answer_phase: bool = False
    evaluator_handoff: bool = False

    def __post_init__(self) -> None:
        if any(not isinstance(getattr(self, key), int) or getattr(self, key) < 0 for key in
               ("reasoning_steps", "tool_attempts", "provider_interactions", "decision_cycles", "provider_transport_attempts")):
            raise ValueError("resource counts must be non-negative ints")
        if any(not isinstance(item, Mapping) for item in self.response_diagnostics):
            raise ValueError("response diagnostics must be mappings")
        if self.answer_ready_first_cycle is not None and (not isinstance(self.answer_ready_first_cycle, int) or self.answer_ready_first_cycle < 1):
            raise ValueError("answer-readiness cycle is invalid")
        if any(not isinstance(value, bool) for value in (self.answer_phase_entered, self.answer_proposed,
                                                           self.stop_proposed, self.illegal_act_in_answer_phase,
                                                           self.evaluator_handoff)):
            raise ValueError("answer-phase telemetry is invalid")
        if any(not isinstance(value, str) or not value for value in self.proposal_kinds):
            raise ValueError("proposal-kind telemetry is invalid")

    def reconcile(self, ceiling: M20ResourceCeiling, pre: ResourceState | None = None,
                  post: ResourceState | None = None) -> None:
        totals = {
            "reasoning_steps": sum(item.reasoning_steps for item in self.deltas),
            "tool_attempts": sum(item.tool_attempts for item in self.deltas),
            "provider_interactions": sum(item.provider_interactions for item in self.deltas),
            "decision_cycles": sum(item.decision_cycles for item in self.deltas),
        }
        if any(totals[key] != getattr(self, key) for key in totals):
            raise M20IntegrityError("resource delta total mismatch")
        if any(totals[key] > getattr(ceiling, key) for key in totals):
            raise M20IntegrityError("resource ceiling exceeded")
        if (pre is None) != (post is None):
            raise M20IntegrityError("resource state reconciliation requires pre and post")
        if pre is not None and post is not None:
            if pre.allocation_identity != post.allocation_identity or pre.version != post.version:
                raise M20IntegrityError("resource state identity changed")
            expected = {ResourceDimension.REASONING_STEP: totals["reasoning_steps"],
                        ResourceDimension.TOOL_ATTEMPT: totals["tool_attempts"],
                        ResourceDimension.PROVIDER_INTERACTION: totals["provider_interactions"]}
            for dimension, amount in expected.items():
                if post.allocation(dimension).consumed - pre.allocation(dimension).consumed != amount:
                    raise M20IntegrityError("resource state/delta mismatch")
        logical = {item.logical_operation_id for item in self.retries}
        if self.provider_transport_attempts != len(self.retries) or any(
            sum(item.logical_operation_id == operation for item in self.retries if item.owner is M20RetryOwner.PROVIDER_CLIENT) < 1
            for operation in logical
        ):
            raise M20IntegrityError("retry attribution mismatch")


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
    cohort: str
    lifecycle: M20LifecycleState = M20LifecycleState.COMPLETED
    resource_pre: Mapping[str, Any] | None = None
    resource_post: Mapping[str, Any] | None = None
    replacement_reason: str | None = None
    schema: str = M20_RECORD_SCHEMA

    def canonical(self) -> dict[str, Any]:
        telemetry = asdict(self.telemetry)
        # The optional field was introduced after the historical #250 records.
        # Omitting it when empty preserves their canonical payloads and digests.
        if not telemetry["response_diagnostics"]:
            del telemetry["response_diagnostics"]
        for key, default in (("answer_ready_first_cycle", None), ("answer_phase_entered", False),
                             ("proposal_kinds", ()), ("answer_proposed", False), ("stop_proposed", False),
                             ("illegal_act_in_answer_phase", False), ("evaluator_handoff", False)):
            if telemetry.get(key) == default or (key == "proposal_kinds" and telemetry.get(key) == []):
                telemetry.pop(key, None)
        return {"execution_id": self.execution_id, "pair_id": self.pair_id, "cohort": self.cohort,
                "lifecycle": self.lifecycle.value,
                "spec": {"suite_id": self.spec.suite_id, "case_id": self.spec.case_id,
                         "repetition": self.spec.repetition, "condition": self.spec.condition.value,
                         "namespace": self.spec.namespace.value, "manifest_digest": self.spec.manifest_digest,
                         "provider_hash": self.spec.provider_hash, "cluster_id": self.spec.cluster_id,
                         "payload_digest": self.spec.payload_digest, "environment_id": self.spec.environment_id,
                         "evaluator_id": self.spec.evaluator_id,
                         "resource_ceiling_identity": self.spec.resource_ceiling_identity,
                         "replacement_of": self.spec.replacement_of, "frozen_pair_id": self.spec.frozen_pair_id},
                "outcome": self.outcome.value, "telemetry": telemetry,
                "environment_id": self.environment_id, "evaluator_id": self.evaluator_id,
                "adapter_id": self.adapter_id, "provenance": dict(self.provenance),
                "resource_pre": dict(self.resource_pre or {}), "resource_post": dict(self.resource_post or {}),
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
        partial = self.root / (record.execution_id + ".partial.json")
        if partial.exists():
            raise M20IntegrityError("partial evidence must be reconciled before completion")
        if path.exists():
            raise FileExistsError("completed execution already exists")
        self._atomic(path, {**record.canonical(), "digest": record.digest})

    def lifecycle(self, spec: M20ExecutionSpec) -> M20LifecycleState:
        if (self.root / (spec.execution_id + ".json")).exists():
            return M20LifecycleState.COMPLETED
        path = self.root / (spec.execution_id + ".partial.json")
        if not path.exists():
            return M20LifecycleState.NOT_STARTED
        value = json.loads(path.read_text(encoding="utf-8"))
        return M20LifecycleState(value["lifecycle"])

    def mark_partial(self, spec: M20ExecutionSpec, telemetry: M20ResourceTelemetry) -> None:
        """Preserve interruption; continuation is allowed only with zero committed delta."""
        if spec.namespace is not self.namespace or spec.manifest_digest != self.manifest.digest:
            raise M20IntegrityError("partial/store identity mismatch")
        path = self.root / (spec.execution_id + ".partial.json")
        if path.exists() or (self.root / (spec.execution_id + ".json")).exists():
            raise FileExistsError("execution lifecycle already recorded")
        lifecycle = (M20LifecycleState.ZERO_COMMIT_PARTIAL if not any((telemetry.reasoning_steps, telemetry.tool_attempts,
                     telemetry.provider_interactions, telemetry.decision_cycles, telemetry.provider_transport_attempts))
                     else M20LifecycleState.CHARGED_PARTIAL)
        self._atomic(path, {"lifecycle": lifecycle.value, "execution_id": spec.execution_id,
                            "spec": spec.execution_id, "telemetry": asdict(telemetry)})

    def resume_partial(self, spec: M20ExecutionSpec) -> None:
        path = self.root / (spec.execution_id + ".partial.json")
        if not path.exists():
            return
        value = json.loads(path.read_text(encoding="utf-8"))
        telemetry = M20ResourceTelemetry(**value["telemetry"])
        if value["lifecycle"] != M20LifecycleState.ZERO_COMMIT_PARTIAL.value or any((telemetry.reasoning_steps, telemetry.tool_attempts, telemetry.provider_interactions,
                telemetry.decision_cycles, telemetry.provider_transport_attempts)):
            raise M20IntegrityError("committed partial execution cannot be resumed by guessing")
        # Preserve the interruption evidence; a resumed episode may never erase
        # the fact that it was interrupted before committing a resource.
        path.replace(self.root / (spec.execution_id + ".partial.resolved.json"))

    @staticmethod
    def statistical_input(record: Mapping[str, Any]) -> dict[str, Any]:
        """Fail-closed #221 schema projection from persisted canonical evidence."""
        required = ("pair_id", "cohort", "lifecycle", "outcome", "telemetry", "spec", "provenance")
        if any(key not in record for key in required):
            raise M20IntegrityError("statistical evidence field missing")
        spec, telemetry, provenance = record["spec"], record["telemetry"], record["provenance"]
        fields = ("case_id", "repetition", "cluster_id", "condition", "replacement_of", "payload_digest",
                  "environment_id", "evaluator_id", "resource_ceiling_identity")
        if any(key not in spec for key in fields) or "provider_interactions" not in telemetry or "retries" not in telemetry:
            raise M20IntegrityError("statistical execution evidence missing")
        if "metrics" not in provenance or "protocol" not in provenance:
            raise M20IntegrityError("statistical protocol evidence missing")
        M20EvidenceStore.validate_persisted(record)
        return {"pair_id": record["pair_id"], "cohort": record["cohort"], "outcome": record["outcome"],
                "lifecycle": record["lifecycle"], "spec": spec, "telemetry": telemetry, "provenance": provenance}

    @staticmethod
    def validate_persisted(record: Mapping[str, Any]) -> None:
        """Canonical fail-closed validation of evidence after storage reload."""
        if record.get("lifecycle") != M20LifecycleState.COMPLETED.value or not record.get("cohort") or not record.get("pair_id"):
            raise M20IntegrityError("completed lifecycle/pair/cohort evidence invalid")
        spec, telemetry = record.get("spec"), record.get("telemetry")
        if not isinstance(spec, Mapping) or not isinstance(telemetry, Mapping):
            raise M20IntegrityError("persisted execution evidence invalid")
        required = ("suite_id", "case_id", "repetition", "cluster_id", "condition", "payload_digest", "environment_id", "evaluator_id", "resource_ceiling_identity")
        if any(not spec.get(key) for key in required):
            raise M20IntegrityError("persisted execution identity incomplete")
        attempts = telemetry.get("retries")
        if not isinstance(attempts, list) or not attempts:
            raise M20IntegrityError("retry evidence absent")
        logical: dict[str, list[Mapping[str, Any]]] = {}
        physical: set[str] = set()
        for item in attempts:
            if not isinstance(item, Mapping) or not all(item.get(key) for key in ("logical_operation_id", "physical_attempt_id", "owner")):
                raise M20IntegrityError("retry attempt identity invalid")
            if item["physical_attempt_id"] in physical or item["owner"] != M20RetryOwner.PROVIDER_CLIENT.value:
                raise M20IntegrityError("retry attempt ownership/uniqueness invalid")
            physical.add(item["physical_attempt_id"]); logical.setdefault(item["logical_operation_id"], []).append(item)
        for chain in logical.values():
            if [item.get("retry_index") for item in chain] != list(range(len(chain))) or sum(bool(item.get("terminal")) for item in chain) != 1 or not chain[-1].get("terminal"):
                raise M20IntegrityError("retry chain ordering/terminal state invalid")
            if any(item.get("terminal") for item in chain[:-1]):
                raise M20IntegrityError("retry attempt follows terminal state")
        if telemetry.get("provider_interactions") != len(logical) or telemetry.get("provider_transport_attempts") != len(attempts):
            raise M20IntegrityError("retry/resource accounting mismatch")

    def records(self) -> tuple[dict[str, Any], ...]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for path in sorted(self.root.glob("*.json")):
            if path.name == "manifest.json" or path.name.endswith(".partial.json") or path.name.endswith(".partial.resolved.json"):
                continue
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("execution_id") in seen or path.stem != value.get("execution_id"):
                raise M20IntegrityError("duplicate or malformed completed evidence")
            digest = value.pop("digest", None)
            if digest != canonical_hash(value):
                raise M20IntegrityError("evidence digest mismatch")
            self.validate_persisted(value)
            seen.add(value["execution_id"])
            result.append(value)
        return tuple(result)

    def completed_ids(self) -> frozenset[str]:
        return frozenset(item["execution_id"] for item in self.records())

    def completed_record(self, spec: M20ExecutionSpec) -> M20ExecutionRecord:
        """Reload one immutable completed record after persisted validation."""
        value = next((item for item in self.records() if item["execution_id"] == spec.execution_id), None)
        if value is None or value.get("lifecycle") != M20LifecycleState.COMPLETED.value:
            raise M20IntegrityError("completed evidence is absent or invalid")
        if value["spec"] != M20ExecutionRecord(spec.execution_id, spec.pair_id, spec, M20Outcome.SUCCESS,
                M20ResourceTelemetry(), spec.environment_id, spec.evaluator_id, "placeholder", {}, "placeholder").canonical()["spec"]:
            raise M20IntegrityError("completed evidence/request identity mismatch")
        telemetry = value["telemetry"]
        retries = tuple(M20RetryAttempt(item["logical_operation_id"], item["physical_attempt_id"], item["retry_index"],
                                        M20RetryOwner(item["owner"]), item.get("reason"), item["terminal"])
                        for item in telemetry["retries"])
        deltas = tuple(M20ResourceDelta(**item) for item in telemetry["deltas"])
        rebuilt = M20ResourceTelemetry(telemetry["reasoning_steps"], telemetry["tool_attempts"],
            telemetry["provider_interactions"], telemetry["decision_cycles"], telemetry["provider_transport_attempts"],
            telemetry.get("token_status", "TOKEN_USAGE_UNAVAILABLE"), telemetry.get("cost_status", "COST_NOT_COMPUTABLE"),
            telemetry.get("latency_status", "LATENCY_NOT_RELIABLE"), deltas, retries,
            tuple(telemetry.get("response_diagnostics", ())),
            telemetry.get("answer_ready_first_cycle"), telemetry.get("answer_phase_entered", False),
            tuple(telemetry.get("proposal_kinds", ())), telemetry.get("answer_proposed", False),
            telemetry.get("stop_proposed", False), telemetry.get("illegal_act_in_answer_phase", False),
            telemetry.get("evaluator_handoff", False))
        return M20ExecutionRecord(value["execution_id"], value["pair_id"], spec, M20Outcome(value["outcome"]), rebuilt,
            value["environment_id"], value["evaluator_id"], value["adapter_id"], value["provenance"], value["cohort"],
            M20LifecycleState(value["lifecycle"]), value.get("resource_pre"), value.get("resource_post"),
            value.get("replacement_reason"), value.get("schema", M20_RECORD_SCHEMA))

    def reconcile(self, expected: tuple[M20ExecutionSpec, ...]) -> dict[str, int]:
        ids = self.completed_ids()
        expected_ids = {item.execution_id for item in expected}
        partial_ids = {path.name.removesuffix(".partial.json") for path in self.root.glob("*.partial.json")}
        resolved_ids = {path.name.removesuffix(".partial.resolved.json") for path in self.root.glob("*.partial.resolved.json")}
        return {"expected": len(expected_ids), "completed": len(ids & expected_ids),
                "missing": len(expected_ids - ids - partial_ids - resolved_ids), "incomplete": len(partial_ids), "invalid": 0,
                "duplicates": 0, "replacement_linked": sum(item.replacement_of is not None for item in expected),
                "namespace_contamination": 0}

    @staticmethod
    def reconstruct_pair(records: tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
        """Admit one persisted primary pair without relying on manifest objects."""
        if len(records) != 2 or any("pair_id" not in item or "cohort" not in item for item in records):
            raise M20IntegrityError("persisted pair evidence missing")
        if len({item["pair_id"] for item in records}) != 1:
            raise M20IntegrityError("persisted pair identity mismatch")
        specs = [item.get("spec") for item in records]
        keys = ("suite_id", "case_id", "repetition", "cluster_id", "payload_digest", "environment_id", "evaluator_id", "resource_ceiling_identity")
        if any(not isinstance(spec, Mapping) for spec in specs) or any(any(spec[key] != specs[0][key] for spec in specs[1:]) for key in keys):
            raise M20IntegrityError("persisted pair metadata mismatch")
        if len({item["cohort"] for item in records}) != 1 or {spec["condition"] for spec in specs} != {M20Condition.MIND_ADAPTIVE.value, M20Condition.MIND_FIXED.value}:
            raise M20IntegrityError("persisted pair condition/cohort mismatch")
        return {"pair_id": records[0]["pair_id"], "cohort": records[0]["cohort"], "adaptive": next(item for item in records if item["spec"]["condition"] == M20Condition.MIND_ADAPTIVE.value), "fixed": next(item for item in records if item["spec"]["condition"] == M20Condition.MIND_FIXED.value)}


class M20Harness:
    """Official adapter -> environment -> evaluator -> evidence path."""

    def __init__(self, manifest: M20Manifest, registry: M20ConditionRegistry,
                 environment: M20Environment, evaluator: M20Evaluator,
                 provenance_overrides: Mapping[str, str] | None = None,
                 answer_termination_enabled: bool = False) -> None:
        if environment.environment_id != manifest.environment_id or evaluator.evaluator_id != manifest.evaluator_id:
            raise M20IntegrityError("environment/evaluator identity mismatch")
        self.manifest, self.registry, self.environment, self.evaluator = manifest, registry, environment, evaluator
        self._active_store: M20EvidenceStore | None = None
        self._provenance_overrides = dict(provenance_overrides or {})
        if not isinstance(answer_termination_enabled, bool):
            raise TypeError("answer-termination policy flag is invalid")
        self.answer_termination_enabled = answer_termination_enabled
        if any(not isinstance(key, str) or not key or not isinstance(value, str) or not value
               for key, value in self._provenance_overrides.items()):
            raise ValueError("provenance overrides must be non-empty strings")

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
        pairing = next(item for item in self.manifest.pairing if item.case_id == case.public.case_id)
        if (spec.cluster_id, spec.payload_digest, spec.environment_id, spec.evaluator_id,
            spec.resource_ceiling_identity) != (pairing.cluster_id, pairing.payload_digest,
                                                 pairing.environment_id, pairing.evaluator_id,
                                                 pairing.resource_ceiling_identity):
            raise M20IntegrityError("execution pairing metadata mismatch")
        if not self.validate_reachability(case):
            raise M20IntegrityError("case reference witness is not reachable")
        return case

    def admit_pair(self, first: M20ExecutionSpec, second: M20ExecutionSpec) -> tuple[M20Case, M20Case]:
        """Canonical paired admission; callers cannot mark a pair valid manually."""
        left, right = self.preflight(first), self.preflight(second)
        if first.condition is second.condition:
            raise M20IntegrityError("paired conditions must be distinct")
        keys = ("suite_id", "case_id", "repetition", "cluster_id", "payload_digest", "environment_id",
                "evaluator_id", "resource_ceiling_identity")
        if any(getattr(first, key) != getattr(second, key) for key in keys):
            raise M20IntegrityError("paired execution metadata mismatch")
        return left, right

    @staticmethod
    def _provider_attempt(adapter: Any, public: M20PublicCase, state: Mapping[str, Any],
                          operation: M20ProviderOperation, retries: list[M20RetryAttempt],
                          diagnostics: list[Mapping[str, Any]]) -> M20Proposal:
        """Single provider-client retry owner; evidence is emitted at each call."""
        ceiling = getattr(adapter._provider, "retry_ceiling", 0)
        for index in range(ceiling + 1):
            try:
                proposal = adapter._provider.propose(public, state)
                if not isinstance(proposal, M20Proposal):
                    raise M20ProviderAttemptError("malformed_response", False)
                diagnostic = getattr(adapter._provider, "last_diagnostic", None)
                if isinstance(diagnostic, Mapping):
                    diagnostics.append(dict(diagnostic))
                retries.append(operation.attempt(index, None if index == 0 else "provider_retry", True))
                return proposal
            except M20ProviderAttemptError as error:
                if error.diagnostic:
                    diagnostics.append(dict(error.diagnostic))
                retries.append(operation.attempt(index, error.reason, not error.retryable or index == ceiling))
                if not error.retryable or index == ceiling:
                    raise
        raise M20IntegrityError("unreachable retry state")

    def run(self, spec: M20ExecutionSpec, adapter: M20AdaptiveAdapter | M20FixedAdapter,
            store: M20EvidenceStore | None = None, interrupt_before_execution: bool = False,
            interrupt_after_commit: bool = False) -> M20ExecutionRecord:
        """Canonical execution owns optional durable lifecycle persistence and resume."""
        if store is not None:
            state = store.lifecycle(spec)
            if state is M20LifecycleState.COMPLETED:
                return store.completed_record(spec)
            if state is M20LifecycleState.CHARGED_PARTIAL:
                raise M20IntegrityError("charged partial cannot be resumed safely")
            if state is M20LifecycleState.ZERO_COMMIT_PARTIAL:
                store.resume_partial(spec)
            if interrupt_before_execution:
                store.mark_partial(spec, M20ResourceTelemetry())
                raise InterruptedError("canonical zero-commit interruption")
        self._active_store = store
        case = self.preflight(spec)
        binding = self.registry.binding(spec.condition)
        if adapter.condition is not spec.condition or adapter.adapter_id != binding.adapter_id:
            raise M20IntegrityError("adapter/condition binding mismatch")
        state = self.environment.initial_public_state(case.public)
        deltas: list[M20ResourceDelta] = []
        retries: list[M20RetryAttempt] = []
        diagnostics: list[Mapping[str, Any]] = []
        counts = {"reasoning_steps": 0, "tool_attempts": 0, "provider_interactions": 0, "decision_cycles": 0}
        resources = self.manifest.resource_ceiling.resource_state(spec.execution_id)
        initial_resources = resources
        recoverable = False
        answer_termination = {"answer_ready_first_cycle": None, "answer_phase_entered": False,
                              "proposal_kinds": [], "answer_proposed": False, "stop_proposed": False,
                              "illegal_act_in_answer_phase": False, "evaluator_handoff": False}
        for cycle in range(1, self.manifest.resource_ceiling.decision_cycles + 1):
            # Resource admission precedes every logical provider operation for
            # both conditions.  A hard-budget stop has no executable operation,
            # physical attempt, or provider charge to persist.
            if resources.allocation(ResourceDimension.PROVIDER_INTERACTION).exhausted:
                return self._record(spec, M20Outcome.INCOMPLETE,
                                    self._telemetry(counts, deltas, retries, diagnostics, answer_termination),
                                    binding.adapter_id, initial_resources, resources)
            answer_phase = self.answer_termination_enabled and m20_answer_ready(state, case.public)
            if answer_phase:
                answer_termination["answer_phase_entered"] = True
                if answer_termination["answer_ready_first_cycle"] is None:
                    answer_termination["answer_ready_first_cycle"] = cycle
            if isinstance(adapter, M20FixedAdapter) and not answer_phase:
                if recoverable:
                    resources = resources.consume(ResourceDimension.REASONING_STEP, 1, "replan")
                    counts["reasoning_steps"] += 1; deltas.append(M20ResourceDelta("replan", reasoning_steps=1))
                resources = resources.consume(ResourceDimension.REASONING_STEP, 1, "reason")
                counts["reasoning_steps"] += 1; deltas.append(M20ResourceDelta("reason", reasoning_steps=1))
            try:
                if isinstance(adapter, M20AdaptiveAdapter) and not answer_phase:
                    operation = M20ProviderOperation(canonical_hash({
                        "execution": spec.execution_id,
                        "logical_provider_interaction": counts["provider_interactions"] + 1,
                    }))
                    proposal, native_result = adapter.native_propose(
                        case.public, state, resources,
                        lambda: self._provider_attempt(adapter, case.public, state, operation, retries, diagnostics))
                    resources = native_result.state.resource_state
                    counts["provider_interactions"] += 1; counts["decision_cycles"] += 1
                    deltas.append(M20ResourceDelta("native:" + resources.transition_identity,
                                                    provider_interactions=1, decision_cycles=1))
                else:
                    operation = M20ProviderOperation(canonical_hash({
                        "execution": spec.execution_id,
                        "logical_provider_interaction": counts["provider_interactions"] + 1,
                    }))
                    # Reserve the one logical interaction before the first
                    # physical attempt. Provider-client retries share this
                    # reservation and cannot add another logical charge.
                    resources = resources.consume(ResourceDimension.PROVIDER_INTERACTION, 1, "proposal")
                    counts["provider_interactions"] += 1; counts["decision_cycles"] += 1
                    deltas.append(M20ResourceDelta("proposal", provider_interactions=1, decision_cycles=1))
                    proposal = self._provider_attempt(adapter, case.public, state, operation, retries, diagnostics)
                if interrupt_after_commit and store is not None:
                    store.mark_partial(spec, self._telemetry(counts, deltas, retries, diagnostics))
                    raise InterruptedError("canonical charged interruption")
            except InterruptedError:
                raise
            except Exception:
                # A provider-client accepted logical operation is charged once,
                # even when all physical attempts fail before a proposal exists.
                if retries and counts["provider_interactions"] == 0:
                    resources = resources.consume(ResourceDimension.PROVIDER_INTERACTION, 1, "provider_failure")
                    counts["provider_interactions"] += 1; counts["decision_cycles"] += 1
                    deltas.append(M20ResourceDelta("provider_failure", provider_interactions=1, decision_cycles=1))
                if any(item.get("illegal_act_in_answer_phase") is True for item in diagnostics):
                    answer_termination["illegal_act_in_answer_phase"] = True
                return self._record(spec, M20Outcome.PROVIDER_FAILURE, self._telemetry(counts, deltas, retries, diagnostics, answer_termination), binding.adapter_id, initial_resources, resources)
            answer_termination["proposal_kinds"].append(proposal.kind.value)
            if answer_phase and proposal.kind in {M20ProposalKind.ACT, M20ProposalKind.OBSERVE}:
                answer_termination["illegal_act_in_answer_phase"] = True
                return self._record(spec, M20Outcome.INVALID_INTERACTION,
                                    self._telemetry(counts, deltas, retries, diagnostics, answer_termination),
                                    binding.adapter_id, initial_resources, resources)
            if proposal.kind is M20ProposalKind.ANSWER:
                answer_termination["answer_proposed"] = True
                answer_termination["evaluator_handoff"] = True
                outcome = self.evaluator.evaluate(case, state, proposal.payload)
                return self._record(spec, outcome, self._telemetry(counts, deltas, retries, diagnostics, answer_termination), binding.adapter_id, initial_resources, resources)
            if proposal.kind is M20ProposalKind.STOP:
                answer_termination["stop_proposed"] = True
                return self._record(spec, M20Outcome.INCOMPLETE,
                                    self._telemetry(counts, deltas, retries, diagnostics, answer_termination),
                                    binding.adapter_id, initial_resources, resources)
            if proposal.action_id not in case.public.actions:
                return self._record(spec, M20Outcome.INVALID_INTERACTION, self._telemetry(counts, deltas, retries, diagnostics, answer_termination), binding.adapter_id, initial_resources, resources)
            resources = resources.consume(ResourceDimension.TOOL_ATTEMPT, 1, "action")
            counts["tool_attempts"] += 1; deltas.append(M20ResourceDelta("action", tool_attempts=1))
            result = self.environment.apply(case.public, state, proposal)
            if result.infrastructure_failure:
                return self._record(spec, M20Outcome.INFRASTRUCTURE_FAILURE, self._telemetry(counts, deltas, retries, diagnostics, answer_termination), binding.adapter_id, initial_resources, resources)
            state, recoverable = result.state, result.recoverable
            if result.terminal:
                return self._record(spec, M20Outcome.FAILURE_OR_INCORRECT, self._telemetry(counts, deltas, retries, diagnostics, answer_termination), binding.adapter_id, initial_resources, resources)
        return self._record(spec, M20Outcome.INCOMPLETE, self._telemetry(counts, deltas, retries, diagnostics, answer_termination), binding.adapter_id, initial_resources, resources)

    @staticmethod
    def _telemetry(counts: Mapping[str, int], deltas: list[M20ResourceDelta],
                   retries: list[M20RetryAttempt], diagnostics: list[Mapping[str, Any]] | None = None,
                   answer_termination: Mapping[str, Any] | None = None) -> M20ResourceTelemetry:
        answer_termination = dict(answer_termination or {})
        return M20ResourceTelemetry(**counts, provider_transport_attempts=len(retries),
                                    deltas=tuple(deltas), retries=tuple(retries),
                                    response_diagnostics=tuple(dict(item) for item in (diagnostics or ())),
                                    answer_ready_first_cycle=answer_termination.get("answer_ready_first_cycle"),
                                    answer_phase_entered=answer_termination.get("answer_phase_entered", False),
                                    proposal_kinds=tuple(answer_termination.get("proposal_kinds", ())),
                                    answer_proposed=answer_termination.get("answer_proposed", False),
                                    stop_proposed=answer_termination.get("stop_proposed", False),
                                    illegal_act_in_answer_phase=answer_termination.get("illegal_act_in_answer_phase", False),
                                    evaluator_handoff=answer_termination.get("evaluator_handoff", False))

    def replacement(self, failed: M20ExecutionRecord) -> M20ExecutionSpec:
        if failed.outcome not in {M20Outcome.PROVIDER_FAILURE, M20Outcome.INFRASTRUCTURE_FAILURE}:
            raise PermissionError("performance outcomes cannot be rerun")
        if failed.spec.replacement_of is not None:
            raise PermissionError("replacement chains are prohibited")
        return M20ExecutionSpec(failed.spec.suite_id, failed.spec.case_id, failed.spec.repetition,
                                failed.spec.condition, failed.spec.namespace, failed.spec.manifest_digest,
                                failed.spec.provider_hash, failed.spec.cluster_id, failed.spec.payload_digest,
                                failed.spec.environment_id, failed.spec.evaluator_id,
                                failed.spec.resource_ceiling_identity, failed.execution_id)

    def _record(self, spec: M20ExecutionSpec, outcome: M20Outcome, telemetry: M20ResourceTelemetry,
                adapter_id: str, pre: ResourceState, post: ResourceState) -> M20ExecutionRecord:
        provenance = {"harness": M20_HARNESS_ID, "provenance_schema": M20_PROVENANCE_SCHEMA,
                      "suite": self.manifest.suite_id, "environment": self.manifest.environment_id,
                      "evaluator": self.manifest.evaluator_id, "condition": spec.condition.value,
                      "provider_hash": spec.provider_hash, "metrics": M20_METRIC_VERSION,
                      "protocol": M20_PROTOCOL_ID, "manifest": self.manifest.digest, "adapter": adapter_id}
        provenance.update(self._provenance_overrides)
        telemetry.reconcile(self.manifest.resource_ceiling, pre, post)
        record = M20ExecutionRecord(spec.execution_id, spec.pair_id, spec, outcome, telemetry,
                                    self.manifest.environment_id, self.manifest.evaluator_id, adapter_id, provenance,
                                    self.manifest.case(spec.case_id).public.cohort, M20LifecycleState.COMPLETED,
                                    pre.to_dict(), post.to_dict())
        if self._active_store is not None:
            self._active_store.persist(record)
        return record
