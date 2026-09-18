"""Strict, stateless M18 Direct Tool-Calling evaluation condition."""

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


_FORBIDDEN_KEYS = frozenset({
    "expected_answer", "ground_truth", "correct_tool", "correct_action", "difficulty",
    "cohort", "cohort_label", "cohort_routing_label", "evaluator_success",
    "judge_metadata", "private_judge_metadata", "completion_status", "completion_label",
    "benchmark_completion_state", "chain_of_thought", "hidden_reasoning", "plan",
    "rationale", "thought", "confidence", "credentials", "api_key",
})


def _freeze_public(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("public JSON floats must be finite")
        return value
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("public mapping keys must be strings")
            if key not in _FORBIDDEN_KEYS:
                output[key] = _freeze_public(item)
        return MappingProxyType(output)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_public(item) for item in value)
    raise TypeError("public values must be JSON-compatible")


def _freeze_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("JSON floats must be finite")
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("JSON mapping keys must be strings")
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    raise TypeError("value must be JSON-compatible")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return deepcopy(value)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _hash(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


M18_DIRECT_ID = "m18_direct_tool_calling_v1"
M18_DIRECT_PROMPT = (
    "Select exactly one next execution action from the supplied public task, current public "
    "feedback, public tools, and public budget. Return only JSON matching the action schema. "
    "Allowed actions are answer and tool_call. Do not include plans, rationale, thoughts, "
    "confidence, chain-of-thought, or extra fields."
)
M18_DIRECT_RESPONSE_SCHEMA = {
    "oneOf": [
        {"type": "object", "additionalProperties": False, "required": ["action", "answer"], "properties": {"action": {"const": "answer"}, "answer": {"type": "integer"}}},
        {"type": "object", "additionalProperties": False, "required": ["action", "tool_name", "parameters"], "properties": {"action": {"const": "tool_call"}, "tool_name": {"type": "string", "minLength": 1}, "parameters": {"type": "object"}}},
    ],
}
M18_DIRECT_DECODER_ID = "strict_json_direct_action_decoder_v1"
M18_DIRECT_SERIALIZER_ID = "public_task_feedback_capabilities_budget_v1"
M18_DIRECT_STATE_POLICY_ID = "stateless_current_feedback_only_v1"
M18_DIRECT_CALL_POLICY_ID = "one_logical_provider_call_no_retry_no_fallback_v1"


class M18DirectConditionError(ValueError):
    """Explicit strict-output failure without repair, retry, or fallback."""


class M18DirectProviderError(RuntimeError):
    """Explicit provider failure without an adapter retry."""


class M18DirectTerminationReason(str, Enum):
    ANSWER_SUBMITTED = "answer_submitted"
    BUDGET_EXHAUSTED = "budget_exhausted"
    UNRECOVERABLE_ENVIRONMENT_FAILURE = "unrecoverable_environment_failure"
    PROVIDER_INTERNAL_FAILURE = "provider_internal_failure"


@dataclass(frozen=True)
class M18DirectProviderRequest:
    """One immutable request built solely from current public Direct inputs."""

    prompt: str
    public_task: dict[str, Any]
    current_feedback: dict[str, Any]
    capabilities: tuple[dict[str, Any], ...]
    budget: dict[str, Any]
    response_schema: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ValueError("prompt must be a non-empty string")
        if not isinstance(self.public_task, dict) or not isinstance(self.current_feedback, dict):
            raise TypeError("public_task and current_feedback must be dicts")
        if not isinstance(self.capabilities, tuple) or any(not isinstance(item, dict) for item in self.capabilities):
            raise TypeError("capabilities must be an ordered tuple of dicts")
        if not isinstance(self.budget, dict) or not isinstance(self.response_schema, dict):
            raise TypeError("budget and response_schema must be dicts")
        object.__setattr__(self, "public_task", _freeze_public(self.public_task))
        object.__setattr__(self, "current_feedback", _freeze_public(self.current_feedback))
        object.__setattr__(self, "capabilities", tuple(_freeze_public(item) for item in self.capabilities))
        object.__setattr__(self, "budget", _freeze_public(self.budget))
        object.__setattr__(self, "response_schema", _freeze_json(self.response_schema))

    def to_dict(self) -> dict[str, Any]:
        return {"prompt": self.prompt, "public_task": _thaw(self.public_task), "current_feedback": _thaw(self.current_feedback), "capabilities": _thaw(self.capabilities), "budget": _thaw(self.budget), "response_schema": _thaw(self.response_schema)}


@runtime_checkable
class M18DirectProvider(Protocol):
    def generate(self, request: M18DirectProviderRequest) -> str:
        """Return one raw structured response for a single Direct decision."""


@dataclass(frozen=True)
class M18DirectArtifacts:
    implementation_hash: str
    prompt_hash: str
    response_schema_hash: str
    decoder_hash: str
    input_serializer_hash: str
    state_history_policy_hash: str
    provider_call_policy_hash: str

    def to_dict(self) -> dict[str, str]:
        return {
            "implementation_hash": self.implementation_hash, "prompt_hash": self.prompt_hash,
            "response_schema_hash": self.response_schema_hash, "decoder_hash": self.decoder_hash,
            "input_serializer_hash": self.input_serializer_hash,
            "state_history_policy_hash": self.state_history_policy_hash,
            "provider_call_policy_hash": self.provider_call_policy_hash,
        }


def m18_direct_artifacts() -> M18DirectArtifacts:
    prompt_hash = _hash({"prompt": M18_DIRECT_PROMPT})
    schema_hash = _hash(M18_DIRECT_RESPONSE_SCHEMA)
    decoder_hash = _hash({"decoder": M18_DIRECT_DECODER_ID})
    serializer_hash = _hash({"serializer": M18_DIRECT_SERIALIZER_ID})
    state_hash = _hash({"state_policy": M18_DIRECT_STATE_POLICY_ID})
    call_hash = _hash({"call_policy": M18_DIRECT_CALL_POLICY_ID})
    return M18DirectArtifacts(
        implementation_hash=_hash({"id": M18_DIRECT_ID, "prompt": prompt_hash, "schema": schema_hash, "decoder": decoder_hash, "serializer": serializer_hash, "state": state_hash, "calls": call_hash}),
        prompt_hash=prompt_hash, response_schema_hash=schema_hash, decoder_hash=decoder_hash,
        input_serializer_hash=serializer_hash, state_history_policy_hash=state_hash,
        provider_call_policy_hash=call_hash,
    )


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise M18DirectConditionError("response contains duplicate JSON keys")
        output[key] = value
    return output


def _constant(_: str) -> None:
    raise M18DirectConditionError("response contains a non-finite JSON constant")


def decode_m18_direct_response(raw_output: str) -> EvaluationAction:
    """Decode only one exact action schema; never parse prose or repair JSON."""

    if not isinstance(raw_output, str):
        raise M18DirectConditionError("provider response must be a JSON string")
    try:
        data = json.loads(raw_output, object_pairs_hook=_pairs, parse_constant=_constant)
    except (json.JSONDecodeError, M18DirectConditionError) as error:
        raise M18DirectConditionError("provider response is not strict JSON") from error
    if not isinstance(data, dict):
        raise M18DirectConditionError("provider response must be an object")
    if data.get("action") == "answer":
        if set(data) != {"action", "answer"}:
            raise M18DirectConditionError("answer response has invalid fields")
        if not isinstance(data["answer"], int) or isinstance(data["answer"], bool):
            raise M18DirectConditionError("answer must be an integer")
        return EvaluationAction(EvaluationActionType.ANSWER, {"answer": _thaw(_freeze_json(data["answer"]))})
    if data.get("action") == "tool_call":
        if set(data) != {"action", "tool_name", "parameters"}:
            raise M18DirectConditionError("tool_call response has invalid fields")
        if not isinstance(data["tool_name"], str) or not data["tool_name"].strip() or data["tool_name"] != data["tool_name"].strip():
            raise M18DirectConditionError("tool_name must be a trimmed non-empty string")
        if not isinstance(data["parameters"], dict):
            raise M18DirectConditionError("tool_call parameters must be an object")
        return EvaluationAction(EvaluationActionType.TOOL_CALL, {"tool_name": data["tool_name"], "parameters": _thaw(_freeze_json(data["parameters"]))})
    raise M18DirectConditionError("response action is unsupported")


class M18DirectToolCallingBaseline:
    """A stateless multi-decision Direct adapter with observational accounting only."""

    def __init__(self, provider: M18DirectProvider, capabilities: tuple[CapabilityDescriptor, ...]) -> None:
        if not isinstance(provider, M18DirectProvider):
            raise TypeError("provider must implement M18DirectProvider")
        if not isinstance(capabilities, tuple) or any(not isinstance(item, CapabilityDescriptor) for item in capabilities):
            raise TypeError("capabilities must be an ordered CapabilityDescriptor tuple")
        self._provider = provider
        self._capabilities = capabilities
        self._logical_provider_calls = 0
        self._decision_count = 0
        self._tool_calls = 0
        self._invalid_action_feedbacks = 0
        self._recovery_feedbacks = 0

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

    @staticmethod
    def termination_for(step_input: AgentStepInput) -> M18DirectTerminationReason | None:
        if not isinstance(step_input, AgentStepInput):
            raise TypeError("step_input must be an AgentStepInput")
        if step_input.budget_state.remaining_steps == 0:
            return M18DirectTerminationReason.BUDGET_EXHAUSTED
        feedback = step_input.previous_feedback
        if feedback.feedback_type is EvaluationFeedbackType.TOOL_FAILURE and feedback.to_dict()["payload"].get("category") == "unrecoverable_failure":
            return M18DirectTerminationReason.UNRECOVERABLE_ENVIRONMENT_FAILURE
        return None

    def request_for(self, step_input: AgentStepInput) -> M18DirectProviderRequest:
        if not isinstance(step_input, AgentStepInput):
            raise TypeError("step_input must be an AgentStepInput")
        return M18DirectProviderRequest(
            prompt=M18_DIRECT_PROMPT,
            public_task=PolicyTaskContext.from_task(step_input.case.task).to_dict(),
            current_feedback=step_input.previous_feedback.to_dict(),
            capabilities=tuple(item.to_dict() for item in self._capabilities),
            budget=step_input.budget_state.to_dict(),
            response_schema=M18_DIRECT_RESPONSE_SCHEMA,
        )

    def step(self, step_input: AgentStepInput) -> AgentStepResult:
        termination = self.termination_for(step_input)
        if termination is not None:
            return AgentStepResult(EvaluationAction(EvaluationActionType.FAIL, {"reason": termination.value}), True)
        feedback_type = step_input.previous_feedback.feedback_type
        if feedback_type is EvaluationFeedbackType.INVALID_ACTION:
            self._invalid_action_feedbacks += 1
        if feedback_type is EvaluationFeedbackType.TOOL_FAILURE and step_input.previous_feedback.to_dict()["payload"].get("category") == "recoverable_failure":
            self._recovery_feedbacks += 1
        request = self.request_for(step_input)
        self._logical_provider_calls += 1
        self._decision_count += 1
        try:
            raw_output = self._provider.generate(request)
        except Exception as error:
            raise M18DirectProviderError("provider request failed") from error
        if not isinstance(raw_output, str):
            raise M18DirectProviderError("provider result must be a raw JSON string")
        action = decode_m18_direct_response(raw_output)
        if action.action_type is EvaluationActionType.TOOL_CALL:
            self._tool_calls += 1
        return AgentStepResult(action, action.action_type is not EvaluationActionType.TOOL_CALL)
