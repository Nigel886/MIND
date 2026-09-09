"""M16-only bridge that admits the public task before legacy projection."""
from __future__ import annotations
from src.core.cognitive_session import CognitiveAgentSession, CognitiveSessionPhase, CognitiveSessionTerminationReason
from src.core.observation import Observation
from src.evaluation.contracts import EvaluationAction, EvaluationActionType
from src.evaluation.execution import AgentStepInput, AgentStepResult
from src.evaluation.m16_leakage_free import project_m16_legacy_task
from src.integration.meta_inference_adapter import IntegrationSelected

class M16MINDSessionEvaluationAdapter:
    """One fresh session per case; M13 sees only the original public Task."""
    def __init__(self, admission_resolver, max_cycles: int = 2) -> None:
        if not callable(admission_resolver): raise TypeError("admission_resolver must be callable")
        self._resolver, self._max_cycles, self._session = admission_resolver, max_cycles, None
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
            self._session=CognitiveAgentSession(max_cycles=self._max_cycles)
            if not admitted or not isinstance(admitted[0], IntegrationSelected):
                return AgentStepResult(EvaluationAction(EvaluationActionType.FAIL,{"reason":"m13_admission_failed"}),True)
            self._session.start(projected, validated_context=admitted[0])
            return self._project(self._session.step())
        feedback=step_input.previous_feedback.to_dict()
        # The session convention consumes compact environment payloads. Preserve
        # the public feedback type while exposing a calculator output only here.
        payload = feedback.get("payload", {})
        if feedback.get("feedback_type") == "tool_response" and isinstance(payload, dict):
            response = payload.get("response")
            if isinstance(response, dict) and "output" in response:
                feedback = {"output": response["output"], "feedback_type": "tool_response"}
        self._session.observe(Observation(source="agent_environment", content=feedback))
        return self._project(self._session.step())

    @staticmethod
    def _project(result) -> AgentStepResult:
        if result.phase is CognitiveSessionPhase.TERMINATED:
            if result.termination_reason is CognitiveSessionTerminationReason.COMPLETED:
                return AgentStepResult(EvaluationAction(EvaluationActionType.ANSWER,{"answer":result.answer}),True)
            return AgentStepResult(EvaluationAction(EvaluationActionType.FAIL,{"reason":result.termination_reason.value}),True)
        request=result.action_request
        parameters = request.to_dict()["parameters"]
        if request.action == "answer": return AgentStepResult(EvaluationAction(EvaluationActionType.ANSWER,parameters),True)
        return AgentStepResult(EvaluationAction(EvaluationActionType.TOOL_CALL,parameters),False)
