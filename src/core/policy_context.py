"""Immutable, provider-independent policy decision contracts for M17."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Mapping, Protocol, Sequence

from src.core.observation import Observation
from src.core.environment_outcome import EnvironmentOutcome
from src.core.runtime import RuntimeState
from src.core.task import Task
from src.core.tool import CapabilityDescriptor

if TYPE_CHECKING:
    from src.core.policy import Policy


_FORBIDDEN_POLICY_KEYS = frozenset(
    {
        "expected_answer",
        "ground_truth",
        "correct_tool",
        "correct_action",
        "completion_status",
        "completion_label",
        "evaluator_success",
        "judge_metadata",
        "private_judge_metadata",
        "chain_of_thought",
        "hidden_reasoning",
        "private_prompt",
        "credentials",
        "api_key",
        "exception",
        "traceback",
        "stack_trace",
    },
)


def _freeze_public(value: Any) -> Any:
    """Detach JSON-compatible public data while removing forbidden fields."""

    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("public policy values must be finite JSON values")
        return value
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("public policy mapping keys must be strings")
            if key not in _FORBIDDEN_POLICY_KEYS:
                output[key] = _freeze_public(item)
        return MappingProxyType(output)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_public(item) for item in value)
    raise TypeError("public policy values must be JSON-compatible")


def _thaw_public(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_public(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_public(item) for item in value]
    return value


@dataclass(frozen=True)
class PolicyTaskContext:
    """The public task/goal projection visible to a generalized policy."""

    task_id: str
    goal_description: str
    goal_success_criteria: tuple[str, ...]
    public_input: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        if not isinstance(self.goal_description, str) or not self.goal_description.strip():
            raise ValueError("goal_description must be a non-empty string")
        if isinstance(self.goal_success_criteria, str) or not isinstance(
            self.goal_success_criteria, Sequence,
        ):
            raise TypeError("goal_success_criteria must be a sequence")
        criteria = tuple(self.goal_success_criteria)
        if not criteria or any(not isinstance(item, str) or not item.strip() for item in criteria):
            raise ValueError("goal_success_criteria must contain non-empty strings")
        if not isinstance(self.public_input, dict):
            raise TypeError("public_input must be a dict")
        object.__setattr__(self, "goal_success_criteria", criteria)
        object.__setattr__(self, "public_input", _freeze_public(self.public_input))

    @classmethod
    def from_task(cls, task: Task) -> "PolicyTaskContext":
        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        return cls(
            task_id=str(task.id),
            goal_description=task.goal.description,
            goal_success_criteria=task.goal.success_criteria,
            public_input=task.to_dict()["input"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal_description": self.goal_description,
            "goal_success_criteria": list(self.goal_success_criteria),
            "public_input": _thaw_public(self.public_input),
        }


@dataclass(frozen=True)
class PolicyRuntimeView:
    """A stable, minimal runtime projection with no opaque runtime metadata."""

    belief_version: int
    belief_record_count: int

    def __post_init__(self) -> None:
        if isinstance(self.belief_version, bool) or not isinstance(self.belief_version, int):
            raise TypeError("belief_version must be an int")
        if isinstance(self.belief_record_count, bool) or not isinstance(self.belief_record_count, int):
            raise TypeError("belief_record_count must be an int")
        if self.belief_version < 0 or self.belief_record_count < 0:
            raise ValueError("runtime view values must not be negative")

    @classmethod
    def from_runtime_state(cls, runtime_state: RuntimeState) -> "PolicyRuntimeView":
        if not isinstance(runtime_state, RuntimeState):
            raise TypeError("runtime_state must be a RuntimeState")
        return cls(runtime_state.belief.version, len(runtime_state.belief.state))

    def to_dict(self) -> dict[str, int]:
        return {
            "belief_version": self.belief_version,
            "belief_record_count": self.belief_record_count,
        }


@dataclass(frozen=True)
class PolicyObservationView:
    """The public, sanitized external observation visible to a policy."""

    source: str
    content: Any

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-empty string")
        object.__setattr__(self, "content", _freeze_public(self.content))

    @classmethod
    def from_observation(cls, observation: Observation) -> "PolicyObservationView":
        if not isinstance(observation, Observation):
            raise TypeError("observation must be an Observation")
        if observation.source != "agent_environment":
            raise ValueError("only agent_environment observations are policy-visible")
        if isinstance(observation.content, dict) and "environment_outcome" in observation.content:
            outcome = EnvironmentOutcome.from_observation(observation)
            return cls(observation.source, {"environment_outcome": outcome.to_dict()})
        return cls(observation.source, observation.content)

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "content": _thaw_public(self.content)}


@dataclass(frozen=True)
class PolicyDecisionContext:
    """All and only public, immutable inputs to one generalized policy decision."""

    task: PolicyTaskContext
    runtime: PolicyRuntimeView
    latest_observation: PolicyObservationView | None
    capabilities: tuple[CapabilityDescriptor, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.task, PolicyTaskContext):
            raise TypeError("task must be a PolicyTaskContext")
        if not isinstance(self.runtime, PolicyRuntimeView):
            raise TypeError("runtime must be a PolicyRuntimeView")
        if self.latest_observation is not None and not isinstance(
            self.latest_observation,
            PolicyObservationView,
        ):
            raise TypeError("latest_observation must be a PolicyObservationView or None")
        if isinstance(self.capabilities, list) or not isinstance(self.capabilities, tuple):
            raise TypeError("capabilities must be an ordered tuple")
        if any(not isinstance(item, CapabilityDescriptor) for item in self.capabilities):
            raise TypeError("capabilities must contain CapabilityDescriptor values")

    @classmethod
    def from_runtime(
        cls,
        task: Task,
        runtime_state: RuntimeState,
        latest_observation: Observation | None = None,
        capabilities: tuple[CapabilityDescriptor, ...] = (),
    ) -> "PolicyDecisionContext":
        return cls(
            task=PolicyTaskContext.from_task(task),
            runtime=PolicyRuntimeView.from_runtime_state(runtime_state),
            latest_observation=(
                PolicyObservationView.from_observation(latest_observation)
                if latest_observation is not None
                else None
            ),
            capabilities=capabilities,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.to_dict(),
            "runtime": self.runtime.to_dict(),
            "latest_observation": (
                self.latest_observation.to_dict()
                if self.latest_observation is not None
                else None
            ),
            "capabilities": [item.to_dict() for item in self.capabilities],
        }


class PolicyDecisionEngine(Protocol):
    """Provider-independent, side-effect-free policy decision boundary."""

    def decide(self, context: PolicyDecisionContext) -> "Policy":
        """Return one policy decision without executing or mutating anything."""
