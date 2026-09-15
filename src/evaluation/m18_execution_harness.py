"""Architecture-neutral M18 execution harness; synthetic validation only.

The harness owns private case/evaluator access.  Adapter inputs are derived
public projections only.  This module never starts real provider execution.
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
from src.evaluation.m18_task_generation import M18Case, M18DeterministicEnvironment, M18EnvironmentCategory, M18EvaluationCategory, M18Evaluator, M18Namespace, canonical_hash, canonical_json


M18_HARNESS_VERSION = "m18_shared_execution_harness_v1"
M18_RESULT_SCHEMA_VERSION = "m18_result_record_v1"
M18_SCHEDULE_POLICY = "balanced_case_repetition_rotation_v1"
M18_RESUME_POLICY = "atomic_per_run_duplicate_reject_v1"
M18_FORMAL_REPETITIONS = 5
M18_SCHEDULE_SEED = "m18_schedule_seed_v1"
M18_SYSTEMS = ("mind_lite_v11", "direct_tool_calling", "react", "plan_and_execute")


def _hash(value: Any) -> str: return sha256(canonical_json(value).encode("utf-8")).hexdigest()


class M18RuntimeTerminal(str, Enum):
    ANSWER_SUBMITTED = "answer_submitted"
    BUDGET_EXHAUSTED = "budget_exhausted"
    INVALID_ACTION_EXHAUSTED = "invalid_action_exhausted"
    UNRECOVERABLE_ENVIRONMENT_FAILURE = "unrecoverable_environment_failure"
    AGENT_INTERNAL_FAILURE = "agent_internal_failure"
    PROVIDER_FAILURE = "provider_failure"
    INFRASTRUCTURE_INVALID = "infrastructure_invalid"


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
    def to_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "suite_version": self.suite_version, "case_id": self.case_id,
                "cohort": self.cohort, "difficulty": self.difficulty, "system_condition": self.system_condition,
                "repetition": self.repetition, "provider_config_hash": self.provider_config_hash,
                "harness_identity": self.harness_identity, "runtime_terminal_outcome": self.runtime_terminal_outcome,
                "evaluator_outcome": self.evaluator_outcome, "neutral_failure_category": self.neutral_failure_category,
                "budget": self.budget.to_dict(), "infrastructure_valid": self.infrastructure_valid,
                "provider_model": self.provider_model, "token_telemetry": dict(self.token_telemetry) if self.token_telemetry else None,
                "latency_ms": self.latency_ms, "raw_artifact_references": list(self.raw_artifact_references)}


@dataclass(frozen=True)
class M18HarnessManifest:
    suite_version: str; suite_manifest_hash: str; split_hash: str; provider_config_hash: str
    repetitions: int; schedule_seed: str; expected_run_count: int; systems: tuple[str, ...]
    harness_identity: str; result_schema_version: str = M18_RESULT_SCHEMA_VERSION
    def to_dict(self) -> dict[str, Any]: return {**asdict(self), "systems": list(self.systems)}


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
                                  M18_FORMAL_REPETITIONS, M18_SCHEDULE_SEED, len(specs), M18_SYSTEMS, harness_identity())
    if len(case_ids) != 162 or len(specs) != 3240: raise ValueError("frozen formal manifest count mismatch")
    return manifest, specs


class M18ResultStore:
    """Atomic per-run JSON storage with duplicate rejection and resume reconciliation."""
    def __init__(self, root: Path, manifest: M18HarnessManifest) -> None:
        self.root, self.manifest = root, manifest
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
        path = self.root / (record.run_id + ".json")
        if path.exists(): raise FileExistsError("duplicate completed run id")
        self._atomic(path, record.to_dict())
    def completed_ids(self) -> frozenset[str]: return frozenset(path.stem for path in self.root.glob("*.json") if path.name != "manifest.json")
    def missing(self, specs: tuple[M18RunSpec, ...]) -> tuple[M18RunSpec, ...]: return tuple(item for item in specs if item.run_id not in self.completed_ids())


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
    def telemetry_snapshot(self) -> Mapping[str, int | str | None]: ...


class _BaselineAdapter:
    def __init__(self, system_condition: str, make: Callable[[tuple[CapabilityDescriptor, ...]], Any]) -> None:
        self.system_condition, self._make, self._baseline, self._case = system_condition, make, None, None
    def initialize(self, case: M18Case) -> None: self._case, self._baseline = case, self._make(_capabilities(case))
    def next_decision(self, feedback: EvaluationFeedback, budget: EvaluationBudgetState) -> EvaluationAction:
        assert self._case is not None and self._baseline is not None
        task = Task(Goal(self._case.public.task_text, ("act using public capability information",)), {"task_text": self._case.public.task_text})
        result = self._baseline.step(AgentStepInput(EvaluationCase(self._case.case_id, task), feedback, budget))
        return result.action
    def telemetry_snapshot(self) -> Mapping[str, int | str | None]:
        value = self._baseline
        calls = getattr(value, "logical_provider_calls", getattr(value, "planner_calls", 0) + getattr(value, "executor_calls", 0) + getattr(value, "replan_calls", 0))
        return {"logical_provider_calls": calls, "transport_attempts": getattr(getattr(value, "_provider", None), "client", None).transport_attempts if getattr(getattr(value, "_provider", None), "client", None) else 0,
                "tool_calls": getattr(value, "tool_calls", 0), "invalid_actions": getattr(value, "invalid_action_feedbacks", 0), "recoverable_failures": getattr(value, "recovery_feedbacks", 0), "replans": getattr(value, "replan_calls", 0)}


class M18MINDAdapter:
    system_condition = "mind_lite_v11"
    def __init__(self, provider: Any) -> None: self._condition, self._case, self._caps = M18MINDPolicyCondition(provider), None, ()
    def initialize(self, case: M18Case) -> None: self._case, self._caps = case, _capabilities(case)
    def next_decision(self, feedback: EvaluationFeedback, budget: EvaluationBudgetState) -> EvaluationAction:
        assert self._case is not None
        task = Task(Goal(self._case.public.task_text, ("choose a public action",)), {"task_text": self._case.public.task_text})
        observation = Observation(source="agent_environment", content=feedback.to_dict()["payload"])
        policy = self._condition.decide(PolicyDecisionContext.from_runtime(task, RuntimeController.initialize(), observation, self._caps))
        if policy.action == "produce_answer": return EvaluationAction(EvaluationActionType.ANSWER, {"answer": policy.parameters["answer"]})
        return EvaluationAction(EvaluationActionType.TOOL_CALL, {"tool_name": policy.parameters["tool_name"], "parameters": policy.parameters["tool_parameters"]})
    def telemetry_snapshot(self) -> Mapping[str, int | str | None]: return {"logical_provider_calls": self._condition.logical_provider_calls, "transport_attempts": 0, "tool_calls": 0, "invalid_actions": 0, "recoverable_failures": 0, "replans": 0}


def direct_adapter(provider: Any) -> _BaselineAdapter: return _BaselineAdapter("direct_tool_calling", lambda caps: M18DirectToolCallingBaseline(provider, caps))
def react_adapter(provider: Any) -> _BaselineAdapter: return _BaselineAdapter("react", lambda caps: M18ReActBaseline(provider, caps))
def plan_adapter(provider: Any) -> _BaselineAdapter: return _BaselineAdapter("plan_and_execute", lambda caps: M18PlanAndExecuteBaseline(provider, caps))


class M18SharedExecutionHarness:
    def __init__(self, provider_config_hash: str, *, max_steps: int = 3, max_tool_calls: int = 1) -> None:
        if len(provider_config_hash) != 64: raise ValueError("provider config hash required")
        self.provider_config_hash, self.budget = provider_config_hash, EvaluationBudget(max_steps, max_tool_calls)
        self.environment, self.evaluator = M18DeterministicEnvironment(), M18Evaluator()
    def run_synthetic(self, spec: M18RunSpec, case: M18Case, adapter: M18Adapter) -> M18RunRecord:
        if case.namespace is not M18Namespace.PILOT and not case.case_id.startswith("synthetic."): raise ValueError("harness dry-run accepts synthetic cases only")
        if spec.case_id != case.case_id or spec.system_condition != adapter.system_condition: raise ValueError("run/adaptor mismatch")
        adapter.initialize(case); feedback = EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT); state = EvaluationBudgetState(self.budget); runtime = None; evaluator = None; invalid = 0; decisions = 0; submitted_tools = 0
        try:
            for used in range(self.budget.max_steps):
                action = adapter.next_decision(feedback, EvaluationBudgetState(self.budget, used, min(used, self.budget.max_tool_calls)))
                decisions += 1
                if action.action_type is EvaluationActionType.ANSWER:
                    runtime = M18RuntimeTerminal.ANSWER_SUBMITTED; evaluator = self.evaluator.evaluate(case, _action_dict(action)["answer"]); break
                if action.action_type is not EvaluationActionType.TOOL_CALL:
                    runtime = M18RuntimeTerminal.AGENT_INTERNAL_FAILURE; break
                submitted_tools += 1
                try:
                    outcome = self.environment.apply(case, _action_dict(action))
                except Exception:
                    runtime = M18RuntimeTerminal.INFRASTRUCTURE_INVALID; break
                feedback = _feedback(outcome)
                if outcome.category is M18EnvironmentCategory.INVALID_ACTION:
                    invalid += 1
                    if invalid >= self.budget.max_tool_calls: runtime = M18RuntimeTerminal.INVALID_ACTION_EXHAUSTED; break
                elif outcome.category is M18EnvironmentCategory.UNRECOVERABLE_FAILURE: runtime = M18RuntimeTerminal.UNRECOVERABLE_ENVIRONMENT_FAILURE; break
            runtime = runtime or M18RuntimeTerminal.BUDGET_EXHAUSTED
        except Exception as error:
            runtime = M18RuntimeTerminal.PROVIDER_FAILURE if "provider" in type(error).__name__.lower() else M18RuntimeTerminal.AGENT_INTERNAL_FAILURE
        telemetry = adapter.telemetry_snapshot(); counters = M18BudgetCounters(decision_cycles=decisions, logical_provider_calls=int(telemetry.get("logical_provider_calls", 0)), transport_attempts=int(telemetry.get("transport_attempts", 0)), tool_calls=submitted_tools, invalid_actions=invalid, recoverable_failures=int(telemetry.get("recoverable_failures", 0)), replans=int(telemetry.get("replans", 0)))
        category = neutral_failure(runtime, evaluator.category if evaluator else None)
        return M18RunRecord(spec.run_id, spec.suite_version, case.case_id, case.cohort.value, case.difficulty.value, spec.system_condition, spec.repetition, spec.provider_config_hash, harness_identity(), runtime.value, evaluator.category.value if evaluator else None, category.value, counters, runtime is not M18RuntimeTerminal.INFRASTRUCTURE_INVALID)
