"""Deterministic, non-analytical execution support for M12 fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from evaluation.tasks.evaluation_task import EvaluationScenario
from src.core.agent import GoalDirectedAgent
from src.core.belief import Belief
from src.core.inference_registry import InferenceStrategyRegistry
from src.core.inference_strategy import InferenceStrategy
from src.core.meta_engine import MetaInferenceEngine
from src.core.meta_inference import MetaInferenceDecisionStatus
from src.core.observation import Observation
from src.core.task import Task
from src.core.tool import ToolRegistry
from src.tools.calculator import CalculatorTool


def _freeze(value: Any) -> Any:
    """Copy JSON-compatible public values into immutable containers."""

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
    """Return fresh ordinary containers for serialization."""

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


def _compact_evidence(evidence: tuple[Mapping[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    """Keep only public decision and execution semantics from Agent evidence."""

    allowed = (
        "type",
        "status",
        "selected_strategy",
        "reason",
        "action",
        "tool_name",
        "success",
        "satisfied",
    )
    return tuple({key: record[key] for key in allowed if key in record} for record in evidence)


class _UnexecutedStrategy:
    """Registry-compatible descriptor companion that must never be invoked."""

    def infer(self, observation: Observation, belief: Belief) -> Belief:
        raise AssertionError("M12 validation must not execute selected strategies")


@dataclass(frozen=True)
class M12ValidationRecord:
    """Immutable compact semantic record for one M12 fixture execution."""

    scenario_id: str
    baseline_name: str
    decision_status: str | None
    selected_strategy: str | None
    evidence_signature: tuple[dict[str, Any], ...]
    execution_signature: dict[str, Any]

    def __post_init__(self) -> None:
        _text(self.scenario_id, "scenario_id")
        _text(self.baseline_name, "baseline_name")
        if self.decision_status is not None:
            if not isinstance(self.decision_status, str):
                raise TypeError("decision_status must be a str or None")
            try:
                status = MetaInferenceDecisionStatus(self.decision_status)
            except ValueError as error:
                raise ValueError("decision_status must be a valid Meta-Inference status") from error
            if status is MetaInferenceDecisionStatus.SELECTED:
                _text(self.selected_strategy, "selected_strategy")
            elif self.selected_strategy is not None:
                raise ValueError("non-selected decisions must not include a strategy")
        elif self.selected_strategy is not None:
            raise ValueError("records without a decision must not include a strategy")

        if not isinstance(self.evidence_signature, (list, tuple)):
            raise TypeError("evidence_signature must be an ordered sequence")
        if any(not isinstance(item, dict) for item in self.evidence_signature):
            raise TypeError("evidence_signature must contain dictionaries")
        if not isinstance(self.execution_signature, dict):
            raise TypeError("execution_signature must be a dict")
        if set(self.execution_signature) != {
            "status",
            "termination_reason",
            "cycles_completed",
            "answer",
        }:
            raise ValueError("execution_signature has an invalid schema")

        object.__setattr__(self, "evidence_signature", _freeze(tuple(self.evidence_signature)))
        object.__setattr__(self, "execution_signature", _freeze(self.execution_signature))

    def to_dict(self) -> dict[str, Any]:
        """Serialize only compact semantic values into fresh containers."""

        return {
            "scenario_id": self.scenario_id,
            "baseline_name": self.baseline_name,
            "decision_status": self.decision_status,
            "selected_strategy": self.selected_strategy,
            "evidence_signature": _thaw(self.evidence_signature),
            "execution_signature": _thaw(self.execution_signature),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "M12ValidationRecord":
        """Reconstruct an equivalent record without accepting hidden objects."""

        if not isinstance(data, dict):
            raise TypeError("M12ValidationRecord data must be a dict")
        return cls(
            scenario_id=data["scenario_id"],
            baseline_name=data["baseline_name"],
            decision_status=data["decision_status"],
            selected_strategy=data["selected_strategy"],
            evidence_signature=data["evidence_signature"],
            execution_signature=data["execution_signature"],
        )


class M12ValidationHarness:
    """Execute frozen M12 fixtures without calculating metrics or conclusions."""

    @staticmethod
    def _scenario_metadata(scenario: EvaluationScenario) -> dict[str, Any]:
        return scenario.to_dict()["metadata"]

    @staticmethod
    def _tool_registry(metadata: dict[str, Any]) -> ToolRegistry:
        registry = ToolRegistry()
        if metadata.get("tool_configuration") != "without_calculator":
            registry.register(CalculatorTool())
        return registry

    @staticmethod
    def _meta_agent(scenario: EvaluationScenario, metadata: dict[str, Any]) -> GoalDirectedAgent:
        descriptors = metadata.get("registry_descriptors", [])
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
                _UnexecutedStrategy(),
            )
        return GoalDirectedAgent(
            M12ValidationHarness._tool_registry(metadata),
            MetaInferenceEngine(registry),
        )

    @staticmethod
    def _m8_agent(metadata: dict[str, Any]) -> GoalDirectedAgent:
        return GoalDirectedAgent(M12ValidationHarness._tool_registry(metadata))

    @staticmethod
    def _record(scenario: EvaluationScenario, baseline_name: str, agent: GoalDirectedAgent, max_cycles: int) -> M12ValidationRecord:
        task = Task.from_dict(scenario.evaluation_task.task.to_dict())
        result = agent.run(task, max_cycles)
        evidence = _compact_evidence(result.evidence)
        decision = next(
            (item for item in evidence if item.get("type") == "meta_inference"),
            None,
        )
        return M12ValidationRecord(
            scenario_id=scenario.name,
            baseline_name=baseline_name,
            decision_status=None if decision is None else decision["status"],
            selected_strategy=None if decision is None else decision["selected_strategy"],
            evidence_signature=evidence,
            execution_signature={
                "status": result.status.value,
                "termination_reason": result.termination_reason.value,
                "cycles_completed": result.cycles_completed,
                "answer": result.to_dict()["answer"],
            },
        )

    def run(self, scenario: EvaluationScenario, max_cycles: int = 1) -> M12ValidationRecord:
        """Execute one frozen fixture once and return its semantic record."""

        if not isinstance(scenario, EvaluationScenario):
            raise TypeError("scenario must be an EvaluationScenario")
        if isinstance(max_cycles, bool) or not isinstance(max_cycles, int):
            raise TypeError("max_cycles must be an int, not bool")
        if max_cycles < 0:
            raise ValueError("max_cycles must not be negative")

        metadata = self._scenario_metadata(scenario)
        if scenario.evaluation_task.category.startswith("meta_inference"):
            return self._record(
                scenario,
                "full_mind_meta_inference",
                self._meta_agent(scenario, metadata),
                max_cycles,
            )
        return self._record(
            scenario,
            "m8_goal_directed_agent",
            self._m8_agent(metadata),
            max_cycles,
        )

    def run_repeated(
        self,
        scenario: EvaluationScenario,
        repetitions: int,
        max_cycles: int = 1,
    ) -> tuple[M12ValidationRecord, ...]:
        """Return ordered repeated semantic records without analysing them."""

        if isinstance(repetitions, bool) or not isinstance(repetitions, int):
            raise TypeError("repetitions must be an int, not bool")
        if repetitions < 1:
            raise ValueError("repetitions must be at least one")
        return tuple(self.run(scenario, max_cycles) for _ in range(repetitions))

    def run_all(
        self,
        scenarios: Iterable[EvaluationScenario],
        max_cycles: int = 1,
    ) -> tuple[M12ValidationRecord, ...]:
        """Execute an ordered fixture collection without calculating any metric."""

        if isinstance(scenarios, (str, bytes)):
            raise TypeError("scenarios must be an iterable of EvaluationScenario")
        try:
            checked = tuple(scenarios)
        except TypeError as error:
            raise TypeError("scenarios must be an iterable of EvaluationScenario") from error
        if any(not isinstance(scenario, EvaluationScenario) for scenario in checked):
            raise TypeError("scenarios must contain only EvaluationScenario values")
        return tuple(self.run(scenario, max_cycles) for scenario in checked)
