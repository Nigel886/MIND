"""Reproducible engineering benchmarks for the MIND-Lite runtime."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from types import MappingProxyType
import platform
import sys
import time
from typing import Any, Mapping

from src.core.observation import Observation
from src.core.runtime import RuntimeController, RuntimeState


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return deepcopy(value)


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return deepcopy(value)


def _normalize_observation(data: dict[str, Any]) -> dict[str, Any]:
    return {"source": data["source"], "content": deepcopy(data["content"])}


def _normalize_final_state(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize model identity fields while preserving user payload fields."""

    belief = deepcopy(data["belief"])
    normalized_state: dict[str, Any] = {}
    for key, record in belief["state"].items():
        normalized_record = {
            item_key: deepcopy(item_value)
            for item_key, item_value in record.items()
            if item_key != "timestamp"
        }
        evidence = normalized_record.get("evidence")
        if isinstance(evidence, list):
            normalized_record["evidence"] = [
                _normalize_observation(item)
                if isinstance(item, dict)
                and {"id", "timestamp", "source", "content"} <= set(item)
                else deepcopy(item)
                for item in evidence
            ]
        normalized_state[key] = normalized_record
    belief["state"] = normalized_state
    return {
        "observation": _normalize_observation(data["observation"]),
        "belief": belief,
        "metadata": deepcopy(data["metadata"]),
    }


