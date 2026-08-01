"""Frozen deterministic fixtures for the M13 architecture evaluation protocol."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping
from uuid import UUID

from src.core.task import Goal, Task
from src.core.task_interpretation import CapabilitySnapshot
from src.integration.llm_provider import (
    ProviderFailure,
    ProviderFailureCategory,
    ProviderResponse,
)


class M13Baseline(str, Enum):
    """The three controlled conditions frozen by the M13 protocol."""

    M12_DETERMINISTIC = "m12_deterministic_meta_inference"
    INTERPRETATION_CONTROL = "llm_interpretation_control"
    FULL_PIPELINE = "full_m13_pipeline"


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("mapping keys must be strings")
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("floats must be finite")
        return value
    raise ValueError("values must be JSON-compatible")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return deepcopy(value)


def _text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value.strip() or value != value.strip():
        raise ValueError(f"{name} must not be empty or padded")


def _descriptor_pairs(value: Any) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Validate ordered public descriptor data without implementations."""

    if not isinstance(value, (list, tuple)):
        raise TypeError("strategy_descriptors must be a list or tuple")
    snapshot = CapabilitySnapshot(value)
    return snapshot.strategy_capabilities


def _provider_to_dict(result: ProviderResponse | ProviderFailure) -> dict[str, Any]:
    if isinstance(result, ProviderResponse):
        return {"kind": "response", "value": result.to_dict()}
    if isinstance(result, ProviderFailure):
        return {"kind": "failure", "value": result.to_dict()}
    raise TypeError("provider_result must be a ProviderResponse or ProviderFailure")


def _provider_from_dict(data: dict[str, Any]) -> ProviderResponse | ProviderFailure:
    if not isinstance(data, dict):
        raise TypeError("provider_result data must be a dict")
    if data.get("kind") == "response":
        return ProviderResponse.from_dict(data["value"])
    if data.get("kind") == "failure":
        return ProviderFailure.from_dict(data["value"])
    raise ValueError("provider_result kind is invalid")


