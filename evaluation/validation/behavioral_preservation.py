"""Controlled M12 preservation evaluation for delivered Agent behavior."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping

from evaluation.tasks.evaluation_task import EvaluationScenario
from evaluation.tasks.fixtures import get_m12_validation_scenarios
from src.core.agent import GoalDirectedAgent
from src.core.belief import Belief
from src.core.inference_registry import InferenceStrategyRegistry
from src.core.inference_strategy import InferenceStrategy
from src.core.meta_engine import MetaInferenceEngine
from src.core.observation import Observation
from src.core.task import Task
from src.core.tool import ToolRegistry
from src.tools.calculator import CalculatorTool


_M8_BASELINE = "m8_goal_directed_agent"
_META_BASELINE = "m9_meta_inference_agent"
_SCENARIO_IDS = (
    "m12_m8_direct_task",
    "m12_m8_calculator_task",
    "m12_m8_unsupported_task",
    "m12_m8_controlled_failure",
)


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
            raise ValueError("float values must be finite")
        return value
    raise ValueError("values must be JSON-compatible data")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


class _UnexecutedCompatibilityDescriptor:
    """Registry companion that fails if M12 ever attempts strategy execution."""

    def infer(self, observation: Observation, belief: Belief) -> Belief:
        raise AssertionError("behavioral-preservation evaluation must not execute a strategy")


@dataclass(frozen=True)
class M12BehavioralRecord:
    """One compact baseline record with Meta-Inference evidence removed."""

    scenario_id: str
    baseline_name: str
    outcome_signature: dict[str, Any]
    failure_signature: dict[str, Any] | None
    evidence_signature: tuple[dict[str, Any], ...]

    def __post_init__(self) -> None:
        _text(self.scenario_id, "scenario_id")
        _text(self.baseline_name, "baseline_name")
        if not isinstance(self.outcome_signature, dict):
            raise TypeError("outcome_signature must be a dict")
        if set(self.outcome_signature) != {
            "status",
            "termination_reason",
            "cycles_completed",
            "answer",
        }:
            raise ValueError("outcome_signature has an invalid schema")
        if self.failure_signature is not None and not isinstance(self.failure_signature, dict):
            raise TypeError("failure_signature must be a dict or None")
        if not isinstance(self.evidence_signature, (tuple, list)):
            raise TypeError("evidence_signature must be an ordered sequence")
        if any(not isinstance(item, dict) for item in self.evidence_signature):
            raise TypeError("evidence_signature must contain dictionaries")
        object.__setattr__(self, "outcome_signature", _freeze(self.outcome_signature))
        object.__setattr__(self, "failure_signature", _freeze(self.failure_signature))
        object.__setattr__(self, "evidence_signature", _freeze(tuple(self.evidence_signature)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "baseline_name": self.baseline_name,
            "outcome_signature": _thaw(self.outcome_signature),
            "failure_signature": _thaw(self.failure_signature),
            "evidence_signature": _thaw(self.evidence_signature),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "M12BehavioralRecord":
        if not isinstance(data, dict):
            raise TypeError("M12BehavioralRecord data must be a dict")
        return cls(
            scenario_id=data["scenario_id"],
            baseline_name=data["baseline_name"],
            outcome_signature=data["outcome_signature"],
            failure_signature=data["failure_signature"],
            evidence_signature=data["evidence_signature"],
        )


@dataclass(frozen=True)
class M12BehavioralPreservationMetrics:
    """The three frozen RQ4 metrics and no task-performance metric."""

    outcome_preservation: float
    failure_semantic_preservation: float
    deterministic_execution_consistency: float

    def __post_init__(self) -> None:
        values = (
            self.outcome_preservation,
            self.failure_semantic_preservation,
            self.deterministic_execution_consistency,
        )
        if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in values):
            raise TypeError("metric values must be numbers, not bools")
        if any(not isfinite(item) or item < 0 or item > 1 for item in values):
            raise ValueError("metric values must be finite values from 0.0 through 1.0")

    def to_dict(self) -> dict[str, float]:
        return {
            "outcome_preservation": self.outcome_preservation,
            "failure_semantic_preservation": self.failure_semantic_preservation,
            "deterministic_execution_consistency": self.deterministic_execution_consistency,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "M12BehavioralPreservationMetrics":
        if not isinstance(data, dict):
            raise TypeError("M12BehavioralPreservationMetrics data must be a dict")
        return cls(**data)


@dataclass(frozen=True)
class M12BehavioralPreservationResult:
    """Immutable compact comparison of M8 and injected Meta-Inference behavior."""

    scenario_ids: tuple[str, ...]
    repetitions: int
    m8_records: tuple[M12BehavioralRecord, ...]
    meta_inference_records: tuple[M12BehavioralRecord, ...]
    metrics: M12BehavioralPreservationMetrics

    def __post_init__(self) -> None:
        if tuple(self.scenario_ids) != _SCENARIO_IDS:
            raise ValueError("scenario_ids must match the frozen M12 preservation scope")
        if isinstance(self.repetitions, bool) or not isinstance(self.repetitions, int):
            raise TypeError("repetitions must be an int, not bool")
        if self.repetitions < 1:
            raise ValueError("repetitions must be at least one")
        expected_ids = tuple(item for item in _SCENARIO_IDS for _ in range(self.repetitions))
        for records, baseline, name in (
            (self.m8_records, _M8_BASELINE, "m8_records"),
            (self.meta_inference_records, _META_BASELINE, "meta_inference_records"),
        ):
            if not isinstance(records, (tuple, list)):
                raise TypeError(f"{name} must be an ordered sequence")
            if len(records) != len(expected_ids):
                raise ValueError(f"{name} has an invalid record count")
            if any(not isinstance(item, M12BehavioralRecord) for item in records):
                raise TypeError(f"{name} must contain M12BehavioralRecord values")
            if tuple(item.scenario_id for item in records) != expected_ids:
                raise ValueError(f"{name} must be ordered by frozen scenario then repetition")
            if any(item.baseline_name != baseline for item in records):
                raise ValueError(f"{name} has an invalid baseline")
        if not isinstance(self.metrics, M12BehavioralPreservationMetrics):
            raise TypeError("metrics must be an M12BehavioralPreservationMetrics")
        object.__setattr__(self, "scenario_ids", tuple(self.scenario_ids))
        object.__setattr__(self, "m8_records", tuple(self.m8_records))
        object.__setattr__(self, "meta_inference_records", tuple(self.meta_inference_records))

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_ids": list(self.scenario_ids),
            "repetitions": self.repetitions,
            "m8_records": [item.to_dict() for item in self.m8_records],
            "meta_inference_records": [item.to_dict() for item in self.meta_inference_records],
            "metrics": self.metrics.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "M12BehavioralPreservationResult":
        if not isinstance(data, dict):
            raise TypeError("M12BehavioralPreservationResult data must be a dict")
        return cls(
            scenario_ids=tuple(data["scenario_ids"]),
            repetitions=data["repetitions"],
            m8_records=tuple(M12BehavioralRecord.from_dict(item) for item in data["m8_records"]),
            meta_inference_records=tuple(
                M12BehavioralRecord.from_dict(item)
                for item in data["meta_inference_records"]
            ),
            metrics=M12BehavioralPreservationMetrics.from_dict(data["metrics"]),
        )


def _metadata(scenario: EvaluationScenario) -> dict[str, Any]:
    return scenario.to_dict()["metadata"]


def _tools(metadata: dict[str, Any]) -> ToolRegistry:
    registry = ToolRegistry()
    if metadata.get("tool_configuration") != "without_calculator":
        registry.register(CalculatorTool())
    return registry


def _meta_agent(metadata: dict[str, Any]) -> GoalDirectedAgent:
    descriptors = metadata.get("registry_descriptors")
    if descriptors is None:
        # The existing frozen descriptor is sufficient for empty-capability M8
        # compatibility Tasks and is never executed.
        descriptors = [{"name": "calculator_strategy", "capabilities": ["calculator"]}]
    if not isinstance(descriptors, list):
        raise TypeError("registry_descriptors must be a list")
    registry = InferenceStrategyRegistry()
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            raise TypeError("registry_descriptors entries must be dictionaries")
        registry.register(
            InferenceStrategy(
                name=descriptor["name"],
                description=f"frozen M12 descriptor {descriptor['name']}",
                capabilities=descriptor["capabilities"],
            ),
            _UnexecutedCompatibilityDescriptor(),
        )
    return GoalDirectedAgent(_tools(metadata), MetaInferenceEngine(registry))


def _record(
    scenario: EvaluationScenario,
    baseline_name: str,
    agent: GoalDirectedAgent,
) -> M12BehavioralRecord:
    result = agent.run(Task.from_dict(scenario.evaluation_task.task.to_dict()), 1)
    evidence = tuple(
        dict(item)
        for item in result.evidence
        if item.get("type") != "meta_inference"
    )
    outcome = {
        "status": result.status.value,
        "termination_reason": result.termination_reason.value,
        "cycles_completed": result.cycles_completed,
        "answer": result.to_dict()["answer"],
    }
    failure = None
    if result.status.value == "failed":
        failure = {
            "status": result.status.value,
            "termination_reason": result.termination_reason.value,
            "evidence": [item for item in evidence],
        }
    return M12BehavioralRecord(
        scenario_id=scenario.name,
        baseline_name=baseline_name,
        outcome_signature=outcome,
        failure_signature=failure,
        evidence_signature=evidence,
    )


def _frozen_scenarios() -> tuple[EvaluationScenario, ...]:
    scenarios = {item.name: item for item in get_m12_validation_scenarios()}
    return tuple(scenarios[item] for item in _SCENARIO_IDS)


def _records_for(
    records: tuple[M12BehavioralRecord, ...],
    scenario_id: str,
) -> tuple[M12BehavioralRecord, ...]:
    return tuple(item for item in records if item.scenario_id == scenario_id)


def _deterministic(records: tuple[M12BehavioralRecord, ...]) -> float:
    groups = tuple(_records_for(records, item) for item in _SCENARIO_IDS)
    return _rate(
        sum(
            bool(group)
            and all(
                (item.outcome_signature, item.evidence_signature)
                == (group[0].outcome_signature, group[0].evidence_signature)
                for item in group
            )
            for group in groups
        ),
        len(groups),
    )


def _metrics(
    m8_records: tuple[M12BehavioralRecord, ...],
    meta_records: tuple[M12BehavioralRecord, ...],
) -> M12BehavioralPreservationMetrics:
    pairs = tuple(zip(m8_records, meta_records, strict=True))
    failures = tuple(pair for pair in pairs if pair[0].failure_signature is not None)
    return M12BehavioralPreservationMetrics(
        outcome_preservation=_rate(
            sum(left.outcome_signature == right.outcome_signature for left, right in pairs),
            len(pairs),
        ),
        failure_semantic_preservation=_rate(
            sum(left.failure_signature == right.failure_signature for left, right in failures),
            len(failures),
        ),
        deterministic_execution_consistency=_rate(
            int(_deterministic(m8_records) == 1.0)
            + int(_deterministic(meta_records) == 1.0),
            2,
        ),
    )


def evaluate_m12_behavioral_preservation(
    repetitions: int = 3,
) -> M12BehavioralPreservationResult:
    """Compare only frozen M8 compatibility behavior with Meta-Inference injection."""

    if isinstance(repetitions, bool) or not isinstance(repetitions, int):
        raise TypeError("repetitions must be an int, not bool")
    if repetitions < 1:
        raise ValueError("repetitions must be at least one")
    m8_records: list[M12BehavioralRecord] = []
    meta_records: list[M12BehavioralRecord] = []
    for scenario in _frozen_scenarios():
        metadata = _metadata(scenario)
        for _ in range(repetitions):
            m8_records.append(_record(scenario, _M8_BASELINE, GoalDirectedAgent(_tools(metadata))))
            meta_records.append(_record(scenario, _META_BASELINE, _meta_agent(metadata)))
    ordered_m8 = tuple(m8_records)
    ordered_meta = tuple(meta_records)
    return M12BehavioralPreservationResult(
        scenario_ids=_SCENARIO_IDS,
        repetitions=repetitions,
        m8_records=ordered_m8,
        meta_inference_records=ordered_meta,
        metrics=_metrics(ordered_m8, ordered_meta),
    )
