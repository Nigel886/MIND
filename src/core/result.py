"""Immutable task-level result and completion value models."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Sequence
from uuid import UUID

from src.core.runtime import RuntimeState


class AgentStatus(str, Enum):
    """Terminal task-level outcome classifications."""

    COMPLETED = "completed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


class TerminationReason(str, Enum):
    """Approved M8 reasons for a terminal task outcome."""

    GOAL_SATISFIED = "goal_satisfied"
    MAX_CYCLES_REACHED = "max_cycles_reached"
    UNSUPPORTED_TASK = "unsupported_task"
    TOOL_FAILURE = "tool_failure"
    POLICY_FAILURE = "policy_failure"


_VALID_REASONS = {
    AgentStatus.COMPLETED: {TerminationReason.GOAL_SATISFIED},
    AgentStatus.INCOMPLETE: {TerminationReason.MAX_CYCLES_REACHED},
    AgentStatus.FAILED: {
        TerminationReason.UNSUPPORTED_TASK,
        TerminationReason.TOOL_FAILURE,
        TerminationReason.POLICY_FAILURE,
    },
}


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("mapping keys must be strings")
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return deepcopy(value)


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return sorted((_thaw(item) for item in value), key=repr)
    return deepcopy(value)


def _contains_runtime_state(value: Any) -> bool:
    if isinstance(value, RuntimeState):
        return True
    if isinstance(value, Mapping):
        return any(_contains_runtime_state(item) for item in value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_runtime_state(item) for item in value)
    return False


def _freeze_evidence(value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("evidence must be an ordered sequence of dictionaries")
    records: list[Mapping[str, Any]] = []
    for record in value:
        if not isinstance(record, dict):
            raise TypeError("each evidence record must be a dict")
        if _contains_runtime_state(record):
            raise ValueError("evidence must not contain RuntimeState")
        records.append(_freeze(record))
    return tuple(records)


def _validate_cycles(value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("cycles_completed must be an int, not bool")
    if value < 0:
        raise ValueError("cycles_completed must not be negative")


@dataclass(frozen=True)
class CompletionDecision:
    """Immutable intermediate result of deterministic completion evaluation."""

    is_satisfied: bool
    answer: Any | None = None
    evidence: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.is_satisfied, bool):
            raise TypeError("is_satisfied must be a bool")
        if self.is_satisfied and self.answer is None:
            raise ValueError("satisfied decisions require an answer")
        object.__setattr__(self, "answer", _freeze(self.answer))
        object.__setattr__(self, "evidence", _freeze_evidence(self.evidence))

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_satisfied": self.is_satisfied,
            "answer": _thaw(self.answer),
            "evidence": _thaw(self.evidence),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CompletionDecision":
        if not isinstance(data, dict):
            raise TypeError("CompletionDecision data must be a dict")
        return cls(
            is_satisfied=data["is_satisfied"],
            answer=data["answer"],
            evidence=data["evidence"],
        )


@dataclass(frozen=True)
class AgentResult:
    """Immutable terminal result returned by a future goal-directed Agent."""

    task_id: UUID
    status: AgentStatus
    answer: Any | None
    final_state: RuntimeState | None
    termination_reason: TerminationReason
    cycles_completed: int
    evidence: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, UUID):
            raise TypeError("task_id must be a UUID")
        if not isinstance(self.status, AgentStatus):
            raise TypeError("status must be an AgentStatus")
        if not isinstance(self.termination_reason, TerminationReason):
            raise TypeError("termination_reason must be a TerminationReason")
        if self.termination_reason not in _VALID_REASONS[self.status]:
            raise ValueError("status and termination_reason are inconsistent")
        _validate_cycles(self.cycles_completed)
        if self.final_state is not None and not isinstance(self.final_state, RuntimeState):
            raise TypeError("final_state must be a RuntimeState or None")
        if self.status is AgentStatus.COMPLETED:
            if self.answer is None:
                raise ValueError("completed results require an answer")
            if self.final_state is None:
                raise ValueError("completed results require a final_state")
        if self.status is AgentStatus.INCOMPLETE and self.final_state is None:
            raise ValueError("incomplete results require a final_state")
        object.__setattr__(self, "answer", _freeze(self.answer))
        object.__setattr__(self, "evidence", _freeze_evidence(self.evidence))
        if not isinstance(self.metadata, dict):
            raise TypeError("metadata must be a dict")
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": str(self.task_id),
            "status": self.status.value,
            "answer": _thaw(self.answer),
            "final_state": self.final_state.to_dict() if self.final_state else None,
            "termination_reason": self.termination_reason.value,
            "cycles_completed": self.cycles_completed,
            "evidence": _thaw(self.evidence),
            "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentResult":
        if not isinstance(data, dict):
            raise TypeError("AgentResult data must be a dict")
        try:
            task_id = UUID(data["task_id"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid task_id") from error
        try:
            status = AgentStatus(data["status"])
            reason = TerminationReason(data["termination_reason"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid status or termination_reason") from error
        final_state_data = data["final_state"]
        final_state = RuntimeState.from_dict(final_state_data) if final_state_data is not None else None
        return cls(
            task_id=task_id,
            status=status,
            answer=data["answer"],
            final_state=final_state,
            termination_reason=reason,
            cycles_completed=data["cycles_completed"],
            evidence=data["evidence"],
            metadata=data["metadata"],
        )
