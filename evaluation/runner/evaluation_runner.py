"""Deterministic, evaluation-only execution of configured agent baselines."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from time import perf_counter
from types import MappingProxyType
from typing import Any, Mapping

from evaluation.tasks.evaluation_task import EvaluationScenario
from src.core.agent import GoalDirectedAgent
from src.core.result import AgentResult, AgentStatus
from src.core.task import Task


def _freeze(value: Any) -> Any:
    """Copy compact JSON-compatible values into immutable containers."""

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
    """Return fresh ordinary containers for public serialization."""

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


def _compact_evidence(result: AgentResult) -> tuple[dict[str, Any], ...]:
    """Extract only public decision and execution semantics from AgentResult."""

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
    return tuple(
        {key: record[key] for key in allowed if key in record}
        for record in result.evidence
    )


def _selected_strategy(evidence: tuple[dict[str, Any], ...]) -> str | None:
    for record in evidence:
        if record.get("type") == "meta_inference":
            return record.get("selected_strategy")
    return None


@dataclass(frozen=True)
class EvaluationRunResult:
    """Immutable, compact observable summary of one baseline execution."""

    scenario_name: str
    baseline_name: str
    success: bool
    agent_status: str
    termination_reason: str
    selected_strategy: str | None
    evidence_summary: tuple[dict[str, Any], ...]
    elapsed_time: float
    semantic_signature: dict[str, Any] = field(init=False)

    def __post_init__(self) -> None:
        for value, name in (
            (self.scenario_name, "scenario_name"),
            (self.baseline_name, "baseline_name"),
            (self.agent_status, "agent_status"),
            (self.termination_reason, "termination_reason"),
        ):
            _text(value, name)
        if not isinstance(self.success, bool):
            raise TypeError("success must be a bool")
        if self.selected_strategy is not None:
            _text(self.selected_strategy, "selected_strategy")
        if not isinstance(self.evidence_summary, (tuple, list)):
            raise TypeError("evidence_summary must be an ordered sequence")
        if any(not isinstance(record, dict) for record in self.evidence_summary):
            raise TypeError("evidence_summary records must be dicts")
        if isinstance(self.elapsed_time, bool) or not isinstance(self.elapsed_time, (int, float)):
            raise TypeError("elapsed_time must be a number")
        if not isfinite(self.elapsed_time) or self.elapsed_time < 0:
            raise ValueError("elapsed_time must be a non-negative finite number")

        frozen_evidence = _freeze(tuple(self.evidence_summary))
        object.__setattr__(self, "evidence_summary", frozen_evidence)
        object.__setattr__(self, "elapsed_time", float(self.elapsed_time))
        object.__setattr__(
            self,
            "semantic_signature",
            _freeze(
                {
                    "scenario_name": self.scenario_name,
                    "baseline_name": self.baseline_name,
                    "success": self.success,
                    "agent_status": self.agent_status,
                    "termination_reason": self.termination_reason,
                    "selected_strategy": self.selected_strategy,
                    "evidence_summary": _thaw(frozen_evidence),
                },
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to fresh JSON-compatible containers without hidden state."""

        return {
            "scenario_name": self.scenario_name,
            "baseline_name": self.baseline_name,
            "success": self.success,
            "agent_status": self.agent_status,
            "termination_reason": self.termination_reason,
            "selected_strategy": self.selected_strategy,
            "evidence_summary": _thaw(self.evidence_summary),
            "elapsed_time": self.elapsed_time,
            "semantic_signature": _thaw(self.semantic_signature),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvaluationRunResult":
        """Reconstruct an equivalent compact result summary."""

        if not isinstance(data, dict):
            raise TypeError("EvaluationRunResult data must be a dict")
        result = cls(
            scenario_name=data["scenario_name"],
            baseline_name=data["baseline_name"],
            success=data["success"],
            agent_status=data["agent_status"],
            termination_reason=data["termination_reason"],
            selected_strategy=data["selected_strategy"],
            evidence_summary=data["evidence_summary"],
            elapsed_time=data["elapsed_time"],
        )
        if "semantic_signature" in data and data["semantic_signature"] != _thaw(result.semantic_signature):
            raise ValueError("semantic_signature does not match result semantics")
        return result


class EvaluationRunner:
    """Execute two configured agents without changing their architecture or state."""

    def __init__(
        self,
        baseline_a: GoalDirectedAgent,
        baseline_b: GoalDirectedAgent,
    ) -> None:
        if not isinstance(baseline_a, GoalDirectedAgent):
            raise TypeError("baseline_a must be a GoalDirectedAgent")
        if not isinstance(baseline_b, GoalDirectedAgent):
            raise TypeError("baseline_b must be a GoalDirectedAgent")
        self._baseline_a = baseline_a
        self._baseline_b = baseline_b

    @staticmethod
    def _run_baseline(
        baseline: GoalDirectedAgent,
        baseline_name: str,
        scenario: EvaluationScenario,
        max_cycles: int,
    ) -> EvaluationRunResult:
        task = Task.from_dict(scenario.evaluation_task.task.to_dict())
        started = perf_counter()
        result = baseline.run(task, max_cycles)
        elapsed = perf_counter() - started
        evidence = _compact_evidence(result)
        return EvaluationRunResult(
            scenario_name=scenario.name,
            baseline_name=baseline_name,
            success=result.status is AgentStatus.COMPLETED,
            agent_status=result.status.value,
            termination_reason=result.termination_reason.value,
            selected_strategy=_selected_strategy(evidence),
            evidence_summary=evidence,
            elapsed_time=elapsed,
        )

    def run(
        self,
        scenario: EvaluationScenario,
        max_cycles: int,
    ) -> tuple[EvaluationRunResult, EvaluationRunResult]:
        """Run one immutable scenario once for Baselines A and B, in that order."""

        if not isinstance(scenario, EvaluationScenario):
            raise TypeError("scenario must be an EvaluationScenario")
        if isinstance(max_cycles, bool) or not isinstance(max_cycles, int):
            raise TypeError("max_cycles must be an int, not bool")
        if max_cycles < 0:
            raise ValueError("max_cycles must not be negative")
        return (
            self._run_baseline(self._baseline_a, "baseline_a", scenario, max_cycles),
            self._run_baseline(self._baseline_b, "baseline_b", scenario, max_cycles),
        )
