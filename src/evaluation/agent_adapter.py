"""Evaluation-only, step-wise adapter for the delivered MIND Agent components."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from src.core.completion import CompletionEvaluator
from src.core.goal_policy import GoalAwarePolicyEngine
from src.core.meta_engine import MetaInferenceEngine
from src.core.meta_inference import MetaInferenceDecisionStatus
from src.core.observation import Observation
from src.core.runtime import RuntimeController, RuntimeState
from src.core.task import Task
from src.evaluation.contracts import (
    EvaluationAction,
    EvaluationActionType,
    EvaluationCase,
    EvaluationFeedback,
    EvaluationFeedbackType,
)
from src.evaluation.execution import AgentStepInput, AgentStepResult


def _task_observation(task: Task) -> Observation:
    """Create the existing Agent-compatible initial observation privately."""

    data = task.to_dict()
    return Observation(
        source="task",
        content={
            "task_id": str(task.id),
            "goal": task.goal.to_dict(),
            "input": data["input"],
            "context": data["context"],
            "constraints": data["constraints"],
        },
    )


def _feedback_observation(feedback: EvaluationFeedback) -> Observation:
    """Convert public feedback into a fresh, internal immutable Observation."""

    return Observation(
        source="evaluation_environment",
        content=feedback.to_dict(),
    )


def _failure(reason: str) -> AgentStepResult:
    return AgentStepResult(
        EvaluationAction(EvaluationActionType.FAIL, {"reason": reason}),
        True,
    )


def _invalid(reason: str) -> AgentStepResult:
    return AgentStepResult(
        EvaluationAction(EvaluationActionType.INVALID, {"reason": reason}),
        True,
    )


class _MINDGoalDirectedEvaluationSession:
    """Private session retaining MIND core state across evaluation steps only."""

    def __init__(
        self,
        task: Task,
        runtime_state: RuntimeState,
        meta_inference_engine: MetaInferenceEngine | None,
    ) -> None:
        self._task = task
        self._runtime_state = runtime_state
        self._meta_inference_engine = meta_inference_engine
        self._awaiting_feedback = False
        self._terminal: AgentStepResult | None = None

    @classmethod
    def start(
        cls,
        task: Task,
        meta_inference_engine: MetaInferenceEngine | None,
    ) -> "_MINDGoalDirectedEvaluationSession":
        """Initialize the private state in the same order as Agent.run()."""

        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        if meta_inference_engine is not None and not isinstance(
            meta_inference_engine,
            MetaInferenceEngine,
        ):
            raise TypeError("meta_inference_engine must be a MetaInferenceEngine or None")
        initial = _task_observation(task)
        state = RuntimeController.initialize(observation=initial)
        state = RuntimeController.apply_inference(state, initial)
        session = cls(task, state, meta_inference_engine)
        if meta_inference_engine is not None:
            decision = meta_inference_engine.select(task, state)
            if decision.status is not MetaInferenceDecisionStatus.SELECTED:
                session._terminal = _failure(
                    f"meta_inference_{decision.status.value}",
                )
        return session

    def next_decision(self) -> AgentStepResult:
        """Expose one public action without exposing Policy or runtime state."""

        if self._terminal is not None:
            return self._terminal
        if self._awaiting_feedback:
            return _invalid("feedback_required_before_next_decision")

        policy = GoalAwarePolicyEngine.generate(self._task, self._runtime_state)
        if policy.action == "produce_answer":
            self._terminal = AgentStepResult(
                EvaluationAction(
                    EvaluationActionType.ANSWER,
                    {"answer": deepcopy(policy.parameters.get("answer"))},
                ),
                True,
            )
            return self._terminal
        if policy.action == "fail_task":
            self._terminal = _failure(str(policy.parameters.get("reason", "policy_failure")))
            return self._terminal
        if policy.action == "call_tool":
            tool_name = policy.parameters.get("tool_name")
            parameters = policy.parameters.get("tool_parameters")
            if not isinstance(tool_name, str) or not isinstance(parameters, dict):
                self._terminal = _invalid("invalid_tool_policy")
                return self._terminal
            self._awaiting_feedback = True
            return AgentStepResult(
                EvaluationAction(
                    EvaluationActionType.TOOL_CALL,
                    {"tool_name": tool_name, "parameters": deepcopy(parameters)},
                ),
                False,
            )
        self._terminal = _invalid("unsupported_policy_action")
        return self._terminal

    def accept_observation(self, observation: Observation) -> None:
        """Incorporate an adapter-created environment Observation privately."""

        if not isinstance(observation, Observation):
            raise TypeError("observation must be an Observation")
        if self._terminal is not None:
            raise RuntimeError("session is already terminal")
        if not self._awaiting_feedback:
            raise RuntimeError("session is not awaiting environment feedback")
        self._runtime_state = RuntimeController.apply_inference(
            self._runtime_state,
            observation,
        )
        self._awaiting_feedback = False
        self._terminal = self._tool_feedback_terminal(observation)

    def _tool_feedback_terminal(self, observation: Observation) -> AgentStepResult:
        """Mirror M8's post-tool answer hand-off without returning AgentResult."""

        content = observation.content
        candidate_answer: Any = None
        if isinstance(content, Mapping):
            payload = content.get("payload")
            if isinstance(payload, Mapping):
                response = payload.get("response")
                if isinstance(response, Mapping) and "output" in response:
                    candidate_answer = deepcopy(response["output"])
        CompletionEvaluator.evaluate(self._task, self._runtime_state, candidate_answer)
        return AgentStepResult(
            EvaluationAction(EvaluationActionType.ANSWER, {"answer": candidate_answer}),
            True,
        )


