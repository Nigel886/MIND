"""Deterministic parsing of untrusted provider responses into M13 proposals."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias

from src.core.task import Task
from src.core.task_interpretation import TaskInterpretationProposal
from src.integration.llm_provider import LLMProvider, ProviderFailure, ProviderResponse


class InterpreterFailureCategory(str, Enum):
    """Explicit failures owned by deterministic provider-payload parsing."""

    INVALID_OUTPUT_FORMAT = "invalid_output_format"
    INVALID_PROPOSAL = "invalid_proposal"


def _freeze_value(value: Any) -> Any:
    """Recursively copy JSON-compatible data into immutable containers."""

    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("mapping keys must be strings")
        return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("float values must be finite")
        return value
    raise ValueError("values must be JSON-compatible data")


def _thaw_value(value: Any) -> Any:
    """Return fresh ordinary containers from recursively frozen data."""

    if isinstance(value, Mapping):
        return {key: _thaw_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    return deepcopy(value)


def _freeze_mapping(value: Any, name: str) -> Mapping[str, Any]:
    """Validate and freeze compact interpreter-owned evidence."""

    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict")
    return _freeze_value(value)


@dataclass(frozen=True)
class InterpreterFailure:
    """Immutable explicit parser failure separate from provider failures."""

    category: InterpreterFailureCategory
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and detach nested caller-owned failure evidence."""

        if not isinstance(self.category, InterpreterFailureCategory):
            raise TypeError("category must be an InterpreterFailureCategory")
        object.__setattr__(self, "evidence", _freeze_mapping(self.evidence, "evidence"))

    def to_dict(self) -> dict[str, Any]:
        """Serialize this failure to fresh ordinary containers."""

        return {"category": self.category.value, "evidence": _thaw_value(self.evidence)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InterpreterFailure":
        """Reconstruct a parser failure without coercing malformed input."""

        if not isinstance(data, dict):
            raise TypeError("InterpreterFailure data must be a dict")
        try:
            category = InterpreterFailureCategory(data["category"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid InterpreterFailure category") from error
        return cls(category=category, evidence=data.get("evidence", {}))


InterpreterResult: TypeAlias = TaskInterpretationProposal | ProviderFailure | InterpreterFailure


class TaskInterpreter:
    """Call one provider and deterministically parse only its raw payload schema."""

    _ALLOWED_PAYLOAD_FIELDS = frozenset(
        {"intent", "required_capabilities", "constraints", "evidence"},
    )

    def __init__(self, provider: LLMProvider) -> None:
        """Create an interpreter with one provider boundary dependency."""

        if not isinstance(provider, LLMProvider):
            raise TypeError("provider must satisfy LLMProvider")
        self._provider = provider

    def interpret(self, task: Task) -> InterpreterResult:
        """Return a proposal, pass through provider failure, or report parser failure."""

        if not isinstance(task, Task):
            raise TypeError("task must be a Task")

        result = self._provider.interpret(task)
        if isinstance(result, ProviderFailure):
            return result
        if not isinstance(result, ProviderResponse):
            return InterpreterFailure(
                InterpreterFailureCategory.INVALID_OUTPUT_FORMAT,
                {"reason": "provider_result_type"},
            )

        payload = result.to_dict()["payload"]
        if not isinstance(payload, dict) or "intent" not in payload:
            return InterpreterFailure(
                InterpreterFailureCategory.INVALID_OUTPUT_FORMAT,
                {"reason": "missing_intent"},
            )
        if set(payload) - self._ALLOWED_PAYLOAD_FIELDS:
            return InterpreterFailure(
                InterpreterFailureCategory.INVALID_OUTPUT_FORMAT,
                {"reason": "unknown_payload_field"},
            )

        try:
            return TaskInterpretationProposal(
                intent=payload["intent"],
                required_capabilities=payload.get("required_capabilities", ()),
                constraints=payload.get("constraints", {}),
                evidence=payload.get("evidence", {}),
            )
        except (TypeError, ValueError):
            return InterpreterFailure(
                InterpreterFailureCategory.INVALID_PROPOSAL,
                {"reason": "proposal_construction"},
            )