@dataclass(frozen=True)
class RuntimeBenchmarkConfig:
    """Immutable configuration for one finite runtime benchmark workload."""

    scenario: str
    repeats: int
    max_cycles: int
    observation_content: dict[str, Any]
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.scenario, str):
            raise TypeError("scenario must be a str")
        if self.scenario not in {"single_cycle", "bounded_runtime"}:
            raise ValueError("unsupported benchmark scenario")
        for name, value in (("repeats", self.repeats), ("max_cycles", self.max_cycles)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an int, not bool")
            if value < 1:
                raise ValueError(f"{name} must be at least 1")
        if self.scenario == "single_cycle" and self.max_cycles != 1:
            raise ValueError("single_cycle requires max_cycles == 1")
        for name, value in (
            ("observation_content", self.observation_content),
            ("metadata", self.metadata),
        ):
            if not isinstance(value, dict):
                raise TypeError(f"{name} must be a dict")
        object.__setattr__(self, "observation_content", _freeze(self.observation_content))
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "repeats": self.repeats,
            "max_cycles": self.max_cycles,
            "observation_content": _thaw(self.observation_content),
            "metadata": _thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeBenchmarkConfig":
        return cls(**deepcopy(data))


@dataclass(frozen=True)
class RuntimeBenchmarkResult:
    """Immutable structured result of a complete benchmark invocation."""

    scenario: str
    repeats_requested: int
    repeats_completed: int
    max_cycles: int
    durations_seconds: tuple[float, ...]
    initial_belief_version: int
    final_belief_versions: tuple[int, ...]
    final_observation_sources: tuple[str, ...]
    final_actions: tuple[str, ...]
    semantic_signatures: tuple[dict[str, Any], ...]
    semantically_deterministic: bool
    semantic_mismatch_count: int
    environment: dict[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "durations_seconds", tuple(self.durations_seconds))
        object.__setattr__(self, "final_belief_versions", tuple(self.final_belief_versions))
        object.__setattr__(self, "final_observation_sources", tuple(self.final_observation_sources))
        object.__setattr__(self, "final_actions", tuple(self.final_actions))
        object.__setattr__(self, "semantic_signatures", tuple(_freeze(item) for item in self.semantic_signatures))
        object.__setattr__(self, "environment", _freeze(self.environment))

    @property
    def total_duration_seconds(self) -> float:
        return sum(self.durations_seconds)

    @property
    def mean_duration_seconds(self) -> float:
        return self.total_duration_seconds / self.repeats_completed

    @property
    def min_duration_seconds(self) -> float:
        return min(self.durations_seconds)

    @property
    def max_duration_seconds(self) -> float:
        return max(self.durations_seconds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "repeats_requested": self.repeats_requested,
            "repeats_completed": self.repeats_completed,
            "max_cycles": self.max_cycles,
            "durations_seconds": list(self.durations_seconds),
            "total_duration_seconds": self.total_duration_seconds,
            "mean_duration_seconds": self.mean_duration_seconds,
            "min_duration_seconds": self.min_duration_seconds,
            "max_duration_seconds": self.max_duration_seconds,
            "initial_belief_version": self.initial_belief_version,
            "final_belief_versions": list(self.final_belief_versions),
            "final_observation_sources": list(self.final_observation_sources),
            "final_actions": list(self.final_actions),
            "semantic_signatures": [_thaw(item) for item in self.semantic_signatures],
            "semantically_deterministic": self.semantically_deterministic,
            "semantic_mismatch_count": self.semantic_mismatch_count,
            "environment": _thaw(self.environment),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeBenchmarkResult":
        fields = deepcopy(data)
        for key in (
            "total_duration_seconds", "mean_duration_seconds",
            "min_duration_seconds", "max_duration_seconds",
        ):
            fields.pop(key, None)
        return cls(
            durations_seconds=tuple(fields["durations_seconds"]),
            final_belief_versions=tuple(fields["final_belief_versions"]),
            final_observation_sources=tuple(fields["final_observation_sources"]),
            final_actions=tuple(fields["final_actions"]),
            semantic_signatures=tuple(fields["semantic_signatures"]),
            **{key: value for key, value in fields.items() if key not in {
                "durations_seconds", "final_belief_versions",
                "final_observation_sources", "final_actions", "semantic_signatures",
            }},
        )


def _environment() -> dict[str, str]:
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "benchmark_timestamp": datetime.now(timezone.utc).isoformat(),
    }


def run_runtime_benchmark(config: RuntimeBenchmarkConfig) -> RuntimeBenchmarkResult:
    """Run finite real runtime repeats and return structured local measurements."""

    durations: list[float] = []
    versions: list[int] = []
    sources: list[str] = []
    actions: list[str] = []
    signatures: list[dict[str, Any]] = []
    initial_version: int | None = None

    for _ in range(config.repeats):
        state = RuntimeController.initialize(metadata=_thaw(config.metadata))
        observation = Observation(
            source="runtime_benchmark",
            content=_thaw(config.observation_content),
        )
        if initial_version is None:
            initial_version = state.belief.version
        started = time.perf_counter()
        if config.scenario == "single_cycle":
            final_state = RuntimeController.run_cycle(state, observation)
        else:
            final_state = RuntimeController.run(state, observation, config.max_cycles)
        durations.append(time.perf_counter() - started)

        serialized = final_state.to_dict()
        if RuntimeState.from_dict(serialized).to_dict() != serialized:
            raise ValueError("final RuntimeState serialization round trip failed")
        action_content = final_state.observation.content
        if not isinstance(action_content, dict) or "action" not in action_content:
            raise ValueError("final Observation lacks documented action semantics")
        versions.append(final_state.belief.version)
        sources.append(final_state.observation.source)
        actions.append(action_content["action"])
        signatures.append(_normalize_final_state(serialized))

    mismatches = sum(signature != signatures[0] for signature in signatures[1:])
    return RuntimeBenchmarkResult(
        scenario=config.scenario,
        repeats_requested=config.repeats,
        repeats_completed=len(durations),
        max_cycles=config.max_cycles,
        durations_seconds=tuple(durations),
        initial_belief_version=initial_version if initial_version is not None else 0,
        final_belief_versions=tuple(versions),
        final_observation_sources=tuple(sources),
        final_actions=tuple(actions),
        semantic_signatures=tuple(signatures),
        semantically_deterministic=mismatches == 0,
        semantic_mismatch_count=mismatches,
        environment=_environment(),
    )


def main() -> None:
    config = RuntimeBenchmarkConfig(
        scenario="bounded_runtime",
        repeats=3,
        max_cycles=3,
        observation_content={"message": "MIND-Lite runtime benchmark"},
        metadata={"benchmark": "runtime_foundation"},
    )
    print(json.dumps(run_runtime_benchmark(config).to_dict(), indent=2))


if __name__ == "__main__":
    main()
