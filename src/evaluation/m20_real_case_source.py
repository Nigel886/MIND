"""Prospective, deterministic real-case source for M20; never executes a provider."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from src.evaluation.m20_harness import (
    M20Case, M20EnvironmentResult, M20Outcome, M20PrivateCase, M20Proposal, M20ProposalKind,
    M20PublicCase, canonical_hash, canonical_json,
)


M20_REAL_CASE_SOURCE_VERSION = "m20_real_case_source_v1"
M20_REAL_CASE_SCHEMA = "m20_real_case_v1"
M20_REAL_CASE_REPETITIONS = 5
M20_REAL_COHORTS = (
    "multi_step_stateful", "information_acquisition", "distractor_unnecessary_action",
    "recovery_replanning", "answer_ready_early_stop", "resource_constrained",
)


@dataclass(frozen=True)
class M20RealCaseDefinition:
    case_id: str
    cohort: str
    cluster_id: str
    initial_state: Mapping[str, Any]
    actions: Mapping[str, Mapping[str, Any]]
    target: str
    witness: tuple[Mapping[str, Any], ...]
    provenance: Mapping[str, str]
    eligible: bool = True
    exclusion_reason: str | None = None

    def __post_init__(self) -> None:
        if self.cohort not in M20_REAL_COHORTS or not self.case_id or not self.cluster_id:
            raise ValueError("real case identity/cohort is invalid")
        if not self.actions or not self.target or not self.witness or not self.provenance:
            raise ValueError("real case contract is incomplete")
        if self.eligible == (self.exclusion_reason is not None):
            raise ValueError("eligibility/exclusion rule is inconsistent")

    def canonical(self) -> dict[str, Any]:
        return {
            "schema": M20_REAL_CASE_SCHEMA, "source_version": M20_REAL_CASE_SOURCE_VERSION,
            "case_id": self.case_id, "cohort": self.cohort, "cluster_id": self.cluster_id,
            "initial_state": dict(self.initial_state),
            "actions": {key: dict(value) for key, value in sorted(self.actions.items())},
            "target": self.target, "witness": [dict(item) for item in self.witness],
            "provenance": dict(sorted(self.provenance.items())), "eligible": self.eligible,
            "exclusion_reason": self.exclusion_reason,
        }

    @property
    def payload_digest(self) -> str:
        public = {key: value for key, value in self.canonical().items() if key not in {"target", "witness"}}
        return canonical_hash(public)

    def to_case(self) -> M20Case:
        public = M20PublicCase(self.case_id, self.cohort, self.initial_state["task"], self.initial_state, self.actions)
        return M20Case(public, M20PrivateCase(self.target, self.witness), cluster_id=self.cluster_id,
                       generation_identity=M20_REAL_CASE_SOURCE_VERSION)


class M20RealEnvironment:
    """Condition-neutral deterministic public transition model for the source."""
    environment_id = "m20_environment_v1"

    def initial_public_state(self, case: M20PublicCase) -> Mapping[str, Any]:
        return dict(case.initial_state)

    def apply(self, case: M20PublicCase, state: Mapping[str, Any], proposal: M20Proposal) -> M20EnvironmentResult:
        if proposal.action_id not in case.actions:
            return M20EnvironmentResult(dict(state), "unknown_action", terminal=True)
        result = dict(state); action = case.actions[proposal.action_id]
        kind = action["effect"]
        if kind == "advance": result["progress"] = result.get("progress", 0) + 1
        elif kind == "observe": result["observed"] = True
        elif kind == "recover": result["recovered"] = True
        elif kind == "distract": result["distractors"] = result.get("distractors", 0) + 1
        elif kind != "noop": return M20EnvironmentResult(dict(state), "invalid_contract", terminal=True)
        return M20EnvironmentResult(result, kind, recoverable=(kind == "recover"))


class M20RealEvaluator:
    """Private target/witness owner; target data is never supplied to adapters."""
    evaluator_id = "m20_evaluator_v1"

    def evaluate(self, case: M20Case, state: Mapping[str, Any], answer: Any) -> M20Outcome:
        required = state.get("required_progress", 0)
        if answer != case.private.target or state.get("progress", 0) < required:
            return M20Outcome.FAILURE_OR_INCORRECT
        if state.get("requires_observation") and not state.get("observed"):
            return M20Outcome.FAILURE_OR_INCORRECT
        if state.get("requires_recovery") and not state.get("recovered"):
            return M20Outcome.FAILURE_OR_INCORRECT
        return M20Outcome.SUCCESS


def _definition(cohort: str, index: int) -> M20RealCaseDefinition:
    case_id = f"m20.real.{cohort}.{index:02d}"
    required = 2 if cohort in {"multi_step_stateful", "resource_constrained"} else 1 if cohort == "recovery_replanning" else 0
    state = {"task": f"Complete the public {cohort} task {index}.", "progress": 0,
             "required_progress": required, "requires_observation": cohort == "information_acquisition",
             "requires_recovery": cohort == "recovery_replanning", "observed": False, "recovered": False,
             "resource_note": "shared frozen ceiling required" if cohort == "resource_constrained" else "standard"}
    actions = {"advance": {"schema": {}, "effect": "advance"}, "observe": {"schema": {}, "effect": "observe"},
               "recover": {"schema": {}, "effect": "recover"}, "distract": {"schema": {}, "effect": "distract"}}
    witness: list[Mapping[str, Any]] = []
    if cohort == "information_acquisition": witness.append({"kind": "act", "action_id": "observe"})
    if cohort == "recovery_replanning": witness.append({"kind": "act", "action_id": "recover"})
    witness.extend({"kind": "act", "action_id": "advance"} for _ in range(required))
    witness.append({"kind": "answer", "payload": f"answer:{case_id}"})
    return M20RealCaseDefinition(case_id, cohort, f"m20.real.cluster.{cohort}", state, actions,
                                 f"answer:{case_id}", tuple(witness),
                                 {"authorship": "m20_real_case_source_v1", "template": cohort,
                                  "enumeration": f"{cohort}:index:{index}"})


def real_case_definitions() -> tuple[M20RealCaseDefinition, ...]:
    """Complete prospective universe: two authored deterministic cases per frozen cohort."""
    values = tuple(_definition(cohort, index) for cohort in M20_REAL_COHORTS for index in (1, 2))
    validate_real_case_definitions(values)
    return values


def validate_real_case_definitions(values: tuple[M20RealCaseDefinition, ...]) -> None:
    """Fail closed on membership, identity, or witness violations before execution."""
    eligible = tuple(item for item in values if item.eligible)
    if len({item.case_id for item in values}) != len(values) or {item.cohort for item in eligible} != set(M20_REAL_COHORTS):
        raise ValueError("real universe completeness/identity failure")
    if len({item.payload_digest for item in values}) != len(values):
        raise ValueError("real universe payload collision")
    environment, evaluator = M20RealEnvironment(), M20RealEvaluator()
    for definition in eligible:
        case, state, result = definition.to_case(), environment.initial_public_state(definition.to_case().public), None
        for raw in definition.witness:
            if raw["kind"] == "answer": result = evaluator.evaluate(case, state, raw["payload"])
            else: state = environment.apply(case.public, state, M20Proposal(M20ProposalKind(raw["kind"]), raw["action_id"])).state
        if result is not M20Outcome.SUCCESS:
            raise ValueError("eligible real case is unreachable")


def real_cases() -> tuple[M20Case, ...]:
    return tuple(item.to_case() for item in real_case_definitions() if item.eligible)


def real_case_source_digest() -> str:
    return canonical_hash({"version": M20_REAL_CASE_SOURCE_VERSION, "repetitions": M20_REAL_CASE_REPETITIONS,
                           "cases": [item.canonical() for item in real_case_definitions()]})


@dataclass(frozen=True)
class M20RealProviderConfiguration:
    """Secret-free canonical schema. No concrete provider choice is made here."""
    provider: str; model: str; api_mode: str; decoding_mode: str; temperature: float; top_p: float | None
    top_k: int | None; output_token_ceiling: int; structured_output_mode: str; tool_mode: str
    timeout_seconds: int; retry_owner: str; retry_ceiling: int; deterministic_seed: int | None

    def __post_init__(self) -> None:
        if any(not isinstance(getattr(self, field), str) or not getattr(self, field) for field in
               ("provider", "model", "api_mode", "decoding_mode", "structured_output_mode", "tool_mode", "retry_owner")):
            raise ValueError("provider identity is incomplete")
        if self.output_token_ceiling < 1 or self.timeout_seconds < 1 or self.retry_ceiling < 0:
            raise ValueError("provider limits are invalid")
        # This closed schema deliberately has no credential, API-key, or secret field.

    def canonical(self) -> dict[str, Any]: return asdict(self)
    @property
    def identity_hash(self) -> str: return canonical_hash(self.canonical())


@dataclass(frozen=True)
class M20RealResourceCeiling:
    identity: str; reasoning_steps: int; tool_attempts: int; provider_interactions: int; decision_cycles: int
    def __post_init__(self) -> None:
        if not self.identity or any(getattr(self, key) < 1 for key in ("reasoning_steps", "tool_attempts", "provider_interactions", "decision_cycles")):
            raise ValueError("resource ceiling is invalid")
    def canonical(self) -> dict[str, Any]: return asdict(self)
    @property
    def digest(self) -> str: return canonical_hash(self.canonical())
