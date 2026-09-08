"""Provider-neutral, stateless Direct Tool-Calling evaluation baseline.

This module is evaluation infrastructure only.  It maps one untrusted direct
provider decision to one existing public evaluation action; it does not execute
tools, judge completion, retain an interaction trace, or import MIND cognitive
runtime components.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping, Protocol, TypeAlias, runtime_checkable

from src.evaluation.contracts import (
    EvaluationAction,
    EvaluationActionType,
    EvaluationCase,
    EvaluationFeedback,
    EvaluationFeedbackType,
)
from src.evaluation.execution import AgentStepInput, AgentStepResult, EvaluationBudgetState


def _freeze_json(value: Any) -> Any:
    """Detach JSON-compatible public values into immutable containers."""

    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("mapping keys must be strings")
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("float values must be finite")
        return value
    raise ValueError("values must be JSON-compatible data")


def _thaw_json(value: Any) -> Any:
    """Return fresh ordinary public containers."""

    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return deepcopy(value)


def _freeze_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict")
    return _freeze_json(value)


def _text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    if value != value.strip():
        raise ValueError(f"{name} must not have leading or trailing whitespace")


def _non_negative_optional_int(value: Any, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int or None")
    if value < 0:
        raise ValueError(f"{name} must not be negative")


@dataclass(frozen=True)
class DirectActionResourceMetadata:
    """Optional, provider-reported observations; never invented by the agent."""

    model_calls: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None

    def __post_init__(self) -> None:
        for name in ("model_calls", "input_tokens", "output_tokens", "latency_ms"):
            _non_negative_optional_int(getattr(self, name), name)

    def to_dict(self) -> dict[str, int | None]:
        return {
            "model_calls": self.model_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_ms": self.latency_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DirectActionResourceMetadata":
        if not isinstance(data, dict):
            raise TypeError("DirectActionResourceMetadata data must be a dict")
        return cls(
            model_calls=data.get("model_calls"),
            input_tokens=data.get("input_tokens"),
            output_tokens=data.get("output_tokens"),
            latency_ms=data.get("latency_ms"),
        )


@dataclass(frozen=True)
class DirectActionRequest:
    """One public, immutable direct-decision request with no interaction trace."""

    task: dict[str, Any]
    latest_feedback: EvaluationFeedback
    budget_state: EvaluationBudgetState
    tool_schemas: dict[str, Any]
    provider_configuration_id: str

    def __post_init__(self) -> None:
        frozen_task = _freeze_mapping(self.task, "task")
        if not isinstance(self.latest_feedback, EvaluationFeedback):
            raise TypeError("latest_feedback must be an EvaluationFeedback")
        if not isinstance(self.budget_state, EvaluationBudgetState):
            raise TypeError("budget_state must be an EvaluationBudgetState")
        frozen_schemas = _freeze_mapping(self.tool_schemas, "tool_schemas")
        _text(self.provider_configuration_id, "provider_configuration_id")
        object.__setattr__(self, "task", frozen_task)
        object.__setattr__(self, "tool_schemas", frozen_schemas)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": _thaw_json(self.task),
            "latest_feedback": self.latest_feedback.to_dict(),
            "budget_state": self.budget_state.to_dict(),
            "tool_schemas": _thaw_json(self.tool_schemas),
            "provider_configuration_id": self.provider_configuration_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DirectActionRequest":
        if not isinstance(data, dict):
            raise TypeError("DirectActionRequest data must be a dict")
        return cls(
            task=data["task"],
            latest_feedback=EvaluationFeedback.from_dict(data["latest_feedback"]),
            budget_state=EvaluationBudgetState.from_dict(data["budget_state"]),
            tool_schemas=data["tool_schemas"],
            provider_configuration_id=data["provider_configuration_id"],
        )


@dataclass(frozen=True)
class DirectActionProviderResponse:
    """One untrusted structured action response, without execution authority."""

    action_type: EvaluationActionType
    payload: dict[str, Any] = field(default_factory=dict)
    resource_metadata: DirectActionResourceMetadata | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.action_type, EvaluationActionType):
            raise TypeError("action_type must be an EvaluationActionType")
        frozen_payload = _freeze_mapping(self.payload, "payload")
        if self.action_type is EvaluationActionType.ANSWER and "answer" not in frozen_payload:
            raise ValueError("answer payload requires answer")
        if self.action_type is EvaluationActionType.TOOL_CALL:
            _text(frozen_payload.get("tool_name"), "tool_name")
            if not isinstance(frozen_payload.get("parameters"), Mapping):
                raise TypeError("tool_call payload requires parameters dict")
        if self.action_type in {EvaluationActionType.FAIL, EvaluationActionType.INVALID}:
            _text(frozen_payload.get("reason"), "reason")
        if self.resource_metadata is not None and not isinstance(
            self.resource_metadata,
            DirectActionResourceMetadata,
        ):
            raise TypeError("resource_metadata must be DirectActionResourceMetadata or None")
        object.__setattr__(self, "payload", frozen_payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "payload": _thaw_json(self.payload),
            "resource_metadata": (
                None if self.resource_metadata is None else self.resource_metadata.to_dict()
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DirectActionProviderResponse":
        if not isinstance(data, dict):
            raise TypeError("DirectActionProviderResponse data must be a dict")
        try:
            action_type = EvaluationActionType(data["action_type"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid DirectActionProviderResponse action_type") from error
        resource_data = data.get("resource_metadata")
        return cls(
            action_type=action_type,
            payload=data.get("payload", {}),
            resource_metadata=(
                None
                if resource_data is None
                else DirectActionResourceMetadata.from_dict(resource_data)
            ),
        )


class DirectActionProviderFailureCategory(str, Enum):
    """Frozen provider-side errors, distinct from evaluator outcomes."""

    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_TIMEOUT = "provider_timeout"
    MALFORMED_RESPONSE = "malformed_response"
    UNSUPPORTED_ACTION = "unsupported_action"


@dataclass(frozen=True)
class DirectActionProviderFailure:
    """Explicit bounded direct-provider failure without benchmark judgment."""

    category: DirectActionProviderFailureCategory
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.category, DirectActionProviderFailureCategory):
            raise TypeError("category must be a DirectActionProviderFailureCategory")
        object.__setattr__(self, "evidence", _freeze_mapping(self.evidence, "evidence"))

    def to_dict(self) -> dict[str, Any]:
        return {"category": self.category.value, "evidence": _thaw_json(self.evidence)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DirectActionProviderFailure":
        if not isinstance(data, dict):
            raise TypeError("DirectActionProviderFailure data must be a dict")
        try:
            category = DirectActionProviderFailureCategory(data["category"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid DirectActionProviderFailure category") from error
        return cls(category=category, evidence=data.get("evidence", {}))


DirectActionProviderResult: TypeAlias = DirectActionProviderResponse | DirectActionProviderFailure


@runtime_checkable
class DirectActionProvider(Protocol):
    """Evaluation-side provider boundary for direct public action generation."""

    def decide(self, request: DirectActionRequest) -> DirectActionProviderResult:
        """Return one structured direct action or explicit provider failure."""


@dataclass(frozen=True)
class FakeDirectActionProvider:
    """Stateless deterministic provider fixture keyed only by latest feedback type."""

    responses: dict[EvaluationFeedbackType, DirectActionProviderResult]

    def __post_init__(self) -> None:
        if not isinstance(self.responses, dict):
            raise TypeError("responses must be a dict")
        copied: dict[EvaluationFeedbackType, DirectActionProviderResult] = {}
        for feedback_type, result in self.responses.items():
            if not isinstance(feedback_type, EvaluationFeedbackType):
                raise TypeError("responses keys must be EvaluationFeedbackType values")
            if not isinstance(result, (DirectActionProviderResponse, DirectActionProviderFailure)):
                raise TypeError("responses values must be direct provider results")
            copied[feedback_type] = result
        object.__setattr__(self, "responses", MappingProxyType(copied))

    def decide(self, request: DirectActionRequest) -> DirectActionProviderResult:
        if not isinstance(request, DirectActionRequest):
            raise TypeError("request must be a DirectActionRequest")
        try:
            return self.responses[request.latest_feedback.feedback_type]
        except KeyError:
            return DirectActionProviderFailure(
                DirectActionProviderFailureCategory.UNSUPPORTED_ACTION,
                {"feedback_type": request.latest_feedback.feedback_type.value},
            )


@dataclass(frozen=True)
class CohortAEligibilityDecision:
    """Evaluator-owned pre-outcome decision for M16 main-comparison membership."""

    eligible: bool
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.eligible, bool):
            raise TypeError("eligible must be a bool")
        _text(self.reason, "reason")

    def to_dict(self) -> dict[str, Any]:
        return {"eligible": self.eligible, "reason": self.reason}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CohortAEligibilityDecision":
        if not isinstance(data, dict):
            raise TypeError("CohortAEligibilityDecision data must be a dict")
        return cls(eligible=data["eligible"], reason=data["reason"])


def assess_cohort_a_eligibility(case: EvaluationCase) -> CohortAEligibilityDecision:
    """Classify frozen M16 metadata before any provider or Agent result exists."""

    if not isinstance(case, EvaluationCase):
        raise TypeError("case must be an EvaluationCase")
    metadata = case.task.metadata
    raw = metadata.get("m16_cohort_a") if isinstance(metadata, Mapping) else None
    if not isinstance(raw, Mapping):
        return CohortAEligibilityDecision(False, "missing_m16_cohort_a_metadata")
    family = raw.get("task_family")
    limit = raw.get("tool_call_limit")
    required_flags = (
        "requires_planning",
        "requires_multi_tool",
        "requires_dependent_multistep",
        "requires_recovery",
    )
    if family not in {"direct_answer", "controlled_single_tool"}:
        return CohortAEligibilityDecision(False, "unsupported_task_family")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit not in {0, 1}:
        return CohortAEligibilityDecision(False, "invalid_tool_call_limit")
    if family == "direct_answer" and limit != 0:
        return CohortAEligibilityDecision(False, "direct_answer_requires_zero_tool_calls")
    if family == "controlled_single_tool" and limit != 1:
        return CohortAEligibilityDecision(False, "controlled_single_tool_requires_one_tool_call")
    for flag in required_flags:
        value = raw.get(flag)
        if not isinstance(value, bool):
            return CohortAEligibilityDecision(False, f"invalid_{flag}")
        if value:
            return CohortAEligibilityDecision(False, flag)
    return CohortAEligibilityDecision(True, "eligible")


class DirectToolCallingEvaluationAgent:
    """Stateless per-decision adapter from a direct provider to public actions."""

    def __init__(
        self,
        provider: DirectActionProvider,
        tool_schemas: dict[str, Any],
        provider_configuration_id: str,
    ) -> None:
        if not isinstance(provider, DirectActionProvider):
            raise TypeError("provider must implement DirectActionProvider")
        self._provider = provider
        self._tool_schemas = _freeze_mapping(tool_schemas, "tool_schemas")
        _text(provider_configuration_id, "provider_configuration_id")
        self._provider_configuration_id = provider_configuration_id

    def step(self, step_input: AgentStepInput) -> AgentStepResult:
        """Map one latest-feedback provider decision without retaining a trace."""

        if not isinstance(step_input, AgentStepInput):
            raise TypeError("step_input must be an AgentStepInput")
        request = DirectActionRequest(
            task=step_input.case.task.to_dict(),
            latest_feedback=step_input.previous_feedback,
            budget_state=step_input.budget_state,
            tool_schemas=_thaw_json(self._tool_schemas),
            provider_configuration_id=self._provider_configuration_id,
        )
        result = self._provider.decide(request)
        if not isinstance(result, (DirectActionProviderResponse, DirectActionProviderFailure)):
            return _invalid("malformed_response")
        if isinstance(result, DirectActionProviderFailure):
            return _provider_failure(result.category)
        return _response_step(result)


def _response_step(response: DirectActionProviderResponse) -> AgentStepResult:
    action = EvaluationAction(response.action_type, _thaw_json(response.payload))
    return AgentStepResult(
        action=action,
        request_termination=response.action_type is not EvaluationActionType.TOOL_CALL,
    )


def _invalid(reason: str) -> AgentStepResult:
    return AgentStepResult(
        EvaluationAction(EvaluationActionType.INVALID, {"reason": reason}),
        True,
    )


def _provider_failure(category: DirectActionProviderFailureCategory) -> AgentStepResult:
    if category in {
        DirectActionProviderFailureCategory.PROVIDER_UNAVAILABLE,
        DirectActionProviderFailureCategory.PROVIDER_TIMEOUT,
    }:
        return AgentStepResult(
            EvaluationAction(EvaluationActionType.FAIL, {"reason": category.value}),
            True,
        )
    return _invalid(category.value)
