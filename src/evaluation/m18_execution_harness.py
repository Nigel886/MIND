"""Architecture-neutral M18 execution harness.

The harness owns private case/evaluator access.  Adapter inputs are derived
public projections only.  Importing this module never starts provider execution.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Mapping, Protocol

from src.core.observation import Observation
from src.core.cognitive_session import CognitiveAgentSession, CognitiveSessionPhase
from src.core.environment_outcome import EnvironmentOutcome, EnvironmentOutcomeCategory, EnvironmentOutcomeReason
from src.core.policy_context import PolicyDecisionContext
from src.core.runtime import RuntimeController
from src.core.task import Goal, Task
from src.core.tool import CapabilityDescriptor
from src.evaluation.contracts import EvaluationAction, EvaluationActionType, EvaluationCase, EvaluationFeedback, EvaluationFeedbackType
from src.evaluation.execution import AgentStepInput, EvaluationBudget, EvaluationBudgetState
from src.evaluation.m18_direct_tool_calling import M18DirectToolCallingBaseline
from src.evaluation.m18_mind_policy_condition import M18MINDPolicyCondition
from src.evaluation.m18_plan_and_execute import M18PlanAndExecuteBaseline
from src.evaluation.m18_react import M18ReActBaseline
from src.evaluation.m18_shared_provider import M18ProviderTransportError, M18SharedProviderClient, M18SharedProviderConfiguration, M18SharedMINDProvider, M18SharedDirectProvider, M18SharedReActProvider, M18SharedPlanProvider
from src.evaluation.m18_task_generation import M18Case, M18DeterministicEnvironment, M18EnvironmentCategory, M18EvaluationCategory, M18Evaluator, M18Namespace, canonical_hash, canonical_json


M18_HARNESS_VERSION = "m18_shared_execution_harness_v5"
M18_RESULT_SCHEMA_VERSION = "m18_result_record_v3"
M18_SCHEDULE_POLICY = "balanced_case_repetition_rotation_v1"
M18_RESUME_POLICY = "atomic_per_run_provenance_validate_v4"
M18_FORMAL_REPETITIONS = 5
M18_SCHEDULE_SEED = "m18_schedule_seed_v1"
M18_SYSTEMS = ("mind_lite_v11", "direct_tool_calling", "react", "plan_and_execute")
M18_SYSTEM_ARTIFACTS = {"mind_lite_v11": "99bbe96c7413024f3c76f1c3439c51593770c22e+b4f1daa5be8c4e6d4ea623e6dc61aa0321e203b0", "direct_tool_calling": "4aa402ea85fdfc8b92f5f180a6d5f3ac461a6a43", "react": "62901b2c9fcbcb79374ee30eab8a77418e9d4849", "plan_and_execute": "0c0decad89793d2b8b1b9d943febd23b9b377759"}


def _hash(value: Any) -> str: return sha256(canonical_json(value).encode("utf-8")).hexdigest()


class M18RuntimeTerminal(str, Enum):
    ANSWER_SUBMITTED = "answer_submitted"
    BUDGET_EXHAUSTED = "budget_exhausted"
    INVALID_ACTION_EXHAUSTED = "invalid_action_exhausted"
    UNRECOVERABLE_ENVIRONMENT_FAILURE = "unrecoverable_environment_failure"
    AGENT_INTERNAL_FAILURE = "agent_internal_failure"
    PROVIDER_FAILURE = "provider_failure"
    INFRASTRUCTURE_INVALID = "infrastructure_invalid"

class M18ExecutionMode(str, Enum):
    SYNTHETIC = "synthetic"
    FROZEN = "frozen"


class M18ExecutionIntegrityError(RuntimeError):
    """Frozen-execution invariant breach; never an ordinary benchmark outcome."""

    def __init__(self, category: str, stage: str, detail: str) -> None:
        super().__init__(detail)
        self.category, self.stage, self.detail = category, stage, detail


def neutral_failure(runtime: M18RuntimeTerminal, evaluator: M18EvaluationCategory | None) -> M18EvaluationCategory:
    if runtime is M18RuntimeTerminal.ANSWER_SUBMITTED:
        return evaluator or M18EvaluationCategory.WRONG_ANSWER
    mapping = {
        M18RuntimeTerminal.BUDGET_EXHAUSTED: M18EvaluationCategory.BUDGET_EXHAUSTED,
        M18RuntimeTerminal.INVALID_ACTION_EXHAUSTED: M18EvaluationCategory.INVALID_ACTION_EXHAUSTED,
        M18RuntimeTerminal.UNRECOVERABLE_ENVIRONMENT_FAILURE: M18EvaluationCategory.UNRECOVERABLE_ENVIRONMENT_FAILURE,
        M18RuntimeTerminal.AGENT_INTERNAL_FAILURE: M18EvaluationCategory.AGENT_INTERNAL_FAILURE,
        M18RuntimeTerminal.PROVIDER_FAILURE: M18EvaluationCategory.PROVIDER_FAILURE,
        M18RuntimeTerminal.INFRASTRUCTURE_INVALID: M18EvaluationCategory.INFRASTRUCTURE_INVALID,
    }
    return mapping[runtime]


@dataclass(frozen=True)
class M18RunSpec:
    suite_version: str; case_id: str; system_condition: str; repetition: int; provider_config_hash: str
    schedule_seed: str = M18_SCHEDULE_SEED
    def __post_init__(self) -> None:
        if self.system_condition not in M18_SYSTEMS: raise ValueError("unknown M18 system")
        if not 1 <= self.repetition <= M18_FORMAL_REPETITIONS: raise ValueError("repetition must be 1..5")
        if len(self.provider_config_hash) != 64: raise ValueError("provider hash must be SHA-256")
    @property
    def run_id(self) -> str:
        return _hash({"suite_version": self.suite_version, "case_id": self.case_id, "system_condition": self.system_condition, "repetition": self.repetition, "provider_config_hash": self.provider_config_hash, "harness_version": M18_HARNESS_VERSION})
    def to_dict(self) -> dict[str, Any]: return {**asdict(self), "run_id": self.run_id}


@dataclass(frozen=True)
class M18BudgetCounters:
    decision_cycles: int = 0; logical_provider_calls: int = 0; transport_attempts: int = 0
    tool_calls: int = 0; invalid_actions: int = 0; recoverable_failures: int = 0; replans: int = 0
    def to_dict(self) -> dict[str, int]: return asdict(self)


@dataclass(frozen=True)
class M18RunRecord:
    run_id: str; suite_version: str; case_id: str; cohort: str; difficulty: str; system_condition: str; repetition: int
    provider_config_hash: str; harness_identity: str; runtime_terminal_outcome: str; evaluator_outcome: str | None
    neutral_failure_category: str; budget: M18BudgetCounters; infrastructure_valid: bool
    provider_model: str | None = None; token_telemetry: Mapping[str, int | None] | None = None; latency_ms: int | None = None
    raw_artifact_references: tuple[str, ...] = ()
    result_schema_version: str = M18_RESULT_SCHEMA_VERSION
    experiment_namespace: str = "m18_synthetic_v1"
    system_artifact_identity: str = ""
    tranche_id: str | None = None
    def to_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "suite_version": self.suite_version, "case_id": self.case_id,
                "cohort": self.cohort, "difficulty": self.difficulty, "system_condition": self.system_condition,
                "repetition": self.repetition, "provider_config_hash": self.provider_config_hash,
                "harness_identity": self.harness_identity, "runtime_terminal_outcome": self.runtime_terminal_outcome,
                "evaluator_outcome": self.evaluator_outcome, "neutral_failure_category": self.neutral_failure_category,
                "budget": self.budget.to_dict(), "infrastructure_valid": self.infrastructure_valid,
                "provider_model": self.provider_model, "token_telemetry": dict(self.token_telemetry) if self.token_telemetry else None,
                "latency_ms": self.latency_ms, "raw_artifact_references": list(self.raw_artifact_references),
                "result_schema_version": self.result_schema_version, "experiment_namespace": self.experiment_namespace,
                "system_artifact_identity": self.system_artifact_identity, "tranche_id": self.tranche_id}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "M18RunRecord":
        """Parse a persisted record before it can participate in resume."""
        if not isinstance(value, Mapping):
            raise ValueError("stored record must be an object")
        expected = {
            "run_id", "suite_version", "case_id", "cohort", "difficulty", "system_condition", "repetition",
            "provider_config_hash", "harness_identity", "runtime_terminal_outcome", "evaluator_outcome",
            "neutral_failure_category", "budget", "infrastructure_valid", "provider_model", "token_telemetry",
            "latency_ms", "raw_artifact_references", "result_schema_version", "experiment_namespace",
            "system_artifact_identity", "tranche_id",
        }
        if set(value) != expected or not isinstance(value["budget"], Mapping):
            raise ValueError("stored record schema mismatch")
        budget = M18BudgetCounters(**dict(value["budget"]))
        telemetry = value["token_telemetry"]
        if telemetry is not None and not isinstance(telemetry, Mapping):
            raise ValueError("stored token telemetry must be an object or null")
        references = value["raw_artifact_references"]
        if not isinstance(references, list) or any(not isinstance(item, str) for item in references):
            raise ValueError("stored raw artifact references must be a string list")
        return cls(
            value["run_id"], value["suite_version"], value["case_id"], value["cohort"], value["difficulty"],
            value["system_condition"], value["repetition"], value["provider_config_hash"],
            value["harness_identity"], value["runtime_terminal_outcome"], value["evaluator_outcome"],
            value["neutral_failure_category"], budget, value["infrastructure_valid"], value["provider_model"],
            dict(telemetry) if telemetry is not None else None, value["latency_ms"], tuple(references),
            value["result_schema_version"], value["experiment_namespace"], value["system_artifact_identity"], value["tranche_id"],
        )


@dataclass(frozen=True)
class M18HarnessManifest:
    suite_version: str; suite_manifest_hash: str; split_hash: str; provider_config_hash: str
    repetitions: int; schedule_seed: str; expected_run_count: int; systems: tuple[str, ...]
    harness_identity: str; result_schema_version: str = M18_RESULT_SCHEMA_VERSION
    experiment_namespace: str = "m18_synthetic_v1"
    system_artifact_identities: Mapping[str, str] | None = None
    def to_dict(self) -> dict[str, Any]: return {**asdict(self), "systems": list(self.systems), "system_artifact_identities": dict(self.system_artifact_identities or {})}


def harness_identity() -> str:
    return _hash({"version": M18_HARNESS_VERSION, "result_schema": M18_RESULT_SCHEMA_VERSION,
                  "schedule": M18_SCHEDULE_POLICY, "resume": M18_RESUME_POLICY,
                  "failure_mapping": "neutral_failure_mapping_v1"})


def balanced_schedule(case_ids: tuple[str, ...], provider_config_hash: str, *, repetitions: int = M18_FORMAL_REPETITIONS, seed: str = M18_SCHEDULE_SEED) -> tuple[M18RunSpec, ...]:
    """Deterministic per-case/repetition rotation; never system-blocked."""
    if repetitions != M18_FORMAL_REPETITIONS: raise ValueError("formal schedule requires exactly five repetitions")
    specs: list[M18RunSpec] = []
    for case_id in sorted(case_ids):
        for repetition in range(1, repetitions + 1):
            offset = int(_hash({"seed": seed, "case_id": case_id, "repetition": repetition})[:8], 16) % len(M18_SYSTEMS)
            rotated = M18_SYSTEMS[offset:] + M18_SYSTEMS[:offset]
            specs.extend(M18RunSpec("m18_suite_v1", case_id, system, repetition, provider_config_hash, seed) for system in rotated)
    return tuple(specs)


def formal_manifest(provider_config_hash: str, suite_manifest: Mapping[str, Any], split: Mapping[str, Any]) -> tuple[M18HarnessManifest, tuple[M18RunSpec, ...]]:
    case_ids = tuple(split["formal_ids"])
    specs = balanced_schedule(case_ids, provider_config_hash)
    manifest = M18HarnessManifest("m18_suite_v1", suite_manifest["manifest_hash"], suite_manifest["split_hash"], provider_config_hash,
                                  M18_FORMAL_REPETITIONS, M18_SCHEDULE_SEED, len(specs), M18_SYSTEMS, harness_identity(), experiment_namespace="m18_formal_v1", system_artifact_identities=M18_SYSTEM_ARTIFACTS)
    if len(case_ids) != 162 or len(specs) != 3240: raise ValueError("frozen formal manifest count mismatch")
    return manifest, specs


class M18ResultStore:
    """Atomic per-run JSON storage with duplicate rejection and resume reconciliation."""
    def __init__(self, root: Path, manifest: M18HarnessManifest, allowed_specs: tuple[M18RunSpec, ...] = (), *, metadata_filenames: tuple[str, ...] = (), required_tranche_id: str | None = None) -> None:
        self.root, self.manifest, self._allowed = root, manifest, {item.run_id: item for item in allowed_specs}
        self._metadata_filenames = frozenset(("manifest.json",) + metadata_filenames)
        if required_tranche_id is not None and (not isinstance(required_tranche_id, str) or not required_tranche_id):
            raise ValueError("required tranche id must be a non-empty string")
        self._required_tranche_id = required_tranche_id
        self.root.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self.root / "manifest.json"
        if self._manifest_path.exists():
            if json.loads(self._manifest_path.read_text(encoding="utf-8")) != manifest.to_dict(): raise ValueError("configuration drift")
        else: self._atomic(self._manifest_path, manifest.to_dict())
    def _atomic(self, path: Path, value: Mapping[str, Any]) -> None:
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=self.root, suffix=".tmp") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"), ensure_ascii=False); handle.write("\n"); temporary = Path(handle.name)
        temporary.replace(path)
    def persist(self, record: M18RunRecord) -> None:
        self._validate_record(record)
        path = self.root / (record.run_id + ".json")
        if path.exists(): raise FileExistsError("duplicate completed run id")
        self._atomic(path, record.to_dict())
    def completed_ids(self) -> frozenset[str]:
        """Return only provenance-valid completed identities, or fail closed."""
        stored: list[tuple[Path, M18RunRecord]] = []
        claimed: set[str] = set()
        for path in sorted(self.root.glob("*.json")):
            if path.name in self._metadata_filenames:
                continue
            try:
                record = M18RunRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
                raise ValueError(f"stored record provenance corruption: {path.name}") from error
            if record.run_id in claimed:
                raise ValueError("duplicate stored record run id")
            claimed.add(record.run_id)
            stored.append((path, record))
        completed: set[str] = set()
        for path, record in stored:
            if path.stem != record.run_id:
                raise ValueError("stored record filename/run-id mismatch")
            self._validate_record(record)
            completed.add(record.run_id)
        return frozenset(completed)
    def missing(self, specs: tuple[M18RunSpec, ...]) -> tuple[M18RunSpec, ...]: return tuple(item for item in specs if item.run_id not in self.completed_ids())
    def _validate_record(self, record: M18RunRecord) -> None:
        if record.suite_version != self.manifest.suite_version or record.provider_config_hash != self.manifest.provider_config_hash or record.harness_identity != self.manifest.harness_identity or record.result_schema_version != self.manifest.result_schema_version or record.experiment_namespace != self.manifest.experiment_namespace:
            raise ValueError("record manifest identity mismatch")
        expected_artifact = (self.manifest.system_artifact_identities or {}).get(record.system_condition)
        if expected_artifact is not None and record.system_artifact_identity != expected_artifact: raise ValueError("record system artifact mismatch")
        if self._required_tranche_id is not None and record.tranche_id != self._required_tranche_id:
            raise ValueError("record tranche identity mismatch")
        if self._allowed:
            spec = self._allowed.get(record.run_id)
            if spec is None or (record.case_id, record.system_condition, record.repetition, record.provider_config_hash) != (spec.case_id, spec.system_condition, spec.repetition, spec.provider_config_hash): raise ValueError("record is not an allowed manifest run")
        else:
            canonical = M18RunSpec(record.suite_version, record.case_id, record.system_condition, record.repetition, record.provider_config_hash, self.manifest.schedule_seed)
            if record.run_id != canonical.run_id:
                raise ValueError("record run id is not canonical")


def _capabilities(case: M18Case) -> tuple[CapabilityDescriptor, ...]:
    return tuple(CapabilityDescriptor(item["tool_id"], item["display_name"], item["description"], item["parameter_schema"]) for item in case.public_view().tools)


def _feedback(outcome: Any) -> EvaluationFeedback:
    mapping = {M18EnvironmentCategory.SUCCESS: EvaluationFeedbackType.TOOL_RESPONSE,
               M18EnvironmentCategory.RECOVERABLE_FAILURE: EvaluationFeedbackType.TOOL_FAILURE,
               M18EnvironmentCategory.INVALID_ACTION: EvaluationFeedbackType.INVALID_ACTION,
               M18EnvironmentCategory.UNRECOVERABLE_FAILURE: EvaluationFeedbackType.TOOL_FAILURE}
    payload = dict(outcome.payload)
    if outcome.category is M18EnvironmentCategory.RECOVERABLE_FAILURE: payload["category"] = "recoverable_failure"
    if outcome.category is M18EnvironmentCategory.UNRECOVERABLE_FAILURE: payload["category"] = "unrecoverable_failure"
    return EvaluationFeedback(mapping[outcome.category], payload)


def _action_dict(action: EvaluationAction) -> dict[str, Any]:
    payload = action.to_dict()["payload"]
    if action.action_type is EvaluationActionType.ANSWER: return {"action": "answer", "answer": payload.get("answer")}
    if action.action_type is EvaluationActionType.TOOL_CALL: return {"action": "tool_call", "tool_name": payload["tool_name"], "parameters": payload["parameters"]}
    return {"action": "invalid"}


class M18Adapter(Protocol):
    system_condition: str
    def initialize(self, case: M18Case) -> None: ...
    def next_decision(self, feedback: EvaluationFeedback, budget: EvaluationBudgetState) -> EvaluationAction: ...
    def accept_observation(self, feedback: EvaluationFeedback) -> None: ...
    def telemetry_snapshot(self) -> Mapping[str, Any]: ...


def _shared_telemetry(client: Any, fallback_calls: int) -> Mapping[str, Any]:
    """Use the canonical client counters; never infer attempts from decisions."""
    if not isinstance(client, M18SharedProviderClient):
        return {"logical_provider_calls": fallback_calls, "transport_attempts": 0}
    responses = tuple(client.responses)
    token_names = ("prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens")
    tokens = {name: sum(getattr(item, name) or 0 for item in responses) for name in token_names} if responses else None
    return {
        "logical_provider_calls": client.logical_provider_calls,
        "transport_attempts": client.transport_attempts,
        "provider_model": responses[-1].returned_model if responses else None,
        "token_telemetry": tokens,
        "latency_ms": sum(item.latency_ms for item in responses) if responses else None,
    }


class _BaselineAdapter:
    def __init__(self, system_condition: str, make: Callable[[tuple[CapabilityDescriptor, ...]], Any]) -> None:
        self.system_condition, self._make, self._baseline, self._case = system_condition, make, None, None
    def initialize(self, case: M18Case) -> None: self._case, self._baseline = case, self._make(_capabilities(case))
    def next_decision(self, feedback: EvaluationFeedback, budget: EvaluationBudgetState) -> EvaluationAction:
        assert self._case is not None and self._baseline is not None
        task = Task(Goal(self._case.public.task_text, ("act using public capability information",)), {"task_text": self._case.public.task_text})
        result = self._baseline.step(AgentStepInput(EvaluationCase(self._case.case_id, task), feedback, budget))
        return result.action
    def accept_observation(self, feedback: EvaluationFeedback) -> None: return None
    def telemetry_snapshot(self) -> Mapping[str, Any]:
        value = self._baseline
        calls = getattr(value, "logical_provider_calls", getattr(value, "planner_calls", 0) + getattr(value, "executor_calls", 0) + getattr(value, "replan_calls", 0))
        data = dict(_shared_telemetry(getattr(getattr(value, "_provider", None), "client", None), calls))
        data.update({"tool_calls": getattr(value, "tool_calls", 0), "invalid_actions": getattr(value, "invalid_action_feedbacks", 0), "recoverable_failures": getattr(value, "recovery_feedbacks", 0), "replans": getattr(value, "replan_calls", 0)})
        return data


class M18MINDAdapter:
    system_condition = "mind_lite_v11"
    def __init__(self, provider: Any) -> None: self._condition, self._case, self._caps, self._session = M18MINDPolicyCondition(provider), None, (), None
    def initialize(self, case: M18Case) -> None:
        self._case, self._caps = case, _capabilities(case)
        task = Task(Goal(case.public.task_text, ("choose a public action",)), {"task_text": case.public.task_text})
        self._session = CognitiveAgentSession(3, policy_engine=self._condition, capabilities=self._caps)
        self._session.start(task)
    def next_decision(self, feedback: EvaluationFeedback, budget: EvaluationBudgetState) -> EvaluationAction:
        assert self._session is not None
        result = self._session.step()
        if result.phase is not CognitiveSessionPhase.AWAITING_OBSERVATION: raise RuntimeError("MIND session terminated before public action")
        request = result.action_request
        assert request is not None
        if request.action == "answer": return EvaluationAction(EvaluationActionType.ANSWER, {"answer": request.parameters["answer"]})
        return EvaluationAction(EvaluationActionType.TOOL_CALL, {"tool_name": request.parameters["tool_name"], "parameters": request.parameters["parameters"]})
    def accept_observation(self, feedback: EvaluationFeedback) -> None:
        assert self._session is not None
        payload = feedback.to_dict()["payload"]
        if feedback.feedback_type is EvaluationFeedbackType.TOOL_RESPONSE:
            outcome = EnvironmentOutcome(EnvironmentOutcomeCategory.SUCCESS, EnvironmentOutcomeReason.SUCCESSFUL_RESULT, payload)
        elif feedback.feedback_type is EvaluationFeedbackType.TOOL_FAILURE and payload.get("category") == "recoverable_failure":
            outcome = EnvironmentOutcome(EnvironmentOutcomeCategory.RECOVERABLE_FAILURE, EnvironmentOutcomeReason.TOOL_TRANSIENT_FAILURE, {k:v for k,v in payload.items() if k != "category"})
        elif feedback.feedback_type is EvaluationFeedbackType.INVALID_ACTION:
            outcome = EnvironmentOutcome(EnvironmentOutcomeCategory.INVALID_ACTION, EnvironmentOutcomeReason.INVALID_ARGUMENTS, payload)
        else:
            outcome = EnvironmentOutcome(EnvironmentOutcomeCategory.UNRECOVERABLE_FAILURE, EnvironmentOutcomeReason.ENVIRONMENT_REJECTED, payload)
        self._session.observe(outcome.to_observation())
    def telemetry_snapshot(self) -> Mapping[str, Any]:
        data = dict(_shared_telemetry(getattr(self._condition._provider, "client", None), self._condition.logical_provider_calls))
        data.update({"tool_calls": 0, "invalid_actions": 0, "recoverable_failures": 0, "replans": 0})
        return data


def direct_adapter(provider: Any) -> _BaselineAdapter:
    adapter = _BaselineAdapter("direct_tool_calling", lambda caps: M18DirectToolCallingBaseline(provider, caps)); adapter.provider_identity = getattr(provider, "client", None); return adapter
def react_adapter(provider: Any) -> _BaselineAdapter:
    adapter = _BaselineAdapter("react", lambda caps: M18ReActBaseline(provider, caps)); adapter.provider_identity = getattr(provider, "client", None); return adapter
def plan_adapter(provider: Any) -> _BaselineAdapter:
    adapter = _BaselineAdapter("plan_and_execute", lambda caps: M18PlanAndExecuteBaseline(provider, caps)); adapter.provider_identity = getattr(provider, "client", None); return adapter

class M18FrozenProviderBinding:
    """Fail-closed admission of the one #118 client/configuration into all adapters."""
    def __init__(self, client: M18SharedProviderClient) -> None:
        if type(client) is not M18SharedProviderClient: raise TypeError("frozen execution requires M18SharedProviderClient")
        expected = M18SharedProviderConfiguration()
        if client.configuration.to_dict() != expected.to_dict() or client.configuration.config_hash != expected.config_hash:
            raise ValueError("frozen provider configuration drift")
        self.client, self.provider_config_hash = client, expected.config_hash
    def adapters(self) -> dict[str, M18Adapter]:
        return {"mind_lite_v11": M18MINDAdapter(M18SharedMINDProvider(self.client)),
                "direct_tool_calling": direct_adapter(M18SharedDirectProvider(self.client)),
                "react": react_adapter(M18SharedReActProvider(self.client)),
                "plan_and_execute": plan_adapter(M18SharedPlanProvider(self.client))}


