"""Opt-in M13 adapter delegating validated selection to the existing engine."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias

from src.core.inference_registry import InferenceStrategyRegistry
from src.core.meta_engine import MetaInferenceEngine
from src.core.meta_inference import MetaInferenceDecision, MetaInferenceDecisionStatus
from src.core.runtime import RuntimeState
from src.core.task import Task
from src.core.task_interpretation import CapabilitySnapshot, ValidatedRequirement


class IntegrationFailureCategory(str, Enum):
    """Explicit adapter failures separate from Provider and Validation failures."""

    TASK_REQUIREMENT_CONFLICT = "task_requirement_conflict"
    SNAPSHOT_STALE = "snapshot_stale"
    META_INFERENCE_UNAVAILABLE = "meta_inference_unavailable"
    META_INFERENCE_REJECTED = "meta_inference_rejected"


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
    """Validate and freeze compact adapter-owned evidence."""

    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict")
    return _freeze_value(value)


@dataclass(frozen=True)
class IntegrationSelected:
    """Immutable adapter success wrapping an existing selected decision."""

    decision: MetaInferenceDecision
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate selected-decision invariants and evidence ownership."""

        if not isinstance(self.decision, MetaInferenceDecision):
            raise TypeError("decision must be a MetaInferenceDecision")
        if self.decision.status is not MetaInferenceDecisionStatus.SELECTED:
            raise ValueError("IntegrationSelected requires a selected decision")
        object.__setattr__(self, "evidence", _freeze_mapping(self.evidence, "evidence"))

    def to_dict(self) -> dict[str, Any]:
        """Serialize success without copying private decision evidence."""

        return {"decision": self.decision.to_dict(), "evidence": _thaw_value(self.evidence)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntegrationSelected":
        """Reconstruct success using the existing decision serialization API."""

        if not isinstance(data, dict):
            raise TypeError("IntegrationSelected data must be a dict")
        return cls(
            decision=MetaInferenceDecision.from_dict(data["decision"]),
            evidence=data.get("evidence", {}),
        )


@dataclass(frozen=True)
class IntegrationFailure:
    """Immutable explicit adapter failure without fallback behavior."""

    category: IntegrationFailureCategory
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate failure data and detach nested caller-owned evidence."""

        if not isinstance(self.category, IntegrationFailureCategory):
            raise TypeError("category must be an IntegrationFailureCategory")
        object.__setattr__(self, "evidence", _freeze_mapping(self.evidence, "evidence"))

    def to_dict(self) -> dict[str, Any]:
        """Serialize failure data to fresh ordinary containers."""

        return {"category": self.category.value, "evidence": _thaw_value(self.evidence)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntegrationFailure":
        """Reconstruct explicit failure data without coercing malformed input."""

        if not isinstance(data, dict):
            raise TypeError("IntegrationFailure data must be a dict")
        try:
            category = IntegrationFailureCategory(data["category"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid IntegrationFailure category") from error
        return cls(category=category, evidence=data.get("evidence", {}))


IntegrationResult: TypeAlias = IntegrationSelected | IntegrationFailure


class MetaInferenceAdapter:
    """Validate integration boundaries then delegate selection to M9 engine."""

    def __init__(self, registry: InferenceStrategyRegistry) -> None:
        """Keep one controlled registry association without mutating it."""

        if not isinstance(registry, InferenceStrategyRegistry):
            raise TypeError("registry must be an InferenceStrategyRegistry")
        self._registry = registry

    def _current_snapshot(self) -> CapabilitySnapshot:
        """Build a descriptor-only snapshot through the Registry public API."""

        return CapabilitySnapshot(
            tuple(
                (name, self._registry.get(name).capabilities)
                for name in self._registry.list_names()
            ),
        )

    def resolve(
        self,
        task: Task,
        runtime_state: RuntimeState,
        requirement: ValidatedRequirement,
        snapshot: CapabilitySnapshot,
    ) -> IntegrationResult:
        """Return selected delegation result or explicit non-selection failure."""

        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        if not isinstance(runtime_state, RuntimeState):
            raise TypeError("runtime_state must be a RuntimeState")
        if not isinstance(requirement, ValidatedRequirement):
            raise TypeError("requirement must be a ValidatedRequirement")
        if not isinstance(snapshot, CapabilitySnapshot):
            raise TypeError("snapshot must be a CapabilitySnapshot")

        if self._current_snapshot() != snapshot:
            return IntegrationFailure(
                IntegrationFailureCategory.SNAPSHOT_STALE,
                {"outcome": "failure"},
            )

        task_data = task.to_dict()
        metadata = task_data["metadata"]
        existing = metadata.get("required_inference_capabilities")
        if existing is not None:
            if isinstance(existing, str) or not isinstance(existing, (list, tuple)):
                return IntegrationFailure(
                    IntegrationFailureCategory.TASK_REQUIREMENT_CONFLICT,
                    {"outcome": "failure"},
                )
            if tuple(existing) != requirement.required_capabilities:
                return IntegrationFailure(
                    IntegrationFailureCategory.TASK_REQUIREMENT_CONFLICT,
                    {"outcome": "failure"},
                )
        else:
            metadata["required_inference_capabilities"] = list(requirement.required_capabilities)

        selection_view = Task.from_dict(task_data)
        decision = MetaInferenceEngine(self._registry).select(selection_view, runtime_state)
        if decision.status is MetaInferenceDecisionStatus.SELECTED:
            return IntegrationSelected(
                decision,
                {"outcome": "selected", "selected_strategy": decision.selected_strategy},
            )
        if decision.status is MetaInferenceDecisionStatus.UNAVAILABLE:
            return IntegrationFailure(
                IntegrationFailureCategory.META_INFERENCE_UNAVAILABLE,
                {"outcome": "failure", "decision_status": decision.status.value},
            )
        return IntegrationFailure(
            IntegrationFailureCategory.META_INFERENCE_REJECTED,
            {"outcome": "failure", "decision_status": decision.status.value},
        )