@dataclass(frozen=True)
class M13EvaluationScenario:
    """Immutable, serializable input and expected outcome for one M13 check."""

    scenario_id: str
    baseline: M13Baseline
    task: Task
    provider_result: ProviderResponse | ProviderFailure
    strategy_descriptors: tuple[tuple[str, tuple[str, ...]], ...]
    validation_snapshot: CapabilitySnapshot
    expected_outcome: str
    expected_failure_category: str | None = None
    expected_selected_strategy: str | None = None
    adapter_snapshot: CapabilitySnapshot | None = None
    baseline_a_capabilities: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _text(self.scenario_id, "scenario_id")
        if not isinstance(self.baseline, M13Baseline):
            raise TypeError("baseline must be an M13Baseline")
        if not isinstance(self.task, Task):
            raise TypeError("task must be a Task")
        if not isinstance(self.provider_result, (ProviderResponse, ProviderFailure)):
            raise TypeError("provider_result must be a ProviderResponse or ProviderFailure")
        object.__setattr__(self, "strategy_descriptors", _descriptor_pairs(self.strategy_descriptors))
        if not isinstance(self.validation_snapshot, CapabilitySnapshot):
            raise TypeError("validation_snapshot must be a CapabilitySnapshot")
        if self.adapter_snapshot is not None and not isinstance(self.adapter_snapshot, CapabilitySnapshot):
            raise TypeError("adapter_snapshot must be a CapabilitySnapshot or None")
        _text(self.expected_outcome, "expected_outcome")
        if self.expected_failure_category is not None:
            _text(self.expected_failure_category, "expected_failure_category")
        if self.expected_selected_strategy is not None:
            _text(self.expected_selected_strategy, "expected_selected_strategy")
        if not isinstance(self.baseline_a_capabilities, (list, tuple)):
            raise TypeError("baseline_a_capabilities must be a list or tuple")
        capabilities = tuple(self.baseline_a_capabilities)
        if any(not isinstance(item, str) or not item.strip() or item != item.strip() for item in capabilities):
            raise ValueError("baseline_a_capabilities must contain unpadded non-empty strings")
        if len(set(capabilities)) != len(capabilities):
            raise ValueError("baseline_a_capabilities must not contain duplicates")
        if not isinstance(self.metadata, dict):
            raise TypeError("metadata must be a dict")
        object.__setattr__(self, "baseline_a_capabilities", capabilities)
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize fixtures using only ordinary, public containers."""

        return {
            "scenario_id": self.scenario_id,
            "baseline": self.baseline.value,
            "task": self.task.to_dict(),
            "provider_result": _provider_to_dict(self.provider_result),
            "strategy_descriptors": [
                {"name": name, "capabilities": list(capabilities)}
                for name, capabilities in self.strategy_descriptors
            ],
            "validation_snapshot": self.validation_snapshot.to_dict(),
            "expected_outcome": self.expected_outcome,
            "expected_failure_category": self.expected_failure_category,
            "expected_selected_strategy": self.expected_selected_strategy,
            "adapter_snapshot": None if self.adapter_snapshot is None else self.adapter_snapshot.to_dict(),
            "baseline_a_capabilities": list(self.baseline_a_capabilities),
            "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "M13EvaluationScenario":
        """Reconstruct one fixture without interpreting its provider output."""

        if not isinstance(data, dict):
            raise TypeError("M13EvaluationScenario data must be a dict")
        descriptors = data["strategy_descriptors"]
        if not isinstance(descriptors, list):
            raise TypeError("strategy_descriptors data must be a list")
        pairs = tuple((item["name"], item["capabilities"]) for item in descriptors)
        adapter_data = data.get("adapter_snapshot")
        return cls(
            scenario_id=data["scenario_id"],
            baseline=M13Baseline(data["baseline"]),
            task=Task.from_dict(data["task"]),
            provider_result=_provider_from_dict(data["provider_result"]),
            strategy_descriptors=pairs,
            validation_snapshot=CapabilitySnapshot.from_dict(data["validation_snapshot"]),
            expected_outcome=data["expected_outcome"],
            expected_failure_category=data.get("expected_failure_category"),
            expected_selected_strategy=data.get("expected_selected_strategy"),
            adapter_snapshot=None if adapter_data is None else CapabilitySnapshot.from_dict(adapter_data),
            baseline_a_capabilities=tuple(data.get("baseline_a_capabilities", ())),
            metadata=data.get("metadata", {}),
        )


_CALCULATOR = (("calculator_strategy", ("calculator",)),)
_SNAPSHOT = CapabilitySnapshot(_CALCULATOR)
_EMPTY_SNAPSHOT = CapabilitySnapshot(())


def _task(index: int, *, required: tuple[str, ...] | None = None) -> Task:
    metadata = {} if required is None else {"required_inference_capabilities": list(required)}
    return Task(
        goal=Goal("Validate controlled M13 semantics", ("preserve the frozen outcome",)),
        input={"value": "ready"},
        metadata=metadata,
        id=UUID(f"13000000-0000-0000-0000-{index:012d}"),
    )


def _response(capabilities: list[str], constraints: dict[str, Any] | None = None) -> ProviderResponse:
    return ProviderResponse(
        {
            "intent": "interpret_task",
            "required_capabilities": capabilities,
            "constraints": {} if constraints is None else constraints,
            "evidence": {"fixture": "m13"},
        },
    )


def get_m13_evaluation_scenarios() -> tuple[M13EvaluationScenario, ...]:
    """Return fresh, ordered, non-executing M13 protocol fixtures."""

    scenarios = (
        M13EvaluationScenario(
            "m13_valid_task_interpretation", M13Baseline.INTERPRETATION_CONTROL,
            _task(1), _response(["calculator"]), _CALCULATOR, _SNAPSHOT,
            "validated_requirement", baseline_a_capabilities=("calculator",),
            metadata={"protocol_version": "M13-v1", "category": "interpretation"},
        ),
        M13EvaluationScenario(
            "m13_malformed_provider_payload", M13Baseline.INTERPRETATION_CONTROL,
            _task(2), ProviderResponse({"unknown": "value"}), _CALCULATOR, _SNAPSHOT,
            "failure", "interpreter:invalid_output_format",
            metadata={"protocol_version": "M13-v1", "category": "interpretation"},
        ),
        M13EvaluationScenario(
            "m13_unsupported_capability", M13Baseline.INTERPRETATION_CONTROL,
            _task(3), _response(["unknown"]), _CALCULATOR, _SNAPSHOT,
            "failure", "validation:unsupported_capability",
            metadata={"protocol_version": "M13-v1", "category": "validation"},
        ),
        M13EvaluationScenario(
            "m13_invalid_constraint_validation_rejection", M13Baseline.INTERPRETATION_CONTROL,
            _task(4), _response(["calculator"], {"nested": {" ": "invalid"}}),
            _CALCULATOR, _SNAPSHOT, "failure", "validation:invalid_constraint",
            metadata={"protocol_version": "M13-v1", "category": "validation"},
        ),
        M13EvaluationScenario(
            "m13_successful_complete_pipeline", M13Baseline.FULL_PIPELINE,
            _task(5), _response(["calculator"]), _CALCULATOR, _SNAPSHOT,
            "selected", expected_selected_strategy="calculator_strategy",
            baseline_a_capabilities=("calculator",),
            metadata={"protocol_version": "M13-v1", "category": "integration"},
        ),
        M13EvaluationScenario(
            "m13_provider_failure_propagation", M13Baseline.INTERPRETATION_CONTROL,
            _task(6), ProviderFailure(ProviderFailureCategory.TIMEOUT, {"outcome": "failure"}),
            _CALCULATOR, _SNAPSHOT, "failure", "provider:timeout",
            metadata={"protocol_version": "M13-v1", "category": "failure"},
        ),
        M13EvaluationScenario(
            "m13_snapshot_stale_rejection", M13Baseline.FULL_PIPELINE,
            _task(7), _response(["calculator"]), _CALCULATOR, _SNAPSHOT,
            "failure", "integration:snapshot_stale", adapter_snapshot=_EMPTY_SNAPSHOT,
            metadata={"protocol_version": "M13-v1", "category": "integration"},
        ),
        M13EvaluationScenario(
            "m13_task_requirement_conflict", M13Baseline.FULL_PIPELINE,
            _task(8, required=("other",)), _response(["calculator"]), _CALCULATOR, _SNAPSHOT,
            "failure", "integration:task_requirement_conflict",
            metadata={"protocol_version": "M13-v1", "category": "integration"},
        ),
    )
    expected = (
        "m13_valid_task_interpretation", "m13_malformed_provider_payload",
        "m13_unsupported_capability", "m13_invalid_constraint_validation_rejection",
        "m13_successful_complete_pipeline", "m13_provider_failure_propagation",
        "m13_snapshot_stale_rejection", "m13_task_requirement_conflict",
    )
    if tuple(item.scenario_id for item in scenarios) != expected:
        raise RuntimeError("M13 fixture order must remain frozen")
    return scenarios
