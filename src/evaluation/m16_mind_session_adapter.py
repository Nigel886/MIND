"""M16-only bridge that admits the public task before legacy projection."""
from __future__ import annotations
from src.core.cognitive_session import CognitiveAgentSession, CognitiveSessionPhase, CognitiveSessionTerminationReason
from src.core.observation import Observation
from src.evaluation.contracts import EvaluationAction, EvaluationActionType
from src.evaluation.execution import AgentStepInput, AgentStepResult
from src.evaluation.m16_leakage_free import project_m16_legacy_task
from src.integration.meta_inference_adapter import IntegrationSelected
from src.evaluation.m16_diagnostic_telemetry import M16DiagnosticReason, M16DiagnosticStage, M16DiagnosticTelemetry

class M16MINDSessionEvaluationAdapter:
    """One fresh session per case; M13 sees only the original public Task."""
    def __init__(self, admission_resolver, max_cycles: int = 2, *, telemetry: M16DiagnosticTelemetry | None = None) -> None:
        if not callable(admission_resolver): raise TypeError("admission_resolver must be callable")
        if telemetry is not None and not isinstance(telemetry, M16DiagnosticTelemetry): raise TypeError("telemetry must be M16DiagnosticTelemetry or None")
        self._resolver, self._max_cycles, self._session, self._telemetry = admission_resolver, max_cycles, None, telemetry
        self._case_id = None

    def step(self, step_input: AgentStepInput) -> AgentStepResult:
        if self._session is None:
            self._case_id = step_input.case.evaluation_id
            # Session invokes resolver before this adapter performs the private projection.
            admitted = []
            def capture(task, runtime_state):
                result = self._resolver(task, runtime_state)
                admitted.append(result)
                return result
            admission_session=CognitiveAgentSession(max_cycles=self._max_cycles)
            admission_session.start(step_input.case.task, admission_resolver=capture)
            # Resolution succeeded: run the private frozen compatibility session only now.
            projected=project_m16_legacy_task(step_input.case.task)
            self._emit(M16DiagnosticStage.PRIVATE_TASK_PROJECTED, success=True)
            self._session=CognitiveAgentSession(max_cycles=self._max_cycles)
            if not admitted or not isinstance(admitted[0], IntegrationSelected):
                self._emit(M16DiagnosticStage.ADMISSION_FAILED, success=False, normalized_reason=M16DiagnosticReason.ADMISSION_FAILURE)
                self._emit(M16DiagnosticStage.TERMINAL_ADAPTER_ACTION, action_type="fail", terminal_category="agent_fail")
                return AgentStepResult(EvaluationAction(EvaluationActionType.FAIL,{"reason":"m13_admission_failed"}),True)
            self._session.start(projected, validated_context=admitted[0])
            self._emit(M16DiagnosticStage.INTEGRATION_SELECTED, success=True, selected_strategy=admitted[0].decision.selected_strategy)
            self._emit(M16DiagnosticStage.PRIVATE_SESSION_CREATED, success=True, session_phase=self._session.phase.value)
            self._emit(M16DiagnosticStage.POLICY_INVOKED)
            return self._project(self._session.step(), self._telemetry)
        feedback=step_input.previous_feedback.to_dict()
        # The session convention consumes compact environment payloads. Preserve
        # the public feedback type while exposing a calculator output only here.
        payload = feedback.get("payload", {})
        if feedback.get("feedback_type") == "tool_response" and isinstance(payload, dict):
            response = payload.get("response")
            if isinstance(response, dict) and "output" in response:
                feedback = {"output": response["output"], "feedback_type": "tool_response"}
        self._session.observe(Observation(source="agent_environment", content=feedback))
        self._emit(M16DiagnosticStage.POLICY_INVOKED)
        return self._project(self._session.step(), self._telemetry)

    @staticmethod
    def _project(self, result=None) -> AgentStepResult:
        """Project a session result, retaining legacy private-call compatibility."""
        # `self` is the result for pre-telemetry private callers; normal calls
        # pass `(result, telemetry)` through the two-argument form below.
        telemetry = result if isinstance(result, M16DiagnosticTelemetry) else None
        if result is None or isinstance(result, M16DiagnosticTelemetry):
            result = self
        def emit(stage, **data):
            if telemetry is not None: telemetry.emit(stage, **data)
        if result.phase is CognitiveSessionPhase.TERMINATED:
            emit(M16DiagnosticStage.PRIVATE_SESSION_TERMINATED, success=result.termination_reason is CognitiveSessionTerminationReason.COMPLETED, normalized_reason=None if result.termination_reason is CognitiveSessionTerminationReason.COMPLETED else M16DiagnosticReason.PRIVATE_SESSION_FAILURE, session_phase=result.phase.value)
            if result.termination_reason is CognitiveSessionTerminationReason.COMPLETED:
                action=AgentStepResult(EvaluationAction(EvaluationActionType.ANSWER,{"answer":result.answer}),True)
            else: action=AgentStepResult(EvaluationAction(EvaluationActionType.FAIL,{"reason":result.termination_reason.value}),True)
            emit(M16DiagnosticStage.TERMINAL_ADAPTER_ACTION, action_type=action.action.action_type.value, terminal_category="agent_fail" if action.action.action_type is EvaluationActionType.FAIL else None)
            emit(M16DiagnosticStage.TERMINAL_REASON, normalized_reason=None if action.action.action_type is not EvaluationActionType.FAIL else M16DiagnosticReason.PRIVATE_SESSION_FAILURE)
            return action
        request=result.action_request
        parameters = request.to_dict()["parameters"]
        emit(M16DiagnosticStage.POLICY_ACTION_CREATED, action_type=request.action)
        if request.action == "answer":
            emit(M16DiagnosticStage.PROJECTED_ANSWER_ACTION, action_type="answer")
            action=AgentStepResult(EvaluationAction(EvaluationActionType.ANSWER,parameters),True)
        else:
            emit(M16DiagnosticStage.PROJECTED_TOOL_ACTION, action_type="tool_call", tool_name=parameters.get("tool_name"))
            action=AgentStepResult(EvaluationAction(EvaluationActionType.TOOL_CALL,parameters),False)
        emit(M16DiagnosticStage.TERMINAL_ADAPTER_ACTION, action_type=action.action.action_type.value, terminal_category=None if action.action.action_type is EvaluationActionType.TOOL_CALL else "pending_evaluator")
        return action

    def _emit(self, stage: M16DiagnosticStage, **data) -> None:
        if self._telemetry is not None: self._telemetry.emit(stage, **data)