class MINDGoalDirectedEvaluationAdapter:
    """Translate M14 public inputs into private MIND session transitions."""

    def __init__(self, meta_inference_engine: MetaInferenceEngine | None = None) -> None:
        if meta_inference_engine is not None and not isinstance(
            meta_inference_engine,
            MetaInferenceEngine,
        ):
            raise TypeError("meta_inference_engine must be a MetaInferenceEngine or None")
        self._meta_inference_engine = meta_inference_engine
        self._session: _MINDGoalDirectedEvaluationSession | None = None
        self._evaluation_id: str | None = None
        self._terminated = False

    def step(self, step_input: AgentStepInput) -> AgentStepResult:
        """Return one public action for an initial or environment-feedback step."""

        if not isinstance(step_input, AgentStepInput):
            raise TypeError("step_input must be an AgentStepInput")
        if self._terminated:
            return _invalid("adapter_already_terminated")
        if self._session is None:
            if step_input.previous_feedback.feedback_type is not EvaluationFeedbackType.INITIAL_INPUT:
                return _invalid("initial_feedback_required")
            self._session = _MINDGoalDirectedEvaluationSession.start(
                step_input.case.task,
                self._meta_inference_engine,
            )
            self._evaluation_id = step_input.case.evaluation_id
            result = self._session.next_decision()
            self._terminated = result.request_termination
            return result

        if step_input.case.evaluation_id != self._evaluation_id:
            return _invalid("evaluation_case_mismatch")
        feedback = step_input.previous_feedback
        if feedback.feedback_type is EvaluationFeedbackType.TOOL_RESPONSE:
            try:
                self._session.accept_observation(_feedback_observation(feedback))
            except RuntimeError:
                return _invalid("unexpected_tool_response")
            result = self._session.next_decision()
            self._terminated = result.request_termination
            return result
        if feedback.feedback_type is EvaluationFeedbackType.TOOL_FAILURE:
            self._terminated = True
            return _failure("tool_failure")
        if feedback.feedback_type is EvaluationFeedbackType.INVALID_ACTION:
            self._terminated = True
            return _invalid("invalid_action")
        if feedback.feedback_type is EvaluationFeedbackType.BUDGET:
            self._terminated = True
            return _failure("budget_exhausted")
        if feedback.feedback_type is EvaluationFeedbackType.TIMEOUT:
            self._terminated = True
            return _failure("timeout")
        return _invalid("unexpected_initial_feedback")
