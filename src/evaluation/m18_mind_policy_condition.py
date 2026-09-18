"""Strict, evaluation-side M18 provider policy condition.

This module intentionally depends only on the public policy-decision boundary.
It neither executes actions nor retains provider conversation state.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

from src.core.policy import Policy
from src.core.policy_context import PolicyDecisionContext, PolicyDecisionEngine


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


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return deepcopy(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _hash(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


M18_POLICY_CONDITION_ID = "m18_mind_policy_condition_v1"
M18_POLICY_PROMPT = (
    "Select exactly one next execution action using only the supplied public context. "
    "Return only a JSON object that satisfies the response schema. "
    "Allowed actions are answer and tool_call. Do not include reasoning, rationale, "
    "plans, confidence, benchmark interpretation, or additional fields."
)
M18_POLICY_RESPONSE_SCHEMA = {
    "oneOf": [
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["action", "answer"],
            "properties": {"action": {"const": "answer"}, "answer": {"type": "integer"}},
        },
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["action", "tool_name", "parameters"],
            "properties": {
                "action": {"const": "tool_call"},
                "tool_name": {"type": "string", "minLength": 1},
                "parameters": {"type": "object"},
            },
        },
    ]
}
M18_POLICY_DECODER_ID = "strict_json_action_decoder_v1"
M18_POLICY_CONTEXT_SERIALIZER_ID = "policy_decision_context_to_dict_canonical_json_v1"
M18_POLICY_CALL_POLICY_ID = "one_logical_provider_call_no_retry_no_fallback_v1"


class M18PolicyConditionError(ValueError):
    """Explicit failure for malformed or unsupported provider output."""


class M18PolicyProviderError(RuntimeError):
    """Explicit provider-boundary failure; it has no retry or fallback behavior."""


@dataclass(frozen=True)
class M18PolicyProviderRequest:
    """One immutable, public, stateless request to an injected provider edge."""

    prompt: str
    public_context: dict[str, Any]
    response_schema: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.prompt, str) or not self.prompt.strip():
            raise ValueError("prompt must be a non-empty string")
        if not isinstance(self.public_context, dict):
            raise TypeError("public_context must be a dict")
        if not isinstance(self.response_schema, dict):
            raise TypeError("response_schema must be a dict")
        object.__setattr__(self, "public_context", _freeze_json(self.public_context))
        object.__setattr__(self, "response_schema", _freeze_json(self.response_schema))

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "public_context": _thaw_json(self.public_context),
            "response_schema": _thaw_json(self.response_schema),
        }


@runtime_checkable
class M18PolicyProvider(Protocol):
    """Provider edge for a single raw structured response, without execution."""

    def generate(self, request: M18PolicyProviderRequest) -> str:
        """Return exactly one raw response for one request."""


@dataclass(frozen=True)
class M18PolicyArtifacts:
    """Deterministic identities for the frozen condition contract, not a provider config."""

    condition_id: str
    condition_hash: str
    prompt_hash: str
    response_schema_hash: str
    decoder_hash: str
    context_serializer_hash: str
    provider_call_policy_hash: str

    def to_dict(self) -> dict[str, str]:
        return {
            "condition_id": self.condition_id,
            "condition_hash": self.condition_hash,
            "prompt_hash": self.prompt_hash,
            "response_schema_hash": self.response_schema_hash,
            "decoder_hash": self.decoder_hash,
            "context_serializer_hash": self.context_serializer_hash,
            "provider_call_policy_hash": self.provider_call_policy_hash,
        }


def m18_policy_artifacts() -> M18PolicyArtifacts:
    """Return stable hashes for all behavior-defining M18 adapter artifacts."""

    prompt_hash = _hash({"prompt": M18_POLICY_PROMPT})
    schema_hash = _hash(M18_POLICY_RESPONSE_SCHEMA)
    decoder_hash = _hash({"decoder": M18_POLICY_DECODER_ID})
    serializer_hash = _hash({"serializer": M18_POLICY_CONTEXT_SERIALIZER_ID})
    call_policy_hash = _hash({"provider_call_policy": M18_POLICY_CALL_POLICY_ID})
    return M18PolicyArtifacts(
        condition_id=M18_POLICY_CONDITION_ID,
        condition_hash=_hash(
            {
                "condition_id": M18_POLICY_CONDITION_ID,
                "prompt_hash": prompt_hash,
                "response_schema_hash": schema_hash,
                "decoder_hash": decoder_hash,
                "context_serializer_hash": serializer_hash,
                "provider_call_policy_hash": call_policy_hash,
            },
        ),
        prompt_hash=prompt_hash,
        response_schema_hash=schema_hash,
        decoder_hash=decoder_hash,
        context_serializer_hash=serializer_hash,
        provider_call_policy_hash=call_policy_hash,
    )


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise M18PolicyConditionError("provider JSON contains duplicate keys")
        output[key] = value
    return output


def _reject_json_constant(_: str) -> None:
    raise M18PolicyConditionError("provider JSON contains a non-finite constant")


def decode_m18_policy_response(raw_output: str) -> Policy:
    """Strictly map one exact JSON action form to the existing Policy model."""

    if not isinstance(raw_output, str):
        raise M18PolicyConditionError("provider output must be a JSON string")
    try:
        data = json.loads(
            raw_output,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, M18PolicyConditionError) as error:
        raise M18PolicyConditionError("provider output is not strict JSON") from error
    if not isinstance(data, dict):
        raise M18PolicyConditionError("provider output must be a JSON object")

    action = data.get("action")
    if action == "answer":
        if set(data) != {"action", "answer"}:
            raise M18PolicyConditionError("answer output has an invalid field set")
        if not isinstance(data["answer"], int) or isinstance(data["answer"], bool):
            raise M18PolicyConditionError("answer must be an integer")
        try:
            answer = _thaw_json(_freeze_json(data["answer"]))
        except (TypeError, ValueError) as error:
            raise M18PolicyConditionError("answer must be JSON-compatible") from error
        return Policy(action="produce_answer", parameters={"answer": answer}, metadata={})

    if action == "tool_call":
        if set(data) != {"action", "tool_name", "parameters"}:
            raise M18PolicyConditionError("tool_call output has an invalid field set")
        if not isinstance(data["tool_name"], str) or not data["tool_name"].strip():
            raise M18PolicyConditionError("tool_name must be a non-empty string")
        if data["tool_name"] != data["tool_name"].strip():
            raise M18PolicyConditionError("tool_name must not have outer whitespace")
        if not isinstance(data["parameters"], dict):
            raise M18PolicyConditionError("parameters must be a JSON object")
        try:
            parameters = _thaw_json(_freeze_json(data["parameters"]))
        except (TypeError, ValueError) as error:
            raise M18PolicyConditionError("parameters must be JSON-compatible") from error
        return Policy(
            action="call_tool",
            parameters={"tool_name": data["tool_name"], "tool_parameters": parameters},
            metadata={},
        )

    raise M18PolicyConditionError("provider output has an unknown action")


class M18MINDPolicyCondition(PolicyDecisionEngine):
    """Stateless evaluation-side PolicyDecisionEngine using one injected provider call."""

    def __init__(self, provider: M18PolicyProvider) -> None:
        if not isinstance(provider, M18PolicyProvider):
            raise TypeError("provider must implement M18PolicyProvider")
        self._provider = provider
        self._logical_provider_calls = 0

    @property
    def logical_provider_calls(self) -> int:
        """Observational call accounting; it never affects policy semantics."""

        return self._logical_provider_calls

    @staticmethod
    def request_for(context: PolicyDecisionContext) -> M18PolicyProviderRequest:
        if not isinstance(context, PolicyDecisionContext):
            raise TypeError("context must be a PolicyDecisionContext")
        # Only the established public projection may cross the provider boundary.
        return M18PolicyProviderRequest(
            prompt=M18_POLICY_PROMPT,
            public_context=context.to_dict(),
            response_schema=M18_POLICY_RESPONSE_SCHEMA,
        )

    def decide(self, context: PolicyDecisionContext) -> Policy:
        request = self.request_for(context)
        self._logical_provider_calls += 1
        try:
            raw_output = self._provider.generate(request)
        except Exception as error:
            raise M18PolicyProviderError("provider request failed") from error
        if not isinstance(raw_output, str):
            raise M18PolicyProviderError("provider response must be a raw JSON string")
        return decode_m18_policy_response(raw_output)
