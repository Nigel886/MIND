"""Evaluation-side M18 ReAct condition with explicit public interaction history."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

from src.core.policy_context import PolicyTaskContext
from src.core.tool import CapabilityDescriptor
from src.evaluation.contracts import EvaluationAction, EvaluationActionType, EvaluationFeedback, EvaluationFeedbackType
from src.evaluation.execution import AgentStepInput, AgentStepResult
from src.evaluation.m18_direct_tool_calling import M18_DIRECT_RESPONSE_SCHEMA, decode_m18_direct_response


_FORBIDDEN = frozenset({
    "expected_answer", "ground_truth", "correct_tool", "correct_action", "difficulty",
    "cohort", "cohort_label", "cohort_routing_label", "evaluator_success",
    "judge_metadata", "private_judge_metadata", "completion_status", "completion_label",
    "benchmark_completion_state", "chain_of_thought", "hidden_reasoning", "thought",
    "rationale", "plan", "confidence", "credentials", "api_key",
})


def _freeze_public(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value): raise ValueError("public floats must be finite")
        return value
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str): raise TypeError("public mapping keys must be strings")
            if key not in _FORBIDDEN: result[key] = _freeze_public(item)
        return MappingProxyType(result)
    if isinstance(value, (tuple, list)): return tuple(_freeze_public(item) for item in value)
    raise TypeError("public values must be JSON-compatible")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping): return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple): return [_thaw(item) for item in value]
    return deepcopy(value)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _hash(value: Any) -> str: return sha256(_canonical(value).encode("utf-8")).hexdigest()


M18_REACT_ID = "m18_react_baseline_v1"
M18_REACT_PROMPT = (
    "Select exactly one next execution action using the public task, public tools, explicit public "
    "action-observation history, current public feedback, and public budget. Return only JSON matching "
    "the action schema. Allowed actions are answer and tool_call. Do not emit thought, reasoning, "
    "rationale, plan, confidence, or additional fields."
)
M18_REACT_DECODER_ID = "m18_shared_strict_direct_action_decoder_v1"
M18_REACT_HISTORY_POLICY_ID = "ordered_explicit_public_action_feedback_history_only_v1"
M18_REACT_SERIALIZER_ID = "public_task_capabilities_history_feedback_budget_v1"
M18_REACT_CALL_POLICY_ID = "one_logical_provider_call_per_decision_no_retry_no_fallback_v1"


class M18ReActConditionError(ValueError): pass
class M18ReActProviderError(RuntimeError): pass


class M18ReActTerminationReason(str, Enum):
    ANSWER_SUBMITTED = "answer_submitted"
    BUDGET_EXHAUSTED = "budget_exhausted"
    UNRECOVERABLE_ENVIRONMENT_FAILURE = "unrecoverable_environment_failure"
    PROVIDER_INTERNAL_FAILURE = "provider_internal_failure"


@dataclass(frozen=True)
class ReActInteraction:
    """One typed public action followed by its public environment feedback."""
    action: EvaluationAction
    feedback: EvaluationFeedback

    def __post_init__(self) -> None:
        if not isinstance(self.action, EvaluationAction) or not isinstance(self.feedback, EvaluationFeedback):
            raise TypeError("action and feedback must be public evaluation contracts")

    def to_dict(self) -> dict[str, Any]:
        return _thaw(_freeze_public({"action": self.action.to_dict(), "feedback": self.feedback.to_dict()}))


@dataclass(frozen=True)
class M18ReActProviderRequest:
    prompt: str
    public_task: dict[str, Any]
    capabilities: tuple[dict[str, Any], ...]
    interaction_history: tuple[ReActInteraction, ...]
    current_feedback: dict[str, Any]
    budget: dict[str, Any]
    response_schema: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.prompt, str) or not self.prompt.strip(): raise ValueError("prompt must be non-empty")
        if not isinstance(self.public_task, dict) or not isinstance(self.current_feedback, dict) or not isinstance(self.budget, dict) or not isinstance(self.response_schema, dict): raise TypeError("request mappings must be dicts")
        if not isinstance(self.capabilities, tuple) or any(not isinstance(item, dict) for item in self.capabilities): raise TypeError("capabilities must be ordered dicts")
        if not isinstance(self.interaction_history, tuple) or any(not isinstance(item, ReActInteraction) for item in self.interaction_history): raise TypeError("interaction_history must be ReActInteraction values")
        object.__setattr__(self, "public_task", _freeze_public(self.public_task))
        object.__setattr__(self, "capabilities", tuple(_freeze_public(item) for item in self.capabilities))
        object.__setattr__(self, "current_feedback", _freeze_public(self.current_feedback))
        object.__setattr__(self, "budget", _freeze_public(self.budget))
        object.__setattr__(self, "response_schema", _freeze_public(self.response_schema))

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt, "public_task": _thaw(self.public_task), "capabilities": _thaw(self.capabilities),
            "interaction_history": [item.to_dict() for item in self.interaction_history],
            "current_feedback": _thaw(self.current_feedback), "budget": _thaw(self.budget),
            "response_schema": _thaw(self.response_schema),
        }


@runtime_checkable
class M18ReActProvider(Protocol):
    def generate(self, request: M18ReActProviderRequest) -> str: ...


@dataclass(frozen=True)
class M18ReActArtifacts:
    implementation_hash: str
    prompt_hash: str
    action_schema_hash: str
    decoder_hash: str
    history_serializer_hash: str
    state_history_policy_hash: str
    provider_call_policy_hash: str
    def to_dict(self) -> dict[str, str]: return self.__dict__.copy()


def m18_react_artifacts() -> M18ReActArtifacts:
    prompt = _hash({"prompt": M18_REACT_PROMPT}); schema = _hash(M18_DIRECT_RESPONSE_SCHEMA)
    decoder = _hash({"decoder": M18_REACT_DECODER_ID}); serializer = _hash({"serializer": M18_REACT_SERIALIZER_ID})
    history = _hash({"history_policy": M18_REACT_HISTORY_POLICY_ID}); calls = _hash({"call_policy": M18_REACT_CALL_POLICY_ID})
    return M18ReActArtifacts(_hash({"id": M18_REACT_ID, "prompt": prompt, "schema": schema, "decoder": decoder, "serializer": serializer, "history": history, "calls": calls}), prompt, schema, decoder, serializer, history, calls)


class M18ReActBaseline:
    """ReAct-style public action-observation loop without a plan or private reasoning."""
    def __init__(self, provider: M18ReActProvider, capabilities: tuple[CapabilityDescriptor, ...]) -> None:
        if not isinstance(provider, M18ReActProvider): raise TypeError("provider must implement M18ReActProvider")
        if not isinstance(capabilities, tuple) or any(not isinstance(item, CapabilityDescriptor) for item in capabilities): raise TypeError("capabilities must be an ordered descriptor tuple")
        self._provider = provider
        self._capabilities = capabilities
        self._history: tuple[ReActInteraction, ...] = ()
        self._pending_action: EvaluationAction | None = None
        self._logical_provider_calls = 0
        self._decision_count = 0
        self._tool_calls = 0
        self._invalid_action_feedbacks = 0
        self._recovery_feedbacks = 0

    @property
    def interaction_history(self) -> tuple[ReActInteraction, ...]: return self._history
    @property
    def logical_provider_calls(self) -> int: return self._logical_provider_calls
    @property
    def decision_count(self) -> int: return self._decision_count
    @property
    def tool_calls(self) -> int: return self._tool_calls
    @property
    def invalid_action_feedbacks(self) -> int: return self._invalid_action_feedbacks
    @property
    def recovery_feedbacks(self) -> int: return self._recovery_feedbacks

    def _accept_feedback(self, feedback: EvaluationFeedback) -> None:
        if self._pending_action is not None:
            self._history = self._history + (ReActInteraction(self._pending_action, feedback),)
            self._pending_action = None
        if feedback.feedback_type is EvaluationFeedbackType.INVALID_ACTION: self._invalid_action_feedbacks += 1
        if feedback.feedback_type is EvaluationFeedbackType.TOOL_FAILURE and feedback.to_dict()["payload"].get("category") == "recoverable_failure": self._recovery_feedbacks += 1

    @staticmethod
    def termination_for(step_input: AgentStepInput) -> M18ReActTerminationReason | None:
        if step_input.budget_state.remaining_steps == 0: return M18ReActTerminationReason.BUDGET_EXHAUSTED
        feedback = step_input.previous_feedback
        if feedback.feedback_type is EvaluationFeedbackType.TOOL_FAILURE and feedback.to_dict()["payload"].get("category") == "unrecoverable_failure": return M18ReActTerminationReason.UNRECOVERABLE_ENVIRONMENT_FAILURE
        return None

    def request_for(self, step_input: AgentStepInput) -> M18ReActProviderRequest:
        return M18ReActProviderRequest(
            M18_REACT_PROMPT, PolicyTaskContext.from_task(step_input.case.task).to_dict(),
            tuple(item.to_dict() for item in self._capabilities), self._history,
            step_input.previous_feedback.to_dict(), step_input.budget_state.to_dict(), M18_DIRECT_RESPONSE_SCHEMA,
        )

    def step(self, step_input: AgentStepInput) -> AgentStepResult:
        if not isinstance(step_input, AgentStepInput): raise TypeError("step_input must be an AgentStepInput")
        self._accept_feedback(step_input.previous_feedback)
        termination = self.termination_for(step_input)
        if termination is not None: return AgentStepResult(EvaluationAction(EvaluationActionType.FAIL, {"reason": termination.value}), True)
        request = self.request_for(step_input)
        self._logical_provider_calls += 1; self._decision_count += 1
        try: raw = self._provider.generate(request)
        except Exception as error: raise M18ReActProviderError("provider request failed") from error
        try: action = decode_m18_direct_response(raw)
        except Exception as error: raise M18ReActConditionError("provider output rejected by strict action decoder") from error
        if action.action_type is EvaluationActionType.TOOL_CALL:
            self._tool_calls += 1; self._pending_action = action
        return AgentStepResult(action, action.action_type is not EvaluationActionType.TOOL_CALL)
