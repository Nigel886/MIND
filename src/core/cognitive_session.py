"""Controlled, observation-aware cognitive session runtime for MIND-Lite.

This module provides a public step boundary around existing MIND components.
It publishes action requests derived from Policies, but it never executes tools
or providers.  External execution returns a public Observation that is accepted
through :meth:`CognitiveAgentSession.observe` for the next cognitive cycle.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Callable, Mapping, TypeAlias

from src.core.cognitive_execution import CognitiveExecutionLoopController
from src.core.meta_engine import MetaInferenceEngine
from src.core.meta_inference import MetaInferenceDecisionStatus
from src.core.observation import Observation
from src.core.policy import Policy
from src.core.runtime import RuntimeController, RuntimeState
from src.core.task import Task
from src.integration.meta_inference_adapter import IntegrationSelected


class CognitiveSessionPhase(str, Enum):
    """Public lifecycle phases of one cognitive session."""

    READY = "ready"
    AWAITING_OBSERVATION = "awaiting_observation"
    TERMINATED = "terminated"


class CognitiveSessionTerminationReason(str, Enum):
    """The frozen M15 public session termination reasons."""

    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    USER_STOPPED = "user_stopped"
    MAX_CYCLES_REACHED = "max_cycles_reached"


_FORBIDDEN_FEEDBACK_KEYS = frozenset(
    {
        "chain_of_thought",
        "hidden_reasoning",
        "private_prompt",
        "credentials",
        "api_key",
    },
)

_AdmissionResolver: TypeAlias = Callable[[Task, RuntimeState], object]


def _freeze_json(value: Any) -> Any:
    """Validate JSON-compatible data and recursively detach mutable values."""

    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("JSON float values must be finite")
        return value
    if isinstance(value, dict):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON mapping keys must be strings")
            if key in _FORBIDDEN_FEEDBACK_KEYS:
                raise ValueError(f"feedback contains forbidden key: {key}")
            frozen[key] = _freeze_json(item)
        return MappingProxyType(frozen)
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    raise TypeError("value must be JSON-compatible")


def _thaw_json(value: Any) -> Any:
    """Return fresh ordinary JSON-compatible containers."""

    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return deepcopy(value)


def _freeze_evidence(value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise TypeError("evidence must be an ordered sequence of dictionaries")
    records: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise TypeError("each evidence item must be a dictionary")
        records.append(_freeze_json(item))
    return tuple(records)


@dataclass(frozen=True)
class CognitiveActionRequest:
    """Immutable public execution request projected from an existing Policy."""

    action: str
    parameters: dict[str, Any]

    def __post_init__(self) -> None:
        if self.action not in {"answer", "tool_call"}:
            raise ValueError("action must be 'answer' or 'tool_call'")
        if not isinstance(self.parameters, dict):
            raise TypeError("parameters must be a dict")
        frozen = _freeze_json(self.parameters)
        if self.action == "answer" and set(frozen) != {"answer"}:
            raise ValueError("answer requests require only an answer parameter")
        if self.action == "tool_call":
            if set(frozen) != {"tool_name", "parameters"}:
                raise ValueError("tool_call requests require tool_name and parameters")
            if not isinstance(frozen["tool_name"], str) or not frozen["tool_name"].strip():
                raise ValueError("tool_name must be a non-empty string")
            if not isinstance(frozen["parameters"], Mapping):
                raise TypeError("tool_call parameters must be a dictionary")
        object.__setattr__(self, "parameters", frozen)

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "parameters": _thaw_json(self.parameters)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CognitiveActionRequest":
        if not isinstance(data, dict):
            raise TypeError("CognitiveActionRequest data must be a dict")
        return cls(action=data["action"], parameters=data["parameters"])


@dataclass(frozen=True)
class CognitiveSessionStepResult:
    """Immutable public result of one session transition.

    RuntimeState, Belief, Policy, task internals, and feedback history remain
    private to :class:`CognitiveAgentSession`.
    """

    phase: CognitiveSessionPhase
    action_request: CognitiveActionRequest | None = None
    termination_reason: CognitiveSessionTerminationReason | None = None
    answer: Any | None = None
    evidence: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.phase, CognitiveSessionPhase):
            raise TypeError("phase must be a CognitiveSessionPhase")
        if self.action_request is not None and not isinstance(
            self.action_request,
            CognitiveActionRequest,
        ):
            raise TypeError("action_request must be a CognitiveActionRequest or None")
        if self.termination_reason is not None and not isinstance(
            self.termination_reason,
            CognitiveSessionTerminationReason,
        ):
            raise TypeError("termination_reason must be a CognitiveSessionTerminationReason or None")
        if self.phase is CognitiveSessionPhase.AWAITING_OBSERVATION:
            if self.action_request is None or self.termination_reason is not None:
                raise ValueError("awaiting-observation steps require exactly one action request")
        elif self.phase is CognitiveSessionPhase.TERMINATED:
            if self.action_request is not None or self.termination_reason is None:
                raise ValueError("terminated steps require exactly one termination reason")
        else:
            raise ValueError("public step results cannot use the ready phase")
        if self.termination_reason is not CognitiveSessionTerminationReason.COMPLETED and self.answer is not None:
            raise ValueError("only completed steps may contain an answer")
        object.__setattr__(self, "answer", _freeze_json(self.answer))
        object.__setattr__(self, "evidence", _freeze_evidence(self.evidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase.value,
            "action_request": (
                self.action_request.to_dict() if self.action_request is not None else None
            ),
            "termination_reason": (
                self.termination_reason.value if self.termination_reason is not None else None
            ),
            "answer": _thaw_json(self.answer),
            "evidence": _thaw_json(self.evidence),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CognitiveSessionStepResult":
        if not isinstance(data, dict):
            raise TypeError("CognitiveSessionStepResult data must be a dict")
        try:
            phase = CognitiveSessionPhase(data["phase"])
            reason_data = data["termination_reason"]
            reason = (
                CognitiveSessionTerminationReason(reason_data)
                if reason_data is not None
                else None
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid cognitive session step result") from error
        request_data = data.get("action_request")
        request = (
            CognitiveActionRequest.from_dict(request_data)
            if request_data is not None
            else None
        )
        return cls(
            phase=phase,
            action_request=request,
            termination_reason=reason,
            answer=data.get("answer"),
            evidence=data.get("evidence", ()),
        )


def _task_observation(task: Task) -> Observation:
    """Construct the existing Agent-compatible initial Observation privately."""

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


class CognitiveAgentSession:
    """A controlled, multi-cycle session over existing immutable MIND state.

    This class deliberately owns mutable lifecycle coordination only. Each
    RuntimeController transition returns a new private immutable RuntimeState;
    callers receive only immutable action and terminal result models.
    """

    def __init__(
        self,
        max_cycles: int,
        *,
        meta_inference_engine: MetaInferenceEngine | None = None,
    ) -> None:
        if isinstance(max_cycles, bool) or not isinstance(max_cycles, int):
            raise TypeError("max_cycles must be an int, not bool")
        if max_cycles < 0:
            raise ValueError("max_cycles must not be negative")
        if meta_inference_engine is not None and not isinstance(
            meta_inference_engine,
            MetaInferenceEngine,
        ):
            raise TypeError("meta_inference_engine must be a MetaInferenceEngine or None")
        self._max_cycles = max_cycles
        self._meta_inference_engine = meta_inference_engine
        self._started = False
        self._phase = CognitiveSessionPhase.READY
        self._task: Task | None = None
        self._runtime_state: RuntimeState | None = None
        self._cycles_completed = 0
        self._pending_observation: Observation | None = None
        self._pending_feedback: Mapping[str, Any] | None = None
        self._pending_start_failure: tuple[dict[str, Any], ...] | None = None
        self._validated_context: IntegrationSelected | None = None
        self._terminal_result: CognitiveSessionStepResult | None = None

    @property
    def phase(self) -> CognitiveSessionPhase:
        """Return the lifecycle phase without exposing cognitive state."""

        return self._phase

    @property
    def cycles_completed(self) -> int:
        """Return the deterministic count of published action requests."""

        return self._cycles_completed

    def start(
        self,
        task: Task,
        *,
        validated_context: IntegrationSelected | None = None,
        admission_resolver: _AdmissionResolver | None = None,
    ) -> None:
        """Initialize a single session using existing public runtime interfaces."""

        if self._started:
            raise RuntimeError("session has already been started")
        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        if validated_context is not None and not isinstance(
            validated_context,
            IntegrationSelected,
        ):
            raise TypeError("validated_context must be an IntegrationSelected or None")
        if validated_context is not None and self._meta_inference_engine is not None:
            raise ValueError("validated_context and meta_inference_engine are mutually exclusive")
        if admission_resolver is not None and not callable(admission_resolver):
            raise TypeError("admission_resolver must be callable or None")
        if admission_resolver is not None and (
            validated_context is not None or self._meta_inference_engine is not None
        ):
            raise ValueError(
                "admission_resolver, validated_context, and meta_inference_engine are mutually exclusive",
            )

        initial = _task_observation(task)
        self._task = task
        self._runtime_state = RuntimeController.initialize(observation=initial)
        self._runtime_state = RuntimeController.apply_inference(self._runtime_state, initial)
        self._started = True

        if validated_context is not None:
            self._validated_context = validated_context
            return
        if admission_resolver is not None:
            admission = admission_resolver(task, self._runtime_state)
            if isinstance(admission, IntegrationSelected):
                self._validated_context = admission
            else:
                self._pending_start_failure = (
                    {"type": "m13_admission", "outcome": "failed"},
                )
            return
        if self._meta_inference_engine is not None:
            decision = self._meta_inference_engine.select(task, self._runtime_state)
            if decision.status is not MetaInferenceDecisionStatus.SELECTED:
                self._pending_start_failure = (
                    {"type": "meta_inference", "status": decision.status.value},
                )

    def step(self) -> CognitiveSessionStepResult:
        """Publish one Policy-derived action request or deterministically terminate."""

        self._require_started()
        self._require_not_terminated()
        if self._phase is CognitiveSessionPhase.AWAITING_OBSERVATION:
            raise RuntimeError("observation feedback is required before the next step")
        if self._pending_start_failure is not None:
            failure = self._pending_start_failure
            self._pending_start_failure = None
            return self._finish(CognitiveSessionTerminationReason.FAILED, failure)

        assert self._task is not None
        assert self._runtime_state is not None
        if self._pending_observation is not None:
            transition = CognitiveExecutionLoopController.advance(
                self._task,
                self._runtime_state,
                self._pending_observation,
                self._pending_feedback,
                request_policy=self._cycles_completed < self._max_cycles,
            )
            self._pending_observation = None
            self._pending_feedback = None
            self._runtime_state = transition.runtime_state
            if transition.failure_category is not None:
                return self._finish(
                    CognitiveSessionTerminationReason.FAILED,
                    ({"type": "environment_feedback", "category": transition.failure_category},),
                )
            if transition.completed_answer is not None:
                return self._finish(
                    CognitiveSessionTerminationReason.COMPLETED,
                    ({"type": "completion", "satisfied": True},),
                    transition.completed_answer,
                )
            if transition.policy is None:
                return self._finish(CognitiveSessionTerminationReason.MAX_CYCLES_REACHED)
        else:
            if self._cycles_completed >= self._max_cycles:
                return self._finish(CognitiveSessionTerminationReason.MAX_CYCLES_REACHED)
            transition = CognitiveExecutionLoopController.advance(
                self._task,
                self._runtime_state,
            )
            self._runtime_state = transition.runtime_state

        assert transition.policy is not None
        policy = transition.policy
        request = _project_policy(policy)
        if request is None:
            return self._finish(
                CognitiveSessionTerminationReason.FAILED,
                ({"type": "policy", "category": _policy_failure_category(policy)},),
            )
        self._cycles_completed += 1
        self._phase = CognitiveSessionPhase.AWAITING_OBSERVATION
        return CognitiveSessionStepResult(
            phase=self._phase,
            action_request=request,
            evidence=({"type": "policy", "action": policy.action},),
        )

    def observe(self, observation: Observation) -> None:
        """Accept one validated external Observation for a later cognitive step."""

        self._require_started()
        self._require_not_terminated()
        if self._phase is not CognitiveSessionPhase.AWAITING_OBSERVATION:
            raise RuntimeError("session is not awaiting an observation")
        if not isinstance(observation, Observation):
            raise TypeError("observation must be an Observation")
        if observation.source != "agent_environment":
            raise ValueError("observation source must be 'agent_environment'")
        if not isinstance(observation.content, dict):
            raise TypeError("observation content must be a JSON-compatible dictionary")

        feedback = _freeze_json(observation.content)
        # A fresh reconstruction prevents aliases to caller-owned nested data.
        private_observation = Observation.from_dict(observation.to_dict())
        self._pending_observation = private_observation
        self._pending_feedback = feedback
        self._phase = CognitiveSessionPhase.READY

    def terminate(
        self,
        reason: CognitiveSessionTerminationReason,
    ) -> CognitiveSessionStepResult:
        """Explicitly end a started session without changing core runtime behavior."""

        self._require_started()
        if not isinstance(reason, CognitiveSessionTerminationReason):
            raise TypeError("reason must be a CognitiveSessionTerminationReason")
        if self._terminal_result is not None:
            return self._terminal_result
        return self._finish(reason, ({"type": "external_termination", "reason": reason.value},))

    def _finish(
        self,
        reason: CognitiveSessionTerminationReason,
        evidence: tuple[dict[str, Any], ...] = (),
        answer: Any | None = None,
    ) -> CognitiveSessionStepResult:
        if self._terminal_result is None:
            if reason is not CognitiveSessionTerminationReason.COMPLETED:
                answer = None
            self._phase = CognitiveSessionPhase.TERMINATED
            self._terminal_result = CognitiveSessionStepResult(
                phase=CognitiveSessionPhase.TERMINATED,
                termination_reason=reason,
                answer=answer,
                evidence=evidence,
            )
        return self._terminal_result

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError("session has not been started")

    def _require_not_terminated(self) -> None:
        if self._terminal_result is not None:
            raise RuntimeError("session is already terminated")


def _project_policy(policy: Policy) -> CognitiveActionRequest | None:
    """Narrowly project supported Goal-aware Policies to the external boundary."""

    if policy.action == "produce_answer" and set(policy.parameters) == {"answer"}:
        return CognitiveActionRequest("answer", {"answer": policy.parameters["answer"]})
    if policy.action == "call_tool" and set(policy.parameters) == {
        "tool_name",
        "tool_parameters",
    }:
        name = policy.parameters["tool_name"]
        parameters = policy.parameters["tool_parameters"]
        if isinstance(name, str) and isinstance(parameters, dict):
            return CognitiveActionRequest(
                "tool_call",
                {"tool_name": name, "parameters": parameters},
            )
    return None


def _policy_failure_category(policy: Policy) -> str:
    if policy.action == "fail_task":
        return str(policy.parameters.get("reason", "unsupported_task"))
    return "unsupported_policy"
