"""Explicit, provider-free shared runtime binding for future M18 v2 execution.

The historical v1 shared harness is intentionally not altered.  This module is
an explicit v2 condition: it uses the already-audited environment, evaluator,
and budget implementation rather than duplicating any semantic transition.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping, Protocol

from src.core.cognitive_session import CognitiveAgentSession, CognitiveSessionPhase
from src.core.environment_outcome import EnvironmentOutcome, EnvironmentOutcomeCategory, EnvironmentOutcomeReason
from src.core.task import Goal, Task
from src.core.tool import CapabilityDescriptor
from src.evaluation.contracts import EvaluationAction, EvaluationActionType, EvaluationCase, EvaluationFeedback, EvaluationFeedbackType
from src.evaluation.execution import AgentStepInput, EvaluationBudget, EvaluationBudgetState
from src.evaluation.m18_direct_tool_calling import M18DirectToolCallingBaseline
from src.evaluation.m18_mind_policy_condition import M18MINDPolicyCondition
from src.evaluation.m18_plan_and_execute import M18PlanAndExecuteBaseline
from src.evaluation.m18_react import M18ReActBaseline
from src.evaluation.m18_task_generation import canonical_hash
from src.evaluation.m18_v2_semantics import (
    M18V2Budget, M18V2BudgetError, M18V2BudgetState, M18V2Case,
    M18V2Episode, M18V2EvaluationCategory, M18V2EnvironmentOutcome,
    M18V2OutcomeCategory, M18_V2_BUDGET_ID, M18_V2_ENVIRONMENT_ID,
    M18_V2_EVALUATOR_ID, M18_V2_SUITE_VERSION,
)


M18_V1_RUNTIME_CONDITION = "m18_runtime_condition_v1_historical"
M18_V2_RUNTIME_CONDITION = "m18_runtime_condition_v2"
M18_V1_BUDGET_ID = "m18_budget_v1_historical_3_1"
M18_V2_RUNTIME_ID = "m18_shared_execution_runtime_v2"
M18_V2_SYSTEMS = ("mind_lite_v11", "direct_tool_calling", "react", "plan_and_execute")


@dataclass(frozen=True)
class M18BenchmarkRuntimeCondition:
    """All semantic identities must travel together; mixed conditions fail closed."""

    condition_id: str
    suite_version: str
    environment_id: str
    evaluator_id: str
    budget_id: str

    def __post_init__(self) -> None:
        allowed = {
            M18_V1_RUNTIME_CONDITION: ("m18_suite_v1", "m18_environment_v1", "m18_evaluator_v1", M18_V1_BUDGET_ID),
            M18_V2_RUNTIME_CONDITION: (M18_V2_SUITE_VERSION, M18_V2_ENVIRONMENT_ID, M18_V2_EVALUATOR_ID, M18_V2_BUDGET_ID),
        }
        if self.condition_id not in allowed or (self.suite_version, self.environment_id, self.evaluator_id, self.budget_id) != allowed[self.condition_id]:
            raise ValueError("mixed or unknown M18 benchmark runtime condition")

    @classmethod
    def v1(cls) -> "M18BenchmarkRuntimeCondition":
        return cls(M18_V1_RUNTIME_CONDITION, "m18_suite_v1", "m18_environment_v1", "m18_evaluator_v1", M18_V1_BUDGET_ID)

    @classmethod
    def v2(cls) -> "M18BenchmarkRuntimeCondition":
        return cls(M18_V2_RUNTIME_CONDITION, M18_V2_SUITE_VERSION, M18_V2_ENVIRONMENT_ID, M18_V2_EVALUATOR_ID, M18_V2_BUDGET_ID)

    def to_dict(self) -> dict[str, str]:
        return self.__dict__.copy()


class M18V2RuntimeTerminal(str, Enum):
    ANSWER_SUBMITTED = "answer_submitted"
    BUDGET_EXHAUSTED = "budget_exhausted"
    TIMEOUT = "timeout"
    AGENT_FAILURE = "agent_failure"


class M18V2ProviderCallGate:
    """The sole logical-call gate for all v2 adapters.

    Transport attempt count is observational and deliberately cannot consume a
    logical call slot more than once.
    """

    def __init__(self, budget_state: M18V2BudgetState) -> None:
        self._logical_provider_calls = budget_state.logical_provider_calls
        self.transport_attempts = 0

    @property
    def budget_state(self) -> M18V2BudgetState:
        return M18V2BudgetState(logical_provider_calls=self._logical_provider_calls)

    def invoke(self, operation: Callable[[], Any], *, transport_attempts: int = 1) -> Any:
        if not isinstance(transport_attempts, int) or transport_attempts < 1:
            raise ValueError("transport_attempts must be a positive integer")
        self._logical_provider_calls = self.budget_state.record_logical_provider_call().logical_provider_calls
        self.transport_attempts += transport_attempts
        return operation()


class M18V2RuntimeAdapter(Protocol):
    system_condition: str
    def initialize(self, case: M18V2Case) -> None: ...
    def next_decision(self, feedback: EvaluationFeedback, budget: M18V2BudgetState,
                      provider_gate: M18V2ProviderCallGate) -> EvaluationAction: ...


def _feedback(outcome: M18V2EnvironmentOutcome) -> EvaluationFeedback:
    payload = dict(outcome.to_dict()["payload"])
    mapping = {
        M18V2OutcomeCategory.SUCCESS: EvaluationFeedbackType.TOOL_RESPONSE,
        M18V2OutcomeCategory.RECOVERABLE_FAILURE: EvaluationFeedbackType.TOOL_FAILURE,
        M18V2OutcomeCategory.INVALID_ACTION: EvaluationFeedbackType.INVALID_ACTION,
        M18V2OutcomeCategory.BUDGET_EXHAUSTED: EvaluationFeedbackType.BUDGET,
        M18V2OutcomeCategory.TIMEOUT: EvaluationFeedbackType.TIMEOUT,
    }
    if outcome.category is M18V2OutcomeCategory.RECOVERABLE_FAILURE:
        payload["category"] = "recoverable_failure"
    return EvaluationFeedback(mapping[outcome.category], payload)


def _tool_action(action: EvaluationAction) -> dict[str, Any]:
    payload = action.to_dict()["payload"]
    return {"action": "tool_call", "tool_name": payload["tool_name"], "parameters": payload["parameters"]}


@dataclass(frozen=True)
class M18V2ResultProvenance:
    """Required semantic identities for future v2 records; no persistence here."""

    condition: M18BenchmarkRuntimeCondition
    execution_harness_id: str
    provider_config_hash: str
    comparator_condition_id: str

    def __post_init__(self) -> None:
        if self.condition.condition_id != M18_V2_RUNTIME_CONDITION:
            raise ValueError("v2 result provenance requires the v2 condition")
        if self.execution_harness_id != M18_V2_RUNTIME_ID:
            raise ValueError("unknown v2 runtime identity")
        if not isinstance(self.provider_config_hash, str) or len(self.provider_config_hash) != 64:
            raise ValueError("provider config hash must be SHA-256")
        if not isinstance(self.comparator_condition_id, str) or not self.comparator_condition_id:
            raise ValueError("comparator condition identity required")

    def to_dict(self) -> dict[str, Any]:
        return {"condition": self.condition.to_dict(), "execution_harness_id": self.execution_harness_id,
                "provider_config_hash": self.provider_config_hash,
                "comparator_condition_id": self.comparator_condition_id}

    @property
    def provenance_hash(self) -> str:
        return canonical_hash(self.to_dict())


@dataclass(frozen=True)
class M18V2RuntimeResult:
    terminal: M18V2RuntimeTerminal
    evaluator_outcome: M18V2EvaluationCategory | None
    actions: tuple[dict[str, Any], ...]
    feedback: tuple[dict[str, Any], ...]
    environment_outcomes: tuple[dict[str, Any], ...]
    final_public_state: dict[str, Any]
    budget: M18V2BudgetState
    logical_provider_calls: int
    transport_attempts: int
    provenance: M18V2ResultProvenance

    def to_dict(self) -> dict[str, Any]:
        return {"terminal": self.terminal.value,
                "evaluator_outcome": self.evaluator_outcome.value if self.evaluator_outcome else None,
                "actions": list(self.actions), "feedback": list(self.feedback),
                "environment_outcomes": list(self.environment_outcomes),
                "final_public_state": dict(self.final_public_state), "budget": self.budget.to_dict(),
                "logical_provider_calls": self.logical_provider_calls,
                "transport_attempts": self.transport_attempts, "provenance": self.provenance.to_dict()}


class M18V2SharedExecutionHarness:
    """The explicit v2 runtime for future adapters and suite-freeze checks."""

    identity = M18_V2_RUNTIME_ID

    def __init__(self, condition: M18BenchmarkRuntimeCondition, provenance: M18V2ResultProvenance) -> None:
        if condition != M18BenchmarkRuntimeCondition.v2() or provenance.condition != condition:
            raise ValueError("M18 v2 shared runtime requires the complete v2 condition")
        self.condition, self.provenance, self.budget = condition, provenance, M18V2Budget()

    def dry_run(self, case: M18V2Case, adapter: M18V2RuntimeAdapter, *, elapsed_seconds: int | float = 0) -> M18V2RuntimeResult:
        """Execute an injected fake/public adapter without persistence or real providers."""
        if not isinstance(case, M18V2Case) or case.suite_version != self.condition.suite_version:
            raise ValueError("case does not match explicit v2 runtime condition")
        if adapter.system_condition not in M18_V2_SYSTEMS:
            raise ValueError("unknown M18 v2 system condition")
        episode = M18V2Episode(case)
        episode.enforce_elapsed_seconds(elapsed_seconds)
        gate = M18V2ProviderCallGate(episode.budget_state)
        actions: list[dict[str, Any]] = []
        feedbacks: list[dict[str, Any]] = []
        outcomes: list[dict[str, Any]] = []
        feedback = EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)
        adapter.initialize(case)
        terminal: M18V2RuntimeTerminal | None = None
        evaluation: M18V2EvaluationCategory | None = None
        while terminal is None:
            if episode.terminal_reason == "timeout":
                terminal = M18V2RuntimeTerminal.TIMEOUT
                evaluation = episode.submit_answer(None)
                break
            try:
                action = adapter.next_decision(feedback, episode.budget_state, gate)
            except M18V2BudgetError:
                terminal = M18V2RuntimeTerminal.BUDGET_EXHAUSTED
                break
            # Provider calls are counted at the call boundary but are a distinct
            # dimension from public action/tool counters.
            episode.budget_state = M18V2BudgetState(
                episode.budget_state.action_cycles, episode.budget_state.tool_attempts,
                episode.budget_state.invalid_actions, episode.budget_state.recoverable_failures,
                gate.budget_state.logical_provider_calls,
            )
            if not isinstance(action, EvaluationAction):
                terminal = M18V2RuntimeTerminal.AGENT_FAILURE
                break
            actions.append(action.to_dict())
            if action.action_type is EvaluationActionType.ANSWER:
                evaluation = episode.submit_answer(action.to_dict()["payload"].get("answer"))
                terminal = M18V2RuntimeTerminal.ANSWER_SUBMITTED if evaluation is not M18V2EvaluationCategory.BUDGET_EXHAUSTED else M18V2RuntimeTerminal.BUDGET_EXHAUSTED
                break
            if action.action_type is EvaluationActionType.TOOL_CALL:
                outcome = episode.submit_tool(_tool_action(action))
            else:
                outcome = episode.submit_invalid_action()
            outcomes.append(outcome.to_dict())
            feedback = _feedback(outcome); feedbacks.append(feedback.to_dict())
            accept = getattr(adapter, "accept_observation", None)
            if callable(accept):
                accept(feedback)
            if episode.terminal_reason:
                terminal = M18V2RuntimeTerminal.TIMEOUT if episode.terminal_reason == "timeout" else M18V2RuntimeTerminal.BUDGET_EXHAUSTED
            elif outcome.category is M18V2OutcomeCategory.BUDGET_EXHAUSTED:
                terminal = M18V2RuntimeTerminal.BUDGET_EXHAUSTED
        return M18V2RuntimeResult(terminal, evaluation, tuple(actions), tuple(feedbacks), tuple(outcomes),
                                  dict(episode.public_state), episode.budget_state,
                                  gate.budget_state.logical_provider_calls, gate.transport_attempts, self.provenance)


# Concrete comparator adapters -------------------------------------------------
# These are deliberately evaluation-side wrappers.  They retain each baseline's
# request/decoder/state implementation and only interpose the v2 call gate.

def _capabilities(case: M18V2Case) -> tuple[CapabilityDescriptor, ...]:
    return tuple(CapabilityDescriptor(item["tool_id"], item["display_name"], item["description"], item["parameter_schema"])
                 for item in case.public.to_dict()["capabilities"])


def _step_input(case: M18V2Case, feedback: EvaluationFeedback, budget: M18V2BudgetState) -> AgentStepInput:
    task = Task(Goal(case.public.task_text, ("act using public capability information",)), {"task_text": case.public.task_text})
    return AgentStepInput(EvaluationCase(case.case_id, task), feedback,
                          EvaluationBudgetState(EvaluationBudget(6, 4), budget.action_cycles, budget.tool_attempts))


class _GatedGenerateProvider:
    def __init__(self, provider: Any) -> None:
        self.provider, self.gate, self.last_request = provider, None, None
    def generate(self, request: Any) -> str:
        if self.gate is None: raise RuntimeError("v2 provider gate not bound")
        self.last_request = request
        attempts = getattr(self.provider, "transport_attempts_per_logical_call", 1)
        return self.gate.invoke(lambda: self.provider.generate(request), transport_attempts=attempts)


class _GatedPlanProvider:
    def __init__(self, provider: Any) -> None:
        self.provider, self.gate, self.last_plan_request, self.last_executor_request = provider, None, None, None
    def plan(self, request: Any) -> str:
        if self.gate is None: raise RuntimeError("v2 provider gate not bound")
        self.last_plan_request = request
        attempts = getattr(self.provider, "transport_attempts_per_logical_call", 1)
        return self.gate.invoke(lambda: self.provider.plan(request), transport_attempts=attempts)
    def execute(self, request: Any) -> str:
        if self.gate is None: raise RuntimeError("v2 provider gate not bound")
        self.last_executor_request = request
        attempts = getattr(self.provider, "transport_attempts_per_logical_call", 1)
        return self.gate.invoke(lambda: self.provider.execute(request), transport_attempts=attempts)


class M18V2MINDAdapter:
    system_condition = "mind_lite_v11"
    def __init__(self, provider: Any) -> None:
        self._provider = _GatedGenerateProvider(provider); self._condition = M18MINDPolicyCondition(self._provider); self._session = None
    def initialize(self, case: M18V2Case) -> None:
        task = Task(Goal(case.public.task_text, ("choose a public action",)), {"task_text": case.public.task_text})
        self._session = CognitiveAgentSession(6, policy_engine=self._condition, capabilities=_capabilities(case)); self._session.start(task)
    def next_decision(self, feedback: EvaluationFeedback, budget: M18V2BudgetState, provider_gate: M18V2ProviderCallGate) -> EvaluationAction:
        self._provider.gate = provider_gate
        assert self._session is not None
        result = self._session.step()
        if result.phase is not CognitiveSessionPhase.AWAITING_OBSERVATION or result.action_request is None: raise RuntimeError("MIND session terminated before public action")
        request = result.action_request
        if request.action == "answer": return EvaluationAction(EvaluationActionType.ANSWER, {"answer": request.parameters["answer"]})
        return EvaluationAction(EvaluationActionType.TOOL_CALL, {"tool_name": request.parameters["tool_name"], "parameters": request.parameters["parameters"]})
    def accept_observation(self, feedback: EvaluationFeedback) -> None:
        assert self._session is not None
        payload = feedback.to_dict()["payload"]
        if feedback.feedback_type is EvaluationFeedbackType.TOOL_RESPONSE: outcome = EnvironmentOutcome(EnvironmentOutcomeCategory.SUCCESS, EnvironmentOutcomeReason.SUCCESSFUL_RESULT, payload)
        elif feedback.feedback_type is EvaluationFeedbackType.TOOL_FAILURE: outcome = EnvironmentOutcome(EnvironmentOutcomeCategory.RECOVERABLE_FAILURE, EnvironmentOutcomeReason.TOOL_TRANSIENT_FAILURE, {k:v for k,v in payload.items() if k != "category"})
        else: outcome = EnvironmentOutcome(EnvironmentOutcomeCategory.INVALID_ACTION, EnvironmentOutcomeReason.INVALID_ARGUMENTS, payload)
        self._session.observe(outcome.to_observation())
    @property
    def last_request(self): return self._provider.last_request


class M18V2DirectAdapter:
    system_condition = "direct_tool_calling"
    def __init__(self, provider: Any) -> None: self._provider = _GatedGenerateProvider(provider); self._baseline = None; self._case = None
    def initialize(self, case: M18V2Case) -> None: self._case = case; self._baseline = M18DirectToolCallingBaseline(self._provider, _capabilities(case))
    def next_decision(self, feedback: EvaluationFeedback, budget: M18V2BudgetState, provider_gate: M18V2ProviderCallGate) -> EvaluationAction:
        self._provider.gate = provider_gate; assert self._baseline is not None and self._case is not None
        return self._baseline.step(_step_input(self._case, feedback, budget)).action
    @property
    def last_request(self): return self._provider.last_request


class M18V2ReActAdapter:
    system_condition = "react"
    def __init__(self, provider: Any) -> None: self._provider = _GatedGenerateProvider(provider); self._baseline = None; self._case = None
    def initialize(self, case: M18V2Case) -> None: self._case = case; self._baseline = M18ReActBaseline(self._provider, _capabilities(case))
    def next_decision(self, feedback: EvaluationFeedback, budget: M18V2BudgetState, provider_gate: M18V2ProviderCallGate) -> EvaluationAction:
        self._provider.gate = provider_gate; assert self._baseline is not None and self._case is not None
        return self._baseline.step(_step_input(self._case, feedback, budget)).action
    @property
    def last_request(self): return self._provider.last_request


class M18V2PlanAdapter:
    system_condition = "plan_and_execute"
    def __init__(self, provider: Any) -> None: self._provider = _GatedPlanProvider(provider); self._baseline = None; self._case = None
    def initialize(self, case: M18V2Case) -> None: self._case = case; self._baseline = M18PlanAndExecuteBaseline(self._provider, _capabilities(case))
    def next_decision(self, feedback: EvaluationFeedback, budget: M18V2BudgetState, provider_gate: M18V2ProviderCallGate) -> EvaluationAction:
        self._provider.gate = provider_gate; assert self._baseline is not None and self._case is not None
        return self._baseline.step(_step_input(self._case, feedback, budget)).action
    @property
    def last_requests(self): return self._provider.last_plan_request, self._provider.last_executor_request


def m18_v2_concrete_adapters(providers: Mapping[str, Any]) -> dict[str, M18V2RuntimeAdapter]:
    """Explicitly construct all four concrete v2 adapters; no v1 fallback."""
    if set(providers) != set(M18_V2_SYSTEMS): raise ValueError("all four v2 comparator providers are required")
    return {"mind_lite_v11": M18V2MINDAdapter(providers["mind_lite_v11"]),
            "direct_tool_calling": M18V2DirectAdapter(providers["direct_tool_calling"]),
            "react": M18V2ReActAdapter(providers["react"]),
            "plan_and_execute": M18V2PlanAdapter(providers["plan_and_execute"])}
