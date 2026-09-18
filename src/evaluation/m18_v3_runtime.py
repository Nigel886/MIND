"""Provider-free execution binding for the corrected M18 v3 public contract.

No production provider is constructed here.  Callers inject the same provider
interfaces used by the comparator implementations, which makes contract tests
both deterministic and representative of their real request/decoder paths.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

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
from src.evaluation.m18_v2_runtime import _GatedGenerateProvider, _GatedPlanProvider
from src.evaluation.m18_v2_semantics import M18V2BudgetError, M18V2OutcomeCategory
from src.evaluation.m18_v3_semantics import M18V3BudgetState, M18V3Case, M18V3Episode, M18_V3_RUNTIME_ID

M18_V3_SYSTEMS = ("mind_lite_v11", "direct_tool_calling", "react", "plan_and_execute")


class M18V3ProviderCallGate:
    """V3 logical-call accounting; transport attempts stay observational."""
    def __init__(self, budget_state: M18V3BudgetState) -> None:
        self._state = budget_state; self.transport_attempts = 0
    @property
    def budget_state(self) -> M18V3BudgetState: return self._state
    def invoke(self, operation, *, transport_attempts: int = 1):
        if not isinstance(transport_attempts, int) or transport_attempts < 1: raise ValueError("transport_attempts must be positive")
        self._state = self._state.record_logical_provider_call(); self.transport_attempts += transport_attempts
        return operation()


def _caps(episode: M18V3Episode) -> tuple[CapabilityDescriptor, ...]:
    """Build descriptors from the typed public projection, never the fixture."""
    return tuple(CapabilityDescriptor(item["tool_id"], item["display_name"], item["description"], item["parameter_schema"])
                 for item in episode.public_context().to_dict()["capabilities"])


def _task(case: M18V3Case, episode: M18V3Episode) -> Task:
    return Task(Goal(case.task_text, ("choose exactly one public action",)),
                {"m18_v3_public_action_context": episode.public_context().to_dict()})


def _step_input(case: M18V3Case, episode: M18V3Episode, feedback: EvaluationFeedback) -> AgentStepInput:
    state = episode.budget_state
    return AgentStepInput(EvaluationCase(case.case_id, _task(case, episode)), feedback,
                          EvaluationBudgetState(EvaluationBudget(6, 4), state.action_cycles, state.tool_attempts))


def _feedback(outcome) -> EvaluationFeedback:
    mapping = {M18V2OutcomeCategory.SUCCESS: EvaluationFeedbackType.TOOL_RESPONSE,
               M18V2OutcomeCategory.RECOVERABLE_FAILURE: EvaluationFeedbackType.TOOL_FAILURE,
               M18V2OutcomeCategory.INVALID_ACTION: EvaluationFeedbackType.INVALID_ACTION,
               M18V2OutcomeCategory.BUDGET_EXHAUSTED: EvaluationFeedbackType.BUDGET}
    payload = dict(outcome.payload)
    if outcome.category is M18V2OutcomeCategory.RECOVERABLE_FAILURE: payload["category"] = "recoverable_failure"
    return EvaluationFeedback(mapping[outcome.category], payload)


class M18V3MINDAdapter:
    system_condition = "mind_lite_v11"
    def __init__(self, provider: Any) -> None:
        self._provider = _GatedGenerateProvider(provider, self.system_condition, "mind_policy")
        self._condition = M18MINDPolicyCondition(self._provider); self._session = None; self._case = None
    def initialize(self, case: M18V3Case, episode: M18V3Episode) -> None:
        self._case = case; self._session = CognitiveAgentSession(6, policy_engine=self._condition, capabilities=_caps(episode)); self._session.start(_task(case, episode))
    def next_decision(self, feedback: EvaluationFeedback, episode: M18V3Episode, gate: M18V3ProviderCallGate) -> EvaluationAction:
        self._provider.gate = gate
        # CognitiveAgentSession retains its task for the lifetime of a normal
        # session.  In this evaluation-only bridge, that task is the active
        # provider-facing projection, so replace it before policy invocation.
        # Public feedback remains in ``latest_observation`` as history; it is
        # deliberately not encoded as a second action context.
        self._session._task = _task(self._case, episode)
        self._session._capabilities = _caps(episode)
        try: result = self._session.step()
        except Exception as error:
            if self._provider.last_failure is not None: raise self._provider.last_failure from error
            raise
        if result.phase is not CognitiveSessionPhase.AWAITING_OBSERVATION or result.action_request is None: raise RuntimeError("MIND session terminated before public action")
        request = result.action_request
        return EvaluationAction(EvaluationActionType.ANSWER, {"answer": request.parameters["answer"]}) if request.action == "answer" else EvaluationAction(EvaluationActionType.TOOL_CALL, {"tool_name": request.parameters["tool_name"], "parameters": request.parameters["parameters"]})
    def accept_observation(self, feedback: EvaluationFeedback, episode: M18V3Episode) -> None:
        category = EnvironmentOutcomeCategory.SUCCESS if feedback.feedback_type is EvaluationFeedbackType.TOOL_RESPONSE else (EnvironmentOutcomeCategory.RECOVERABLE_FAILURE if feedback.feedback_type is EvaluationFeedbackType.TOOL_FAILURE else EnvironmentOutcomeCategory.INVALID_ACTION)
        reason = EnvironmentOutcomeReason.SUCCESSFUL_RESULT if category is EnvironmentOutcomeCategory.SUCCESS else (EnvironmentOutcomeReason.TOOL_TRANSIENT_FAILURE if category is EnvironmentOutcomeCategory.RECOVERABLE_FAILURE else EnvironmentOutcomeReason.INVALID_ARGUMENTS)
        # This is historical public feedback, not a second executable-context
        # channel.  The next decision receives its sole active context via the
        # replacement task installed in ``next_decision``.
        payload = {"feedback": feedback.to_dict()}
        self._session.observe(EnvironmentOutcome(category, reason, payload).to_observation())
    @property
    def last_request(self): return self._provider.last_request


class _DecisionAdapter:
    baseline_type: Any
    system_condition: str
    stage: str
    def __init__(self, provider: Any) -> None:
        self._provider = _GatedGenerateProvider(provider, self.system_condition, self.stage); self._baseline = None; self._case = None
    def initialize(self, case: M18V3Case, episode: M18V3Episode) -> None:
        self._case = case; self._baseline = self.baseline_type(self._provider, _caps(episode))
    def next_decision(self, feedback: EvaluationFeedback, episode: M18V3Episode, gate: M18V3ProviderCallGate) -> EvaluationAction:
        self._provider.gate = gate
        self._baseline._capabilities = _caps(episode)
        try: return self._baseline.step(_step_input(self._case, episode, feedback)).action
        except Exception as error:
            if self._provider.last_failure is not None: raise self._provider.last_failure from error
            raise
    @property
    def last_request(self): return self._provider.last_request


class M18V3DirectAdapter(_DecisionAdapter):
    system_condition="direct_tool_calling"; stage="direct_decision"; baseline_type=M18DirectToolCallingBaseline
class M18V3ReActAdapter(_DecisionAdapter):
    system_condition="react"; stage="react_decision"; baseline_type=M18ReActBaseline


class M18V3PlanAdapter:
    system_condition = "plan_and_execute"
    def __init__(self, provider: Any) -> None:
        self._provider = _GatedPlanProvider(provider, self.system_condition); self._baseline = None; self._case = None
    def initialize(self, case: M18V3Case, episode: M18V3Episode) -> None:
        self._case = case; self._baseline = M18PlanAndExecuteBaseline(self._provider, _caps(episode))
    def next_decision(self, feedback: EvaluationFeedback, episode: M18V3Episode, gate: M18V3ProviderCallGate) -> EvaluationAction:
        self._provider.gate = gate
        self._baseline._capabilities = _caps(episode)
        self._provider.stage = "plan_planner" if self._baseline.plan is None else ("plan_replan" if feedback.feedback_type in {EvaluationFeedbackType.INVALID_ACTION, EvaluationFeedbackType.TOOL_FAILURE} else "plan_executor")
        try: return self._baseline.step(_step_input(self._case, episode, feedback)).action
        except Exception as error:
            if self._provider.last_failure is not None: raise self._provider.last_failure from error
            raise
    @property
    def last_requests(self): return self._provider.last_plan_request, self._provider.last_executor_request


@dataclass(frozen=True)
class M18V3RuntimeResult:
    actions: tuple[dict[str, Any], ...]
    feedback: tuple[dict[str, Any], ...]
    terminal: str
    evaluator_outcome: str | None
    final_public_state: Mapping[str, Any]
    logical_provider_calls: int
    transport_attempts: int


class M18V3SharedExecutionHarness:
    identity = M18_V3_RUNTIME_ID
    def dry_run(self, case: M18V3Case, adapter: Any) -> M18V3RuntimeResult:
        if not isinstance(case, M18V3Case) or adapter.system_condition not in M18_V3_SYSTEMS: raise ValueError("v3 case and comparator adapter required")
        episode = M18V3Episode(case); feedback = EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT); gate = M18V3ProviderCallGate(episode.budget_state)
        actions: list[dict[str, Any]]=[]; feedbacks: list[dict[str, Any]]=[]; terminal="budget_exhausted"; evaluation=None
        adapter.initialize(case, episode)
        while not episode.terminal_reason:
            try: action = adapter.next_decision(feedback, episode, gate)
            except M18V2BudgetError: break
            episode.budget_state = M18V3BudgetState(episode.budget_state.action_cycles, episode.budget_state.tool_attempts, episode.budget_state.invalid_actions, episode.budget_state.recoverable_failures, gate.budget_state.logical_provider_calls)
            actions.append(action.to_dict())
            if action.action_type is EvaluationActionType.ANSWER:
                evaluation = episode.submit_answer(action.to_dict()["payload"].get("answer")); terminal="answer_submitted"; break
            if action.action_type is EvaluationActionType.FAIL:
                terminal = "agent_failure"; break
            if action.action_type is EvaluationActionType.TOOL_CALL:
                raw = action.to_dict()["payload"]; outcome = episode.submit_tool({"action":"tool_call", "tool_name":raw["tool_name"], "parameters":raw["parameters"]})
            else:
                outcome = episode.submit_tool({"action":"invalid"})
            feedback = _feedback(outcome); feedbacks.append(feedback.to_dict())
            accept = getattr(adapter, "accept_observation", None)
            if callable(accept): accept(feedback, episode)
        return M18V3RuntimeResult(tuple(actions), tuple(feedbacks), terminal, evaluation.value if evaluation else None, dict(episode.public_state), gate.budget_state.logical_provider_calls, gate.transport_attempts)


def m18_v3_concrete_adapters(providers: Mapping[str, Any]) -> dict[str, Any]:
    if set(providers) != set(M18_V3_SYSTEMS): raise ValueError("all four v3 comparator providers are required")
    return {"mind_lite_v11": M18V3MINDAdapter(providers["mind_lite_v11"]), "direct_tool_calling": M18V3DirectAdapter(providers["direct_tool_calling"]), "react": M18V3ReActAdapter(providers["react"]), "plan_and_execute": M18V3PlanAdapter(providers["plan_and_execute"])}
