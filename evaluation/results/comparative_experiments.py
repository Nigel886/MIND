"""Frozen-protocol M10 experiment execution and compact result storage."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from evaluation.metrics.evaluation_metrics import EvaluationMetrics, calculate_metrics
from evaluation.runner.evaluation_runner import EvaluationRunResult, EvaluationRunner
from evaluation.tasks.evaluation_task import EvaluationScenario
from evaluation.tasks.fixtures import get_default_evaluation_scenarios
from src.core.agent import GoalDirectedAgent
from src.core.inference_registry import InferenceStrategyRegistry
from src.core.inference_strategy import InferenceStrategy
from src.core.meta_engine import MetaInferenceEngine
from src.core.tool import ToolRegistry
from src.tools.calculator import CalculatorTool


def _text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


class _NoOpInference:
    """Protocol-local controlled implementation; it is never executed or stored."""

    def infer(self, observation: object, belief: object) -> object:
        return belief


@dataclass(frozen=True)
class ExperimentRun:
    """One compact baseline run identified by a deterministic repetition index."""

    repetition_index: int
    result: EvaluationRunResult

    def __post_init__(self) -> None:
        if isinstance(self.repetition_index, bool) or not isinstance(self.repetition_index, int):
            raise TypeError("repetition_index must be an int, not bool")
        if self.repetition_index < 1:
            raise ValueError("repetition_index must be at least 1")
        if not isinstance(self.result, EvaluationRunResult):
            raise TypeError("result must be an EvaluationRunResult")

    def to_dict(self) -> dict[str, Any]:
        return {"repetition_index": self.repetition_index, "result": self.result.to_dict()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentRun":
        if not isinstance(data, dict):
            raise TypeError("ExperimentRun data must be a dict")
        return cls(data["repetition_index"], EvaluationRunResult.from_dict(data["result"]))


@dataclass(frozen=True)
class ComparativeExperimentResult:
    """Compact immutable results for one frozen scenario and both baselines."""

    scenario_name: str
    baseline_results: tuple[ExperimentRun, ...]
    repetitions: int
    semantic_consistency: dict[str, bool]
    metrics: EvaluationMetrics
    notes: tuple[str, ...] = field(default_factory=lambda: ("observational_protocol_only",))

    def __post_init__(self) -> None:
        _text(self.scenario_name, "scenario_name")
        if isinstance(self.repetitions, bool) or not isinstance(self.repetitions, int):
            raise TypeError("repetitions must be an int, not bool")
        if self.repetitions < 3:
            raise ValueError("repetitions must be at least 3")
        if not isinstance(self.baseline_results, (tuple, list)):
            raise TypeError("baseline_results must be an ordered sequence")
        runs = tuple(self.baseline_results)
        if len(runs) != self.repetitions * 2 or any(not isinstance(run, ExperimentRun) for run in runs):
            raise ValueError("baseline_results must contain two ExperimentRuns per repetition")
        if any(run.result.scenario_name != self.scenario_name for run in runs):
            raise ValueError("all baseline results must match scenario_name")
        expected = tuple(
            (index, baseline)
            for index in range(1, self.repetitions + 1)
            for baseline in ("baseline_a", "baseline_b")
        )
        actual = tuple((run.repetition_index, run.result.baseline_name) for run in runs)
        if actual != expected:
            raise ValueError("baseline results must be ordered by repetition, baseline A, baseline B")
        if not isinstance(self.semantic_consistency, dict):
            raise TypeError("semantic_consistency must be a dict")
        if set(self.semantic_consistency) != {"baseline_a", "baseline_b"}:
            raise ValueError("semantic_consistency must contain both baseline names")
        if any(not isinstance(value, bool) for value in self.semantic_consistency.values()):
            raise TypeError("semantic_consistency values must be bools")
        if not isinstance(self.metrics, EvaluationMetrics):
            raise TypeError("metrics must be EvaluationMetrics")
        if self.metrics.total_runs != len(runs):
            raise ValueError("metrics total_runs must match baseline_results")
        if not isinstance(self.notes, (tuple, list)) or any(not isinstance(note, str) or not note.strip() for note in self.notes):
            raise TypeError("notes must be a sequence of non-empty strings")
        object.__setattr__(self, "baseline_results", runs)
        object.__setattr__(self, "semantic_consistency", MappingProxyType(dict(self.semantic_consistency)))
        object.__setattr__(self, "notes", tuple(self.notes))

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "baseline_results": [run.to_dict() for run in self.baseline_results],
            "repetitions": self.repetitions,
            "semantic_consistency": _thaw(self.semantic_consistency),
            "metrics": self.metrics.to_dict(),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ComparativeExperimentResult":
        if not isinstance(data, dict):
            raise TypeError("ComparativeExperimentResult data must be a dict")
        return cls(
            scenario_name=data["scenario_name"],
            baseline_results=tuple(ExperimentRun.from_dict(item) for item in data["baseline_results"]),
            repetitions=data["repetitions"],
            semantic_consistency=data["semantic_consistency"],
            metrics=EvaluationMetrics.from_dict(data["metrics"]),
            notes=data["notes"],
        )


def _tool_registry(scenario: EvaluationScenario) -> ToolRegistry:
    registry = ToolRegistry()
    if scenario.metadata.get("tool_configuration") != "without_calculator":
        registry.register(CalculatorTool())
    return registry


def _meta_inference_engine(scenario: EvaluationScenario) -> MetaInferenceEngine:
    registry = InferenceStrategyRegistry()
    if scenario.name == "ambiguous_strategy":
        entries = (
            ("ambiguous_left", ("ambiguous",)),
            ("ambiguous_right", ("ambiguous",)),
        )
    else:
        entries = (("incremental", ("incremental",)),)
    for name, capabilities in entries:
        registry.register(InferenceStrategy(name, name, capabilities), _NoOpInference())
    return MetaInferenceEngine(registry)


def _runner(scenario: EvaluationScenario) -> EvaluationRunner:
    return EvaluationRunner(
        GoalDirectedAgent(_tool_registry(scenario)),
        GoalDirectedAgent(_tool_registry(scenario), _meta_inference_engine(scenario)),
    )


def _max_cycles(scenario: EvaluationScenario) -> int:
    value = scenario.metadata.get("max_cycles", 1)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("fixture max_cycles must be a non-negative int")
    return value


def _consistent(runs: tuple[ExperimentRun, ...], baseline_name: str) -> bool:
    signatures = [
        run.result.semantic_signature
        for run in runs
        if run.result.baseline_name == baseline_name
    ]
    return bool(signatures) and all(signature == signatures[0] for signature in signatures)


def _execute_scenario(
    scenario: EvaluationScenario,
    repetitions: int,
) -> ComparativeExperimentResult:
    runs: list[ExperimentRun] = []
    for index in range(1, repetitions + 1):
        baseline_a, baseline_b = _runner(scenario).run(scenario, _max_cycles(scenario))
        runs.extend((ExperimentRun(index, baseline_a), ExperimentRun(index, baseline_b)))
    ordered = tuple(runs)
    return ComparativeExperimentResult(
        scenario_name=scenario.name,
        baseline_results=ordered,
        repetitions=repetitions,
        semantic_consistency={
            "baseline_a": _consistent(ordered, "baseline_a"),
            "baseline_b": _consistent(ordered, "baseline_b"),
        },
        metrics=calculate_metrics(tuple(run.result for run in ordered)),
    )


def execute_comparative_experiments(
    repetitions: int = 3,
) -> tuple[ComparativeExperimentResult, ...]:
    """Execute every frozen scenario for both baselines under the M10 protocol."""

    if isinstance(repetitions, bool) or not isinstance(repetitions, int):
        raise TypeError("repetitions must be an int, not bool")
    if repetitions < 3:
        raise ValueError("repetitions must be at least 3")
    return tuple(
        _execute_scenario(scenario, repetitions)
        for scenario in get_default_evaluation_scenarios()
    )
