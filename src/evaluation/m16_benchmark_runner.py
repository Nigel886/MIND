"""Evaluation-only M16 execution runner.  It never imports formal fixtures."""
from __future__ import annotations
from dataclasses import dataclass
from time import monotonic
from typing import Callable, Protocol, Any
from src.evaluation.contracts import EvaluationAction, EvaluationActionType, EvaluationFeedback
from src.evaluation.execution import AgentStepInput, EvaluationBudget, EvaluationBudgetState, EnvironmentInteraction
from src.evaluation.m16_benchmark_contracts import M16BaselineID, M16FailureCategory, M16FormalExecutionManifest, M16FormalRunDefinition, M16RunAttemptRecord, counterbalanced_schedule
from src.evaluation.m16_leakage_free import M16ExactCompletionJudge, M16PrivateEvaluationEnvironment, m16_completion_mode
from src.evaluation.m16_diagnostic_telemetry import M16DiagnosticStage, M16DiagnosticTelemetry

class M16StepAgent(Protocol):
    def step(self, step_input: AgentStepInput): ...

@dataclass(frozen=True)
class M16RunActor:
    agent: M16StepAgent
    observations: list[Any]
    telemetry: M16DiagnosticTelemetry | None = None

class M16BenchmarkRunner:
    def __init__(self, manifest: M16FormalExecutionManifest, factories: dict[M16BaselineID, Callable[[], M16RunActor]], clock: Callable[[], float] = monotonic) -> None:
        if set(factories) != set(M16BaselineID): raise ValueError("M16 requires exactly frozen baseline factories")
        self.manifest, self._factories, self._clock = manifest, dict(factories), clock

    def schedule(self, cases: tuple[Any, ...]) -> tuple[M16FormalRunDefinition, ...]:
        return counterbalanced_schedule(self.manifest, tuple(item.case.evaluation_id for item in cases))

    def execute(self, development_case: Any, definition: M16FormalRunDefinition, attempt_number: int = 1) -> M16RunAttemptRecord:
        if development_case.case.evaluation_id != definition.evaluation_id: raise ValueError("case/run mismatch")
        actor = self._factories[definition.baseline_id](); environment=M16PrivateEvaluationEnvironment(development_case.environment); judge=M16ExactCompletionJudge(development_case.private_truth)
        budget=EvaluationBudget(self.manifest.budget_contract.max_agent_steps, self.manifest.budget_contract.max_tool_calls)
        state=EvaluationBudgetState(budget); feedback=environment.reset(development_case.case); interactions=[]; terminal=None; started=self._clock()
        for _ in range(budget.max_steps):
            if self._clock()-started > self.manifest.budget_contract.wall_timeout_seconds:
                terminal=None; break
            result=actor.agent.step(AgentStepInput(development_case.case, feedback, state)); terminal=result.action
            state=EvaluationBudgetState(budget, state.steps_used+1, state.tool_calls_used)
            if result.request_termination: break
            if terminal.action_type is not EvaluationActionType.TOOL_CALL: break
            if state.tool_calls_used >= budget.max_tool_calls: break
            if actor.telemetry is not None: actor.telemetry.emit(M16DiagnosticStage.TOOL_INVOKED, action_type="tool_call", tool_name=terminal.payload.get("tool_name"))
            feedback=environment.apply(terminal,state); interactions.append(EnvironmentInteraction(terminal,feedback))
            state=EvaluationBudgetState(budget, state.steps_used, state.tool_calls_used+1)
            if feedback.feedback_type.value in {"budget","timeout","invalid_action"}: break
        if actor.telemetry is not None: actor.telemetry.emit(M16DiagnosticStage.EVALUATOR_INVOKED)
        outcome=judge.evaluate(development_case.case, tuple(interactions), state, terminal if terminal and terminal.action_type is not EvaluationActionType.TOOL_CALL else None)
        category=self._category(outcome.outcome_type.value, outcome.payload, terminal, state, actor.observations)
        if actor.telemetry is not None:
            actor.telemetry.emit(M16DiagnosticStage.TERMINAL_ADAPTER_ACTION, action_type=terminal.action_type.value if terminal else None, terminal_category=category.value)
            actor.telemetry.emit(M16DiagnosticStage.TERMINAL_REASON, success=category is M16FailureCategory.SUCCESS, terminal_category=category.value)
        return M16RunAttemptRecord("m16-attempt-record-v1",definition.run_id,definition.attempt_id(attempt_number),attempt_number,definition.evaluation_id,definition.baseline_id,definition.repetition,development_case.task_family,development_case.difficulty,development_case.eligibility,m16_completion_mode(development_case.case).value,category is M16FailureCategory.SUCCESS,category,state.steps_used,state.tool_calls_used,provider_request_attempts=sum(getattr(x,"request_attempts",0) for x in actor.observations),model_calls=sum(getattr(x,"model_calls",0) for x in actor.observations),manifest_hash=self.manifest.manifest_hash)

    @staticmethod
    def _category(outcome: str, evidence: Any, terminal: EvaluationAction|None, state: EvaluationBudgetState, observations: list[Any]) -> M16FailureCategory:
        if sum(getattr(x,"request_attempts",0) for x in observations) and not sum(getattr(x,"model_calls",0) for x in observations): return M16FailureCategory.PROVIDER_INFRASTRUCTURE_INVALID_RUN
        if outcome == "success": return M16FailureCategory.SUCCESS
        if outcome == "timeout": return M16FailureCategory.TIMEOUT
        if isinstance(evidence, dict) and evidence.get("failure_category") == "incorrect_answer": return M16FailureCategory.WRONG_ANSWER
        if terminal and terminal.action_type is EvaluationActionType.FAIL: return M16FailureCategory.AGENT_FAIL
        if terminal and terminal.action_type is EvaluationActionType.INVALID: return M16FailureCategory.INVALID_ACTION
        if state.steps_used >= state.budget.max_steps: return M16FailureCategory.STEP_BUDGET_EXHAUSTED
        if state.tool_calls_used >= state.budget.max_tool_calls and terminal and terminal.action_type is EvaluationActionType.TOOL_CALL: return M16FailureCategory.TOOL_BUDGET_EXHAUSTED
        return M16FailureCategory.WRONG_ANSWER
