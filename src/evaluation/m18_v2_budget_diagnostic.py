"""Non-canonical, provider-free-admissible M18 v2 budget diagnostics.

This module is intentionally separate from the frozen pilot result contract.
It observes public runtime events only; it never changes the action loop.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Mapping

from src.evaluation.m18_task_generation import canonical_hash, canonical_json
from src.evaluation.m18_v2_pilot_runner import M18V2PilotPlan, M18V2PilotIntegrityError
from src.evaluation.m18_v2_runtime import (
    M18BenchmarkRuntimeCondition, M18V2ResultProvenance, M18V2SharedExecutionHarness,
    M18V2RuntimeResult, M18_V2_RUNTIME_ID, m18_v2_concrete_adapters,
)
from src.evaluation.m18_v2_provenance import M18_V2_COMPARATOR_CONDITIONS
from src.evaluation.m18_v2_provider_diagnostics import M18V2SystematicProviderStop, M18V2SystematicProviderStopEvent


M18_V2_BUDGET_DIAGNOSTIC_CONDITION = "m18_v2_budget_diagnostic_v1"
M18_V2_BUDGET_DIAGNOSTIC_SCHEMA = "m18_v2_budget_diagnostic_record_v1"
M18_V2_BUDGET_DIAGNOSTIC_NAMESPACE = Path("evaluation/m18/results/diagnostic/m18_v2_budget_diagnostic_v1")
M18_V2_BUDGET_DIAGNOSTIC_STORE = "m18_v2_budget_diagnostic_store.json"
M18_V2_BUDGET_DIAGNOSTIC_STOP = "m18_v2_budget_diagnostic_systematic_provider_stop.json"
_DIMENSIONS = frozenset({"action_cycle_limit", "tool_attempt_limit", "logical_provider_call_limit", "invalid_action_limit", "recoverable_failure_limit", "none"})
_TELEMETRY_KEYS = frozenset({"action_cycles_used", "tool_attempts_used", "invalid_actions", "recoverable_failures", "logical_provider_calls", "transport_attempts", "answer_emitted", "first_answer_step", "public_completion_before_first_answer", "last_action_type", "decoder_failure", "decoder_failure_kind"})
_TOKEN_KEYS = frozenset({"prompt_tokens", "completion_tokens", "cached_tokens", "total_tokens", "run_latency_seconds", "provider_call_latency_seconds"})
_TRACE_LIMIT = 6
_DECODER_FAILURE_KINDS = frozenset({"none", "malformed_output", "invalid_schema", "invalid_action_encoding"})
# The diagnostic must faithfully project every existing public
# ``EvaluationAction`` kind.  It never invents an action for decoder failure.
_ACTION_TYPES = frozenset({"tool_call", "answer", "fail", "invalid"})


def derive_diagnostic_run_id(case_id: str, comparator_condition_id: str, repetition: int) -> str:
    if not isinstance(case_id, str) or not case_id or not isinstance(comparator_condition_id, str) or not comparator_condition_id:
        raise ValueError("diagnostic identity strings are required")
    if repetition != 1:
        raise ValueError("the frozen initial diagnostic repetition is 1")
    return canonical_hash({"schema": M18_V2_BUDGET_DIAGNOSTIC_SCHEMA,
                           "condition": M18_V2_BUDGET_DIAGNOSTIC_CONDITION,
                           "source_case_id": case_id, "comparator_condition_id": comparator_condition_id,
                           "diagnostic_repetition": repetition})


def _dimension(reason: str | None) -> str:
    return {"action_cycle_limit": "action_cycle_limit", "tool_attempt_limit": "tool_attempt_limit",
            "logical_provider_call_limit": "logical_provider_call_limit",
            "invalid_action_threshold_reached": "invalid_action_limit",
            "recoverable_failure_threshold_reached": "recoverable_failure_limit"}.get(reason, "none")


def _safe_parameters(action: Mapping[str, Any]) -> Mapping[str, Any] | None:
    payload = action.get("payload")
    if action.get("action_type") != "tool_call" or not isinstance(payload, Mapping):
        return None
    value = payload.get("parameters")
    # Diagnostic traces prove the public action shape, not its raw values.  A
    # type-only projection prevents provider-derived strings or credentials
    # from becoming a persisted diagnostic side channel.
    return ({str(key): type(item).__name__ for key, item in value.items()}
            if isinstance(value, Mapping) else None)


@dataclass
class M18V2BudgetDiagnosticObserver:
    """Passive public event recorder passed to ``dry_run``; it cannot mutate it."""
    case: Any
    comparator_condition_id: str
    trace: list[dict[str, Any]] = field(default_factory=list)
    terminal_reason: str | None = None
    terminal_outcome: str | None = None
    exhaustion_cause: str = "none"
    decoder_failure: bool = False
    decoder_failure_kind: str = "none"
    answer_emitted: bool = False
    first_answer_step: int | None = None
    completion_before_answer: bool | None = None
    last_action_type: str | None = None

    def observe(self, name: str, **value: Any) -> None:
        if name == "interaction":
            action, outcome, state, budget = value["action"], value["outcome"], value["public_state"], value["budget"]
            payload = action.get("payload", {})
            self.last_action_type = action.get("action_type")
            config = self.case.public.to_dict()["task_config"]
            if len(self.trace) >= _TRACE_LIMIT: return
            self.trace.append({"step_index": len(self.trace) + 1, "comparator_condition_id": self.comparator_condition_id,
                "action_type": self.last_action_type, "tool_id": payload.get("tool_name") if isinstance(payload, Mapping) else None,
                "parameters": _safe_parameters(action), "environment_outcome": outcome["category"],
                "public_progress": {"completed_steps": state["completed_steps"], "required_successful_steps": config["required_successful_steps"]},
                "action_cycles_used": budget.action_cycles, "tool_attempts_used": budget.tool_attempts,
                "invalid_actions": budget.invalid_actions, "recoverable_failures": budget.recoverable_failures,
                "logical_provider_calls": budget.logical_provider_calls})
        elif name == "answer":
            action, state, budget = value["action"], value["public_state"], value["budget"]
            config = self.case.public.to_dict()["task_config"]
            self.last_action_type = "answer"; self.answer_emitted = True
            self.first_answer_step = len(self.trace) + 1 if self.first_answer_step is None else self.first_answer_step
            self.completion_before_answer = state["completed_steps"] == config["required_successful_steps"]
            if len(self.trace) >= _TRACE_LIMIT: return
            self.trace.append({"step_index": len(self.trace) + 1, "comparator_condition_id": self.comparator_condition_id,
                "action_type": "answer", "tool_id": None, "parameters": None, "environment_outcome": None,
                "public_progress": {"completed_steps": state["completed_steps"], "required_successful_steps": config["required_successful_steps"]},
                "action_cycles_used": budget.action_cycles, "tool_attempts_used": budget.tool_attempts,
                "invalid_actions": budget.invalid_actions, "recoverable_failures": budget.recoverable_failures,
                "logical_provider_calls": budget.logical_provider_calls})
        elif name == "terminal":
            self.terminal_outcome, self.terminal_reason = value["terminal"], value.get("reason")
            self.exhaustion_cause = value.get("exhaustion_cause", "none")
        elif name == "decoder_failure":
            self.decoder_failure = True
            kind = value["kind"]
            if kind not in _DECODER_FAILURE_KINDS - {"none"}: raise ValueError("unknown decoder failure kind")
            self.decoder_failure_kind = kind


@dataclass(frozen=True)
class M18V2BudgetDiagnosticRecord:
    run_id: str
    condition_id: str
    source_case_id: str
    comparator_condition_id: str
    diagnostic_repetition: int
    source_suite_identity: str
    environment_id: str
    evaluator_id: str
    budget_id: str
    runtime_id: str
    provider_config_hash: str
    execution_baseline: str
    terminal_outcome: str
    terminal_reason: str | None
    exhausted_budget_dimension: str
    telemetry: Mapping[str, Any]
    public_trace: tuple[Mapping[str, Any], ...]
    token_latency_telemetry: Mapping[str, Any]
    integrity_hash: str = ""
    schema_version: str = M18_V2_BUDGET_DIAGNOSTIC_SCHEMA
    non_canonical: bool = True
    diagnostic_only: bool = True
    not_performance_evidence: bool = True

    def __post_init__(self) -> None:
        if self.condition_id != M18_V2_BUDGET_DIAGNOSTIC_CONDITION or self.schema_version != M18_V2_BUDGET_DIAGNOSTIC_SCHEMA:
            raise ValueError("unknown diagnostic condition/schema")
        if self.run_id != derive_diagnostic_run_id(self.source_case_id, self.comparator_condition_id, self.diagnostic_repetition):
            raise ValueError("diagnostic run id mismatch")
        if self.exhausted_budget_dimension not in _DIMENSIONS:
            raise ValueError("unknown exhaustion dimension")
        if set(self.telemetry) != _TELEMETRY_KEYS or set(self.token_latency_telemetry) != _TOKEN_KEYS:
            raise ValueError("diagnostic telemetry schema mismatch")
        integer_keys = {"action_cycles_used", "tool_attempts_used", "invalid_actions", "recoverable_failures", "logical_provider_calls", "transport_attempts"}
        if any(not isinstance(self.telemetry[key], int) or self.telemetry[key] < 0 for key in integer_keys):
            raise ValueError("diagnostic counter schema mismatch")
        if not isinstance(self.telemetry["answer_emitted"], bool) or not isinstance(self.telemetry["decoder_failure"], bool):
            raise ValueError("diagnostic boolean schema mismatch")
        if self.telemetry["last_action_type"] is not None and self.telemetry["last_action_type"] not in _ACTION_TYPES:
            raise ValueError("diagnostic action provenance mismatch")
        if self.telemetry["decoder_failure_kind"] not in _DECODER_FAILURE_KINDS:
            raise ValueError("diagnostic decoder provenance mismatch")
        if self.telemetry["decoder_failure"] != (self.telemetry["decoder_failure_kind"] != "none"):
            raise ValueError("diagnostic decoder provenance inconsistency")
        if self.telemetry["first_answer_step"] is not None and (not isinstance(self.telemetry["first_answer_step"], int) or self.telemetry["first_answer_step"] < 1):
            raise ValueError("diagnostic answer provenance mismatch")
        if self.telemetry["public_completion_before_first_answer"] is not None and not isinstance(self.telemetry["public_completion_before_first_answer"], bool):
            raise ValueError("diagnostic completion provenance mismatch")
        if not isinstance(self.public_trace, tuple) or len(self.public_trace) > _TRACE_LIMIT:
            raise ValueError("diagnostic trace bound violation")
        for index, event in enumerate(self.public_trace, 1):
            if not isinstance(event, Mapping) or event.get("step_index") != index:
                raise ValueError("diagnostic trace step schema mismatch")
            if set(event) != {"step_index", "comparator_condition_id", "action_type", "tool_id", "parameters", "environment_outcome", "public_progress", "action_cycles_used", "tool_attempts_used", "invalid_actions", "recoverable_failures", "logical_provider_calls"}:
                raise ValueError("diagnostic trace schema mismatch")
            if event["action_type"] not in _ACTION_TYPES:
                raise ValueError("diagnostic trace action mismatch")
        if not (self.non_canonical and self.diagnostic_only and self.not_performance_evidence):
            raise ValueError("diagnostic provenance flags are required")
        protected = self._protected_payload()
        expected_integrity_hash = canonical_hash(protected)
        if not self.integrity_hash:
            object.__setattr__(self, "integrity_hash", expected_integrity_hash)
        elif self.integrity_hash != expected_integrity_hash:
            raise ValueError("diagnostic integrity hash mismatch")
        text = canonical_json(self.to_dict())
        for forbidden in ("expected_final_result", "ground_truth", "chain_of_thought", "hidden_reasoning", "api_key", "authorization"):
            if forbidden in text:
                raise ValueError("diagnostic truth/secret firewall violation")

    def _protected_payload(self) -> Mapping[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "integrity_hash"} | {
            "public_trace": [dict(x) for x in self.public_trace],
            "telemetry": dict(self.telemetry),
            "token_latency_telemetry": dict(self.token_latency_telemetry),
        }

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__} | {"public_trace": [dict(x) for x in self.public_trace], "telemetry": dict(self.telemetry), "token_latency_telemetry": dict(self.token_latency_telemetry)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "M18V2BudgetDiagnosticRecord":
        names = set(cls.__dataclass_fields__)
        if not isinstance(value, Mapping) or set(value) != names: raise ValueError("diagnostic record schema mismatch")
        if not isinstance(value.get("integrity_hash"), str) or not value["integrity_hash"]:
            raise ValueError("diagnostic integrity hash required")
        return cls(**{k: (tuple(value[k]) if k == "public_trace" else value[k]) for k in names})


def build_diagnostic_record(case: Any, comparator_condition_id: str, result: M18V2RuntimeResult,
                            observer: M18V2BudgetDiagnosticObserver, repetition: int = 1) -> M18V2BudgetDiagnosticRecord:
    budget = result.budget
    reason = observer.terminal_reason
    return M18V2BudgetDiagnosticRecord(
        derive_diagnostic_run_id(case.case_id, comparator_condition_id, repetition), M18_V2_BUDGET_DIAGNOSTIC_CONDITION,
        case.case_id, comparator_condition_id, repetition, case.suite_version, case.environment_id, case.evaluator_id,
        "m18_budget_v2", M18_V2_RUNTIME_ID, result.run_provenance.provider_config_hash, result.run_provenance.execution_baseline,
        result.terminal.value, reason, getattr(observer, "exhaustion_cause", _dimension(reason)),
        {"action_cycles_used": budget.action_cycles, "tool_attempts_used": budget.tool_attempts,
         "invalid_actions": budget.invalid_actions, "recoverable_failures": budget.recoverable_failures,
         "logical_provider_calls": result.logical_provider_calls, "transport_attempts": result.transport_attempts,
         "answer_emitted": observer.answer_emitted, "first_answer_step": observer.first_answer_step,
         "public_completion_before_first_answer": observer.completion_before_answer,
         "last_action_type": observer.last_action_type, "decoder_failure": observer.decoder_failure,
         "decoder_failure_kind": observer.decoder_failure_kind}, tuple(observer.trace),
        {"prompt_tokens": None, "completion_tokens": None, "cached_tokens": None, "total_tokens": None,
         "run_latency_seconds": None, "provider_call_latency_seconds": None})


def replay_public_completion(public_case: Mapping[str, Any], public_trace: tuple[Mapping[str, Any], ...]) -> Mapping[str, Any]:
    """Offline-only completion analysis from public configuration and trace fields."""
    if not isinstance(public_case, Mapping) or not isinstance(public_trace, tuple):
        raise TypeError("public case and trace are required")
    config = public_case.get("task_config")
    if not isinstance(config, Mapping) or not isinstance(config.get("required_successful_steps"), int):
        raise ValueError("public completion configuration required")
    required = config["required_successful_steps"]; first = None; answer_at = None
    for event in public_trace:
        progress = event.get("public_progress", {}) if isinstance(event, Mapping) else {}
        if first is None and progress.get("completed_steps") == required: first = event.get("step_index")
        if event.get("action_type") == "answer" and answer_at is None: answer_at = event.get("step_index")
    return {"completion_reached": first is not None, "first_completion_step": first,
            "post_completion_actions": 0 if first is None else sum(1 for event in public_trace if event.get("step_index", 0) > first),
            "answer_emitted_by_completion": answer_at is not None and first is not None and answer_at <= first}


class M18V2BudgetDiagnosticPlan:
    def __init__(self, pilot: M18V2PilotPlan) -> None:
        self.pilot = pilot
        self.expected = tuple((case.case_id, condition, 1) for case in pilot.cases for condition in M18_V2_COMPARATOR_CONDITIONS.values())
        self.run_ids = tuple(derive_diagnostic_run_id(*item) for item in self.expected)
        if len(self.expected) != 72 or len(set(self.run_ids)) != 72: raise M18V2PilotIntegrityError("diagnostic universe mismatch")
        if set(self.run_ids) & {item.run_id for item in pilot.expected}: raise M18V2PilotIntegrityError("diagnostic/canonical ID collision")

    @classmethod
    def from_repository(cls, root: Path) -> "M18V2BudgetDiagnosticPlan": return cls(M18V2PilotPlan.from_repository(root))


class M18V2BudgetDiagnosticStore:
    def __init__(self, root: Path, plan: M18V2BudgetDiagnosticPlan) -> None: self.root, self.plan = root, plan
    def _atomic(self, path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as f:
            f.write(canonical_json(dict(value)) + "\n"); f.flush(); os.fsync(f.fileno()); temp = Path(f.name)
        try:
            if path.exists(): raise FileExistsError("diagnostic no-overwrite violation")
            os.replace(temp, path)
        except Exception: temp.unlink(missing_ok=True); raise
    def initialize(self) -> None:
        data={"schema": M18_V2_BUDGET_DIAGNOSTIC_SCHEMA, "condition": M18_V2_BUDGET_DIAGNOSTIC_CONDITION,
              "source_suite_manifest_hash": self.plan.pilot.suite_manifest["manifest_hash"], "expected_run_ids": list(self.plan.run_ids)}
        path=self.root/M18_V2_BUDGET_DIAGNOSTIC_STORE
        if path.exists():
            if json.loads(path.read_text(encoding="utf-8")) != data: raise M18V2PilotIntegrityError("diagnostic store manifest drift")
        else: self._atomic(path,data)
    def records(self) -> tuple[M18V2BudgetDiagnosticRecord,...]:
        if not self.root.exists(): return ()
        out=[]
        for path in sorted(self.root.glob("*.json")):
            if path.name == M18_V2_BUDGET_DIAGNOSTIC_STORE: continue
            record=M18V2BudgetDiagnosticRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
            expected = next((item for item in self.plan.expected if derive_diagnostic_run_id(*item) == record.run_id), None)
            if (path.stem != record.run_id or expected is None or
                (record.source_case_id, record.comparator_condition_id, record.diagnostic_repetition) != expected or
                record.source_suite_identity != self.plan.pilot.suite_manifest["suite_identity"] or
                record.environment_id != self.plan.pilot.suite_manifest["environment_id"] or
                record.evaluator_id != self.plan.pilot.suite_manifest["evaluator_id"] or
                record.budget_id != self.plan.pilot.suite_manifest["budget_id"] or
                record.runtime_id != self.plan.pilot.suite_manifest["runtime_id"] or
                record.provider_config_hash != self.plan.pilot.suite_manifest["provider_config_hash"] or
                record.execution_baseline != self.plan.pilot.expected[0].execution_baseline):
                raise M18V2PilotIntegrityError("diagnostic admission failed")
            out.append(record)
        if len({x.run_id for x in out}) != len(out): raise M18V2PilotIntegrityError("duplicate diagnostic record")
        return tuple(out)
    def persist(self, record: M18V2BudgetDiagnosticRecord) -> M18V2BudgetDiagnosticRecord:
        if record.run_id not in self.plan.run_ids or record.run_id in {x.run_id for x in self.records()}: raise M18V2PilotIntegrityError("unexpected or duplicate diagnostic run")
        self._atomic(self.root/(record.run_id+".json"), record.to_dict())
        return M18V2BudgetDiagnosticRecord.from_dict(json.loads((self.root/(record.run_id+".json")).read_text(encoding="utf-8")))

    def missing(self) -> tuple[tuple[str, str, int], ...]:
        done = {item.run_id for item in self.records()}
        return tuple(item for item in self.plan.expected if derive_diagnostic_run_id(*item) not in done)

    @property
    def systematic_stop_path(self) -> Path: return self.root / M18_V2_BUDGET_DIAGNOSTIC_STOP
    def systematic_stop(self) -> M18V2SystematicProviderStopEvent | None:
        if not self.systematic_stop_path.exists(): return None
        return M18V2SystematicProviderStopEvent.from_dict(json.loads(self.systematic_stop_path.read_text(encoding="utf-8")))
    def persist_systematic_stop(self, event: M18V2SystematicProviderStopEvent) -> None:
        if self.systematic_stop_path.exists():
            if self.systematic_stop() != event: raise M18V2PilotIntegrityError("conflicting diagnostic systematic stop")
            return
        self._atomic(self.systematic_stop_path, event.to_dict())


class M18V2BudgetDiagnosticRunner:
    """Explicit diagnostic executor.  It is never invoked on import or by inspection."""
    def __init__(self, plan: M18V2BudgetDiagnosticPlan, *, result_root: Path | None = None) -> None:
        self.plan = plan
        self.result_root = result_root if result_root is not None else plan.pilot.repository_root / M18_V2_BUDGET_DIAGNOSTIC_NAMESPACE
        self.store = M18V2BudgetDiagnosticStore(self.result_root, plan)

    def execute(self, provider_factory: Callable[[str], Any], *, limit: int | None = None) -> tuple[M18V2BudgetDiagnosticRecord, ...]:
        """Execute only missing diagnostic identities; callers must supply a provider explicitly."""
        self.store.initialize(); completed=[]; by_case=self.plan.pilot.cases_by_id
        prior_stop=self.store.systematic_stop()
        if prior_stop is not None: raise M18V2SystematicProviderStop(prior_stop)
        reverse={value:key for key,value in M18_V2_COMPARATOR_CONDITIONS.items()}
        evidence: dict[tuple[str,str,str],list[str]]={}
        for case_id, condition_id, repetition in self.store.missing()[:limit]:
            system=reverse[condition_id]; providers={name: provider_factory(name) for name in M18_V2_COMPARATOR_CONDITIONS}
            case=by_case[case_id]; condition=M18BenchmarkRuntimeCondition.v2()
            runtime=M18V2SharedExecutionHarness(condition, M18V2ResultProvenance(condition, M18_V2_RUNTIME_ID,
                self.plan.pilot.suite_manifest["provider_config_hash"], condition_id))
            observer=M18V2BudgetDiagnosticObserver(case, condition_id)
            result=runtime.dry_run(case, m18_v2_concrete_adapters(providers)[system], repetition=repetition,
                execution_baseline=self.plan.pilot.expected[0].execution_baseline, diagnostic_observer=observer)
            record=self.store.persist(build_diagnostic_record(case, condition_id, result, observer, repetition)); completed.append(record)
            diagnostic=result.provider_diagnostic
            if diagnostic is not None and diagnostic.is_contract_incompatibility:
                key=(diagnostic.comparator,diagnostic.stage,diagnostic.category); ids=evidence.setdefault(key,[]); ids.append(record.run_id)
                if len(ids)>=2:
                    event=M18V2SystematicProviderStopEvent(diagnostic.comparator,diagnostic.stage,diagnostic.category,tuple(ids),len(ids))
                    self.store.persist_systematic_stop(event); raise M18V2SystematicProviderStop(event)
        return tuple(completed)
