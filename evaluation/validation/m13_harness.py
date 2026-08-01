"""Deterministic, local-only execution support for frozen M13 fixtures."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping

from evaluation.tasks.m13_fixtures import M13Baseline, M13EvaluationScenario
from src.core.belief import Belief
from src.core.inference_registry import InferenceStrategyRegistry
from src.core.inference_strategy import InferenceStrategy
from src.core.meta_engine import MetaInferenceEngine
from src.core.meta_inference import MetaInferenceDecisionStatus
from src.core.observation import Observation
from src.core.runtime import RuntimeController, RuntimeState
from src.core.task import Task
from src.core.task_interpretation import ValidatedRequirement
from src.core.task_validation import ValidationFailure, validate_proposal
from src.integration.llm_provider import FakeLLMProvider, ProviderFailure
from src.integration.meta_inference_adapter import IntegrationFailure, IntegrationSelected, MetaInferenceAdapter
from src.integration.task_interpreter import InterpreterFailure, TaskInterpreter


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
    raise ValueError("record values must be JSON-compatible")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return deepcopy(value)


def _text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


@dataclass(frozen=True)
class M13EvaluationRecord:
    """Compact semantic output without provider secrets or execution objects."""

    scenario_id: str
    baseline: M13Baseline
    semantic_outcome: str
    failure_category: str | None
    evidence_signature: tuple[dict[str, Any], ...]
    deterministic_signature: dict[str, Any]

    def __post_init__(self) -> None:
        _text(self.scenario_id, "scenario_id")
        if not isinstance(self.baseline, M13Baseline):
            raise TypeError("baseline must be an M13Baseline")
        _text(self.semantic_outcome, "semantic_outcome")
        if self.failure_category is not None:
            _text(self.failure_category, "failure_category")
        if not isinstance(self.evidence_signature, (list, tuple)):
            raise TypeError("evidence_signature must be an ordered sequence")
        if any(not isinstance(item, dict) for item in self.evidence_signature):
            raise TypeError("evidence_signature must contain dictionaries")
        if not isinstance(self.deterministic_signature, dict):
            raise TypeError("deterministic_signature must be a dict")
        object.__setattr__(self, "evidence_signature", _freeze(tuple(self.evidence_signature)))
        object.__setattr__(self, "deterministic_signature", _freeze(self.deterministic_signature))

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "baseline": self.baseline.value,
            "semantic_outcome": self.semantic_outcome,
            "failure_category": self.failure_category,
            "evidence_signature": _thaw(self.evidence_signature),
            "deterministic_signature": _thaw(self.deterministic_signature),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "M13EvaluationRecord":
        if not isinstance(data, dict):
            raise TypeError("M13EvaluationRecord data must be a dict")
        return cls(
            scenario_id=data["scenario_id"], baseline=M13Baseline(data["baseline"]),
            semantic_outcome=data["semantic_outcome"], failure_category=data["failure_category"],
            evidence_signature=tuple(data["evidence_signature"]),
            deterministic_signature=data["deterministic_signature"],
        )


class _NeverExecuteImplementation:
    """Registry companion that proves the evaluation never executes strategies."""

    def infer(self, observation: Observation, belief: Belief) -> Belief:
        raise AssertionError("M13 evaluation infrastructure must not execute strategies")


def _registry(scenario: M13EvaluationScenario) -> InferenceStrategyRegistry:
    registry = InferenceStrategyRegistry()
    for name, capabilities in scenario.strategy_descriptors:
        registry.register(
            InferenceStrategy(name, f"frozen M13 descriptor {name}", capabilities),
            _NeverExecuteImplementation(),
        )
    return registry


def _selection_task(task: Task, capabilities: tuple[str, ...]) -> Task:
    data = task.to_dict()
    data["metadata"]["required_inference_capabilities"] = list(capabilities)
    return Task.from_dict(data)


def _record(
    scenario: M13EvaluationScenario,
    baseline: M13Baseline,
    outcome: str,
    failure: str | None,
    evidence: tuple[dict[str, Any], ...],
    selected_strategy: str | None = None,
) -> M13EvaluationRecord:
    return M13EvaluationRecord(
        scenario_id=scenario.scenario_id,
        baseline=baseline,
        semantic_outcome=outcome,
        failure_category=failure,
        evidence_signature=evidence,
        deterministic_signature={
            "semantic_outcome": outcome,
            "failure_category": failure,
            "selected_strategy": selected_strategy,
        },
    )


class M13EvaluationHarness:
    """Stateless public-API composition for M13 architecture checks only."""

    def execute(
        self,
        scenario: M13EvaluationScenario,
        baseline: M13Baseline | None = None,
        runtime_state: RuntimeState | None = None,
    ) -> M13EvaluationRecord:
        """Execute one frozen condition without tools, Agent, or provider I/O."""

        if not isinstance(scenario, M13EvaluationScenario):
            raise TypeError("scenario must be an M13EvaluationScenario")
        selected_baseline = scenario.baseline if baseline is None else baseline
        if not isinstance(selected_baseline, M13Baseline):
            raise TypeError("baseline must be an M13Baseline or None")
        if runtime_state is not None and not isinstance(runtime_state, RuntimeState):
            raise TypeError("runtime_state must be a RuntimeState or None")
        state = RuntimeController.initialize() if runtime_state is None else runtime_state
        registry = _registry(scenario)

        if selected_baseline is M13Baseline.M12_DETERMINISTIC:
            decision = MetaInferenceEngine(registry).select(
                _selection_task(scenario.task, scenario.baseline_a_capabilities), state,
            )
            status = decision.status.value
            selected = decision.selected_strategy
            outcome = "selected" if decision.status is MetaInferenceDecisionStatus.SELECTED else f"decision_{status}"
            return _record(
                scenario, selected_baseline, outcome, None,
                ({"owner": "meta_inference_engine", "status": status, "selected_strategy": selected},), selected,
            )

        interpreted = TaskInterpreter(FakeLLMProvider(scenario.provider_result)).interpret(scenario.task)
        if isinstance(interpreted, ProviderFailure):
            return _record(
                scenario, selected_baseline, "failure", f"provider:{interpreted.category.value}",
                ({"owner": "provider", "category": interpreted.category.value},),
            )
        if isinstance(interpreted, InterpreterFailure):
            return _record(
                scenario, selected_baseline, "failure", f"interpreter:{interpreted.category.value}",
                ({"owner": "interpreter", "category": interpreted.category.value},),
            )

        validated = validate_proposal(interpreted, scenario.validation_snapshot)
        if isinstance(validated, ValidationFailure):
            return _record(
                scenario, selected_baseline, "failure", f"validation:{validated.category.value}",
                (
                    {"owner": "interpreter", "outcome": "proposal"},
                    {"owner": "validator", "category": validated.category.value},
                ),
            )
        if selected_baseline is M13Baseline.INTERPRETATION_CONTROL:
            return _record(
                scenario, selected_baseline, "validated_requirement", None,
                (
                    {"owner": "interpreter", "outcome": "proposal"},
                    {"owner": "validator", "outcome": "valid"},
                ),
            )

        adapter_snapshot = scenario.validation_snapshot if scenario.adapter_snapshot is None else scenario.adapter_snapshot
        integrated = MetaInferenceAdapter(registry).resolve(
            scenario.task, state, validated, adapter_snapshot,
        )
        if isinstance(integrated, IntegrationSelected):
            selected = integrated.decision.selected_strategy
            return _record(
                scenario, selected_baseline, "selected", None,
                (
                    {"owner": "interpreter", "outcome": "proposal"},
                    {"owner": "validator", "outcome": "valid"},
                    {"owner": "meta_inference_engine", "status": "selected", "selected_strategy": selected},
                    {"owner": "adapter", "outcome": "selected"},
                ), selected,
            )
        if not isinstance(integrated, IntegrationFailure):
            raise AssertionError("adapter must return an M13 integration result")
        return _record(
            scenario, selected_baseline, "failure", f"integration:{integrated.category.value}",
            (
                {"owner": "interpreter", "outcome": "proposal"},
                {"owner": "validator", "outcome": "valid"},
                {"owner": "adapter", "category": integrated.category.value},
            ),
        )

    def execute_repeated(
        self,
        scenario: M13EvaluationScenario,
        repetitions: int = 3,
        baseline: M13Baseline | None = None,
    ) -> tuple[M13EvaluationRecord, ...]:
        """Return ordered independent records without retaining execution state."""

        if isinstance(repetitions, bool) or not isinstance(repetitions, int):
            raise TypeError("repetitions must be an int, not bool")
        if repetitions < 1:
            raise ValueError("repetitions must be at least one")
        return tuple(self.execute(scenario, baseline) for _ in range(repetitions))
