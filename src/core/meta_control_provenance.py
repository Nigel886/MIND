"""Immutable, deterministic M19 decision provenance and execution telemetry."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from src.core.meta_control_policy import MetaDecision, MetaDecisionType
from src.core.meta_control_runtime import MetaControlExecutionResult, MetaControlRuntimePhase, MetaControlRuntimeState
from src.core.resource_accounting import ResourceDimension, ResourceState


class MetaControlExecutionOutcome(str, Enum):
    EXECUTED = "executed"
    REJECTED_PRECONDITION = "rejected_precondition"
    EXHAUSTED_RESOURCE = "exhausted_resource"
    EXECUTION_FAILURE = "execution_failure"
    TERMINAL_ANSWER = "terminal_answer"
    TERMINAL_STOP = "terminal_stop"
    ALREADY_TERMINAL = "already_terminal"


def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


@dataclass(frozen=True)
class ResourceDelta:
    """Explicit non-negative delta derived from immutable #212 states."""

    reasoning_steps: int
    tool_attempts: int
    provider_interactions: int

    def __post_init__(self) -> None:
        for name in ("reasoning_steps", "tool_attempts", "provider_interactions"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int")

    @classmethod
    def between(cls, pre: ResourceState, post: ResourceState) -> "ResourceDelta":
        if not isinstance(pre, ResourceState) or not isinstance(post, ResourceState):
            raise TypeError("pre and post must be ResourceState values")
        if pre.allocation_identity != post.allocation_identity:
            raise ValueError("resource allocation identity must not change")
        values = []
        for dimension in ResourceDimension:
            before = pre.allocation(dimension)
            after = post.allocation(dimension)
            if before.capacity != after.capacity or after.consumed < before.consumed:
                raise ValueError("resource transition resurrects or changes capacity")
            values.append(after.consumed - before.consumed)
        return cls(*values)

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResourceDelta":
        if not isinstance(data, dict):
            raise TypeError("ResourceDelta data must be a dict")
        try:
            return cls(data["reasoning_steps"], data["tool_attempts"], data["provider_interactions"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid ResourceDelta data") from error


@dataclass(frozen=True)
class MetaDecisionProvenance:
    """Structured public evidence for one committed decision, without CoT."""

    decision_identity: str
    decision: MetaDecisionType
    policy_version: str
    formalism_version: str
    runtime_projection_identity: str
    deliberation_transition_identity: str
    resource_transition_identity: str
    reason_code: str
    rule_code: str
    transition_intent_identity: str
    tie_break_applied: bool
    fallback_applied: bool

    def __post_init__(self) -> None:
        if not isinstance(self.decision, MetaDecisionType):
            raise TypeError("decision must be a MetaDecisionType")
        for name in ("decision_identity", "policy_version", "formalism_version", "runtime_projection_identity", "deliberation_transition_identity", "resource_transition_identity", "reason_code", "rule_code", "transition_intent_identity"):
            _text(getattr(self, name), name)
        if not isinstance(self.tie_break_applied, bool) or not isinstance(self.fallback_applied, bool):
            raise TypeError("tie_break_applied and fallback_applied must be bool")

    @classmethod
    def from_decision(cls, decision_identity: str, decision: MetaDecision, transition_intent_identity: str) -> "MetaDecisionProvenance":
        if not isinstance(decision, MetaDecision):
            raise TypeError("decision must be a MetaDecision")
        return cls(
            decision_identity, decision.decision, decision.policy_version, decision.formalism_version,
            decision.runtime_projection_identity, decision.deliberation_transition_identity,
            decision.resource_transition_identity, decision.reason_code, decision.rule_code,
            transition_intent_identity, decision.tie_break_applied, decision.fallback_applied,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["decision"] = self.decision.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MetaDecisionProvenance":
        if not isinstance(data, dict):
            raise TypeError("MetaDecisionProvenance data must be a dict")
        try:
            values = dict(data)
            values["decision"] = MetaDecisionType(values["decision"])
            return cls(**values)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid MetaDecisionProvenance data") from error


@dataclass(frozen=True)
class MetaControlExecutionTelemetry:
    """Immutable one-transition evidence; it has no persistence behavior."""

    decision_identity: str
    decision: MetaDecisionType
    execution_transition_identity: str
    pre_state_identity: str
    post_state_identity: str
    resource_delta: ResourceDelta
    outcome: MetaControlExecutionOutcome
    failure_code: str | None
    terminal: bool

    def __post_init__(self) -> None:
        _text(self.decision_identity, "decision_identity")
        if not isinstance(self.decision, MetaDecisionType):
            raise TypeError("decision must be a MetaDecisionType")
        for name in ("execution_transition_identity", "pre_state_identity", "post_state_identity"):
            _text(getattr(self, name), name)
        if not isinstance(self.resource_delta, ResourceDelta):
            raise TypeError("resource_delta must be a ResourceDelta")
        if not isinstance(self.outcome, MetaControlExecutionOutcome):
            raise TypeError("outcome must be a MetaControlExecutionOutcome")
        if self.failure_code is not None:
            _text(self.failure_code, "failure_code")
        if not isinstance(self.terminal, bool):
            raise TypeError("terminal must be a bool")

    @classmethod
    def from_execution(
        cls,
        provenance: MetaDecisionProvenance,
        pre_state: MetaControlRuntimeState,
        result: MetaControlExecutionResult,
    ) -> "MetaControlExecutionTelemetry":
        if not isinstance(provenance, MetaDecisionProvenance):
            raise TypeError("provenance must be a MetaDecisionProvenance")
        if not isinstance(pre_state, MetaControlRuntimeState) or not isinstance(result, MetaControlExecutionResult):
            raise TypeError("pre_state and result must be runtime values")
        if provenance.decision is not result.decision:
            raise ValueError("provenance decision does not match execution decision")
        post = result.state
        delta = ResourceDelta.between(pre_state.resource_state, post.resource_state)
        code = result.outcome_code
        outcome = {
            "executed": MetaControlExecutionOutcome.EXECUTED,
            "resource_exhausted": MetaControlExecutionOutcome.EXHAUSTED_RESOURCE,
            "execution_failure": MetaControlExecutionOutcome.EXECUTION_FAILURE,
            "answer_committed": MetaControlExecutionOutcome.TERMINAL_ANSWER,
            "stopped": MetaControlExecutionOutcome.TERMINAL_STOP,
            "already_terminal": MetaControlExecutionOutcome.ALREADY_TERMINAL,
        }.get(code, MetaControlExecutionOutcome.REJECTED_PRECONDITION)
        terminal = post.phase is not MetaControlRuntimePhase.ACTIVE
        failure = None if outcome in {MetaControlExecutionOutcome.EXECUTED, MetaControlExecutionOutcome.TERMINAL_ANSWER, MetaControlExecutionOutcome.TERMINAL_STOP} else code
        return cls(provenance.decision_identity, result.decision, post.transition_identity, pre_state.transition_identity, post.transition_identity, delta, outcome, failure, terminal)

    def to_dict(self) -> dict[str, Any]:
        return {"decision_identity": self.decision_identity, "decision": self.decision.value, "execution_transition_identity": self.execution_transition_identity, "pre_state_identity": self.pre_state_identity, "post_state_identity": self.post_state_identity, "resource_delta": self.resource_delta.to_dict(), "outcome": self.outcome.value, "failure_code": self.failure_code, "terminal": self.terminal}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MetaControlExecutionTelemetry":
        if not isinstance(data, dict):
            raise TypeError("MetaControlExecutionTelemetry data must be a dict")
        try:
            return cls(data["decision_identity"], MetaDecisionType(data["decision"]), data["execution_transition_identity"], data["pre_state_identity"], data["post_state_identity"], ResourceDelta.from_dict(data["resource_delta"]), MetaControlExecutionOutcome(data["outcome"]), data.get("failure_code"), data["terminal"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid MetaControlExecutionTelemetry data") from error