class M18SharedExecutionHarness:
    def __init__(self, provider_config_hash: str, *, max_steps: int = 3, max_tool_calls: int = 1, mode: M18ExecutionMode = M18ExecutionMode.SYNTHETIC, frozen_binding: M18FrozenProviderBinding | None = None) -> None:
        if len(provider_config_hash) != 64: raise ValueError("provider config hash required")
        if not isinstance(mode, M18ExecutionMode): raise TypeError("mode must be M18ExecutionMode")
        if mode is M18ExecutionMode.FROZEN and (frozen_binding is None or frozen_binding.provider_config_hash != provider_config_hash): raise ValueError("frozen execution requires matching canonical provider binding")
        if mode is M18ExecutionMode.SYNTHETIC and frozen_binding is not None: raise ValueError("synthetic execution cannot admit frozen binding")
        self.provider_config_hash, self.budget, self.mode, self.frozen_binding = provider_config_hash, EvaluationBudget(max_steps, max_tool_calls), mode, frozen_binding
        self.environment, self.evaluator = M18DeterministicEnvironment(), M18Evaluator()
    def run_synthetic(self, spec: M18RunSpec, case: M18Case, adapter: M18Adapter) -> M18RunRecord:
        if self.mode is not M18ExecutionMode.SYNTHETIC: raise RuntimeError("synthetic runner is unavailable in frozen mode")
        return self._run(spec, case, adapter, "m18_synthetic_v1")

    def run_frozen_pilot(self, spec: M18RunSpec, case: M18Case, *, tranche_id: str | None = None) -> M18RunRecord:
        """Execute one already-admitted frozen-pilot run; formal execution is absent."""
        if self.mode is not M18ExecutionMode.FROZEN or self.frozen_binding is None:
            raise RuntimeError("frozen pilot execution requires canonical frozen mode")
        if case.namespace is not M18Namespace.PILOT or not spec.case_id.startswith("pilot."):
            raise ValueError("frozen pilot execution accepts pilot cases only")
        if spec.provider_config_hash != self.provider_config_hash:
            raise ValueError("frozen pilot provider hash mismatch")
        adapters = self.frozen_binding.adapters()
        return self._run(spec, case, adapters[spec.system_condition], "m18_pilot_v1", tranche_id=tranche_id)

    def _run(self, spec: M18RunSpec, case: M18Case, adapter: M18Adapter, experiment_namespace: str, *, tranche_id: str | None = None) -> M18RunRecord:
        if spec.case_id != case.case_id or spec.system_condition != adapter.system_condition: raise ValueError("run/adaptor mismatch")
        adapter.initialize(case); feedback = EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT); state = EvaluationBudgetState(self.budget); runtime = None; evaluator = None; invalid = 0; decisions = 0; submitted_tools = 0
        try:
            for used in range(self.budget.max_steps):
                action = adapter.next_decision(feedback, EvaluationBudgetState(self.budget, used, min(used, self.budget.max_tool_calls)))
                decisions += 1
                if action.action_type is EvaluationActionType.ANSWER:
                    try:
                        evaluator = self.evaluator.evaluate(case, _action_dict(action)["answer"])
                    except Exception as error:
                        if self.mode is M18ExecutionMode.FROZEN:
                            raise M18ExecutionIntegrityError("evaluator_invariant_failure", "evaluator", type(error).__name__) from error
                        runtime = M18RuntimeTerminal.INFRASTRUCTURE_INVALID
                        break
                    runtime = M18RuntimeTerminal.ANSWER_SUBMITTED
                    break
                if action.action_type is not EvaluationActionType.TOOL_CALL:
                    runtime = M18RuntimeTerminal.AGENT_INTERNAL_FAILURE; break
                submitted_tools += 1
                try:
                    outcome = self.environment.apply(case, _action_dict(action))
                except Exception as error:
                    if self.mode is M18ExecutionMode.FROZEN:
                        raise M18ExecutionIntegrityError("environment_invariant_failure", "environment", type(error).__name__) from error
                    runtime = M18RuntimeTerminal.INFRASTRUCTURE_INVALID; break
                feedback = _feedback(outcome)
                adapter.accept_observation(feedback)
                if outcome.category is M18EnvironmentCategory.INVALID_ACTION:
                    invalid += 1
                    if invalid >= self.budget.max_tool_calls: runtime = M18RuntimeTerminal.INVALID_ACTION_EXHAUSTED; break
                elif outcome.category is M18EnvironmentCategory.UNRECOVERABLE_FAILURE: runtime = M18RuntimeTerminal.UNRECOVERABLE_ENVIRONMENT_FAILURE; break
            runtime = runtime or M18RuntimeTerminal.BUDGET_EXHAUSTED
        except M18ExecutionIntegrityError:
            raise
        except M18ProviderTransportError as error:
            if self.mode is M18ExecutionMode.FROZEN and error.category in {"model_identity_mismatch", "malformed_json"}:
                category = "provider_identity_drift" if error.category == "model_identity_mismatch" else "provider_decoder_incompatibility"
                raise M18ExecutionIntegrityError(category, "provider_decode", error.category) from error
            runtime = M18RuntimeTerminal.PROVIDER_FAILURE
        except Exception as error:
            runtime = M18RuntimeTerminal.PROVIDER_FAILURE if "provider" in type(error).__name__.lower() else M18RuntimeTerminal.AGENT_INTERNAL_FAILURE
        telemetry = adapter.telemetry_snapshot(); counters = M18BudgetCounters(decision_cycles=decisions, logical_provider_calls=int(telemetry.get("logical_provider_calls", 0)), transport_attempts=int(telemetry.get("transport_attempts", 0)), tool_calls=submitted_tools, invalid_actions=invalid, recoverable_failures=int(telemetry.get("recoverable_failures", 0)), replans=int(telemetry.get("replans", 0)))
        category = neutral_failure(runtime, evaluator.category if evaluator else None)
        return M18RunRecord(spec.run_id, spec.suite_version, case.case_id, case.cohort.value, case.difficulty.value, spec.system_condition, spec.repetition, spec.provider_config_hash, harness_identity(), runtime.value, evaluator.category.value if evaluator else None, category.value, counters, runtime is not M18RuntimeTerminal.INFRASTRUCTURE_INVALID, provider_model=telemetry.get("provider_model"), token_telemetry=telemetry.get("token_telemetry"), latency_ms=telemetry.get("latency_ms"), result_schema_version=M18_RESULT_SCHEMA_VERSION, experiment_namespace=experiment_namespace, system_artifact_identity=M18_SYSTEM_ARTIFACTS[spec.system_condition], tranche_id=tranche_id)
