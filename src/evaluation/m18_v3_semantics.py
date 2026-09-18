"""M18 v3 public-action contract and deterministic environment.

This module is intentionally a new domain.  It reuses the *private* v2 task
semantics as a source fixture, but never changes a v2 identity, transition, or
artifact.  The v3 projection gives an agent precisely the public facts that
the deterministic environment admits for the next action.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from src.evaluation.m18_task_generation import canonical_hash
from src.evaluation.m18_v2_semantics import (
    M18V2Budget, M18V2BudgetError, M18V2BudgetState, M18V2Case,
    M18V2EvaluationCategory, M18V2OutcomeCategory, _config, _transform,
)

M18_V3_SUITE_VERSION = "m18_suite_v3"
M18_V3_ENVIRONMENT_ID = "m18_environment_v3"
M18_V3_EVALUATOR_ID = "m18_evaluator_v3"
M18_V3_BUDGET_ID = "m18_budget_v3"
M18_V3_RUNTIME_ID = "m18_shared_execution_runtime_v3"
M18_V3_PUBLIC_ACTION_CONTRACT_ID = "m18_v3_public_action_contract_v1"

_CONTEXT_KEYS = frozenset({"case_id", "task_text", "state", "current_action", "capabilities", "latest_feedback", "budget"})
# Mechanical audit of every action-admission predicate in ``submit_tool``.
# Values name the only public context field(s) needed to construct a conforming
# action.  The environment's private transformation and target are absent.
M18_V3_PUBLIC_VALIDATION_MAPPING = {
    "unsupported_public_action": (),
    "interaction_already_complete": ("state.completed_steps", "current_action"),
    "unknown_stable_tool_id": ("capabilities.tool_id",),
    "tool_not_currently_available": ("current_action.tool_id", "capabilities.available"),
    "parameter_schema_violation": ("current_action.parameter_schema",),
    "parameter_value_not_current_public_state": ("current_action.parameters", "state.current_value"),
}


@dataclass(frozen=True)
class M18V3Budget:
    """Frozen v3 budget identity; numeric limits intentionally match v2."""
    identity: str = M18_V3_BUDGET_ID
    max_action_cycles: int = 6
    max_tool_attempts: int = 4
    invalid_action_threshold: int = 2
    recoverable_failure_threshold: int = 2
    max_logical_provider_calls: int = 8
    def __post_init__(self) -> None:
        if self.__dict__ != {"identity": M18_V3_BUDGET_ID, "max_action_cycles": 6, "max_tool_attempts": 4, "invalid_action_threshold": 2, "recoverable_failure_threshold": 2, "max_logical_provider_calls": 8}:
            raise ValueError("m18_budget_v3 is immutable")
    def to_dict(self) -> dict[str, Any]: return dict(self.__dict__)


@dataclass(frozen=True)
class M18V3BudgetState:
    action_cycles: int = 0
    tool_attempts: int = 0
    invalid_actions: int = 0
    recoverable_failures: int = 0
    logical_provider_calls: int = 0
    def consume_action(self, tool_attempt: bool = False) -> "M18V3BudgetState":
        budget = M18V3Budget()
        if self.action_cycles >= budget.max_action_cycles: raise M18V2BudgetError("action_cycle_limit")
        if tool_attempt and self.tool_attempts >= budget.max_tool_attempts: raise M18V2BudgetError("tool_attempt_limit")
        return M18V3BudgetState(self.action_cycles + 1, self.tool_attempts + int(tool_attempt), self.invalid_actions, self.recoverable_failures, self.logical_provider_calls)
    def record_outcome(self, category: M18V2OutcomeCategory) -> tuple["M18V3BudgetState", str | None]:
        invalid = self.invalid_actions + int(category is M18V2OutcomeCategory.INVALID_ACTION); recovery = self.recoverable_failures + int(category is M18V2OutcomeCategory.RECOVERABLE_FAILURE)
        state = M18V3BudgetState(self.action_cycles, self.tool_attempts, invalid, recovery, self.logical_provider_calls)
        budget = M18V3Budget()
        return state, "invalid_action_threshold_reached" if invalid >= budget.invalid_action_threshold else ("recoverable_failure_threshold_reached" if recovery >= budget.recoverable_failure_threshold else None)
    def record_logical_provider_call(self) -> "M18V3BudgetState":
        if self.logical_provider_calls >= M18V3Budget().max_logical_provider_calls: raise M18V2BudgetError("logical_provider_call_limit")
        return M18V3BudgetState(self.action_cycles, self.tool_attempts, self.invalid_actions, self.recoverable_failures, self.logical_provider_calls + 1)
    def to_dict(self) -> dict[str, int]: return dict(self.__dict__)


def _json(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool, float)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    raise TypeError("public action context must be JSON-compatible")


@dataclass(frozen=True)
class M18V3Case:
    """A v3 identity around immutable private benchmark semantics."""
    source: M18V2Case
    suite_version: str = M18_V3_SUITE_VERSION
    environment_id: str = M18_V3_ENVIRONMENT_ID
    evaluator_id: str = M18_V3_EVALUATOR_ID

    def __post_init__(self) -> None:
        if not isinstance(self.source, M18V2Case):
            raise TypeError("source must be an M18V2Case")
        if (self.suite_version, self.environment_id, self.evaluator_id) != (M18_V3_SUITE_VERSION, M18_V3_ENVIRONMENT_ID, M18_V3_EVALUATOR_ID):
            raise ValueError("M18 v3 identities are closed")

    @property
    def case_id(self) -> str: return self.source.case_id
    @property
    def cohort(self): return self.source.cohort
    @property
    def difficulty(self): return self.source.difficulty
    @property
    def failure_subtype(self): return self.source.failure_subtype
    @property
    def task_text(self) -> str: return self.source.public.task_text

    def to_dict(self) -> dict[str, Any]:
        return {"case_id": self.case_id, "suite_version": self.suite_version,
                "environment_id": self.environment_id, "evaluator_id": self.evaluator_id,
                "source_case_hash": canonical_hash(self.source.to_dict())}


@dataclass(frozen=True)
class M18V3CurrentAction:
    """The one currently legal public tool operation; no future route leaks."""
    tool_id: str
    parameters: Mapping[str, Any]
    parameter_schema: Mapping[str, Any]
    available: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.tool_id, str) or not self.tool_id:
            raise ValueError("current stable tool_id is required")
        object.__setattr__(self, "parameters", _json(self.parameters))
        object.__setattr__(self, "parameter_schema", _json(self.parameter_schema))

    def to_dict(self) -> dict[str, Any]:
        return {"tool_id": self.tool_id, "parameters": _json(self.parameters),
                "parameter_schema": _json(self.parameter_schema), "available": self.available}


@dataclass(frozen=True)
class M18V3PublicActionContext:
    """Closed policy-visible context for exactly one v3 action cycle."""
    case_id: str
    task_text: str
    state: Mapping[str, Any]
    current_action: M18V3CurrentAction | None
    capabilities: tuple[Mapping[str, Any], ...]
    latest_feedback: Mapping[str, Any] | None
    budget: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.case_id, str) or not self.case_id or not isinstance(self.task_text, str):
            raise ValueError("case identity and task text are required")
        if not isinstance(self.capabilities, tuple):
            raise TypeError("capabilities must be an ordered tuple")
        object.__setattr__(self, "state", _json(self.state))
        object.__setattr__(self, "capabilities", tuple(_json(item) for item in self.capabilities))
        object.__setattr__(self, "latest_feedback", None if self.latest_feedback is None else _json(self.latest_feedback))
        object.__setattr__(self, "budget", _json(self.budget))

    def to_dict(self) -> dict[str, Any]:
        result = {"case_id": self.case_id, "task_text": self.task_text, "state": _json(self.state),
                  "current_action": self.current_action.to_dict() if self.current_action else None,
                  "capabilities": [_json(item) for item in self.capabilities],
                  "latest_feedback": None if self.latest_feedback is None else _json(self.latest_feedback),
                  "budget": _json(self.budget)}
        assert frozenset(result) == _CONTEXT_KEYS
        return result


@dataclass(frozen=True)
class M18V3EnvironmentOutcome:
    category: M18V2OutcomeCategory
    payload: Mapping[str, Any]
    state: Mapping[str, Any]
    def to_dict(self) -> dict[str, Any]:
        return {"category": self.category.value, "payload": _json(self.payload), "state": _json(self.state)}


def _public_capabilities(case: M18V3Case, current_tool: str | None) -> tuple[Mapping[str, Any], ...]:
    result = []
    for item in case.source.public.to_dict()["capabilities"]:
        # A capability not executable now is not provider-visible.  This is
        # stronger than an availability flag: it prevents future ordered tool
        # identifiers and their parameter contracts crossing the boundary.
        if item["tool_id"] == current_tool:
            result.append({"tool_id": item["tool_id"], "display_name": item["display_name"],
                           "description": item["description"], "parameter_schema": item["parameter_schema"],
                           "available": True})
    return tuple(result)


def _parameter_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {"value": {"type": "integer"}},
            "required": ["value"], "additionalProperties": False}


@dataclass
class M18V3Episode:
    """Private v3 episode state; only :meth:`public_context` crosses policy boundary."""
    case: M18V3Case
    budget_state: M18V3BudgetState = field(default_factory=M18V3BudgetState)
    public_state: dict[str, Any] = field(init=False)
    terminal_reason: str | None = None
    latest_feedback: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        config = _config(self.case.source)
        self.public_state = {"current_value": config["initial_value"], "completed_steps": 0, "failure_consumed": False}

    def public_context(self) -> M18V3PublicActionContext:
        config = _config(self.case.source)
        completed = self.public_state["completed_steps"]
        step = config["steps"][completed] if completed < config["required_successful_steps"] else None
        current = None if step is None else M18V3CurrentAction(step["tool_id"], {"value": self.public_state["current_value"]}, _parameter_schema())
        return M18V3PublicActionContext(self.case.case_id, self.case.task_text,
            {"current_value": self.public_state["current_value"], "completed_steps": completed,
             "required_successful_steps": config["required_successful_steps"]}, current,
            _public_capabilities(self.case, None if step is None else step["tool_id"]), self.latest_feedback,
            {"max_action_cycles": 6, "max_tool_attempts": 4, "action_cycles_used": self.budget_state.action_cycles,
             "tool_attempts_used": self.budget_state.tool_attempts, "remaining_action_cycles": 6-self.budget_state.action_cycles,
             "remaining_tool_attempts": 4-self.budget_state.tool_attempts})

    def submit_tool(self, action: Mapping[str, Any]) -> M18V3EnvironmentOutcome:
        if self.terminal_reason: raise M18V2BudgetError("episode_terminated")
        try: self.budget_state = self.budget_state.consume_action(True)
        except M18V2BudgetError as error:
            self.terminal_reason = str(error); return M18V3EnvironmentOutcome(M18V2OutcomeCategory.BUDGET_EXHAUSTED, {"reason": str(error)}, dict(self.public_state))
        config = _config(self.case.source); state = dict(self.public_state); completed = state["completed_steps"]
        if action.get("action") != "tool_call": outcome = M18V3EnvironmentOutcome(M18V2OutcomeCategory.INVALID_ACTION, {"reason": "unsupported_public_action"}, state)
        elif completed >= config["required_successful_steps"]: outcome = M18V3EnvironmentOutcome(M18V2OutcomeCategory.INVALID_ACTION, {"reason": "interaction_already_complete"}, state)
        else:
            schedule = config["failure_schedule"]
            if schedule is not None and not state["failure_consumed"] and completed == schedule["after_successful_steps"]:
                state["failure_consumed"] = True
                category = M18V2OutcomeCategory.RECOVERABLE_FAILURE if schedule["subtype"] == "recoverable" else M18V2OutcomeCategory.INVALID_ACTION
                outcome = M18V3EnvironmentOutcome(category, {"reason": schedule["subtype"], "retry_permitted": True}, state)
            else:
                step = config["steps"][completed]; name = action.get("tool_name"); params = action.get("parameters")
                if name not in {item["tool_id"] for item in config["steps"]}: reason = "unknown_stable_tool_id"
                elif name != step["tool_id"]: reason = "tool_not_currently_available"
                elif not isinstance(params, Mapping) or set(params) != {"value"} or not isinstance(params.get("value"), int) or isinstance(params.get("value"), bool): reason = "parameter_schema_violation"
                elif params["value"] != state["current_value"]: reason = "parameter_value_not_current_public_state"
                else:
                    value = _transform(state["current_value"], step["transformation_id"])
                    state = {"current_value": value, "completed_steps": completed + 1, "failure_consumed": state["failure_consumed"]}
                    outcome = M18V3EnvironmentOutcome(M18V2OutcomeCategory.SUCCESS, {"public_value": value, "completed_steps": completed+1}, state)
                    self.public_state = state; self.budget_state, stop = self.budget_state.record_outcome(outcome.category); self.terminal_reason = stop or self.terminal_reason
                    self.latest_feedback = outcome.to_dict(); return outcome
                outcome = M18V3EnvironmentOutcome(M18V2OutcomeCategory.INVALID_ACTION, {"reason": reason}, state)
        self.public_state = dict(outcome.state); self.budget_state, stop = self.budget_state.record_outcome(outcome.category); self.terminal_reason = stop or self.terminal_reason; self.latest_feedback = outcome.to_dict(); return outcome

    def submit_answer(self, candidate: Any) -> M18V2EvaluationCategory:
        if not self.terminal_reason:
            try: self.budget_state = self.budget_state.consume_action()
            except M18V2BudgetError as error: self.terminal_reason = str(error)
        if self.terminal_reason: return M18V2EvaluationCategory.BUDGET_EXHAUSTED
        if not isinstance(candidate, int) or isinstance(candidate, bool): return M18V2EvaluationCategory.MALFORMED_ANSWER
        if self.public_state["completed_steps"] != _config(self.case.source)["required_successful_steps"]: return M18V2EvaluationCategory.INTERACTION_INCOMPLETE
        return M18V2EvaluationCategory.SUCCESS if candidate == self.case.source.evaluator.expected_final_result else M18V2EvaluationCategory.WRONG_ANSWER
