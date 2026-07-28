"""RuntimeState model and RuntimeController for the MIND-Lite runtime subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from src.core.belief import Belief
from src.core.inference import InferenceEngine
from src.core.observation import Observation
from src.core.action import ActionExecutor
from src.core.policy import PolicyEngine


def _serialize_metadata_value(value: Any) -> Any:
    """Recursively serialize runtime metadata values.

    Metadata is treated as an opaque container during the prototype
    stage. This helper preserves that design by avoiding schema
    validation while still supporting serialization of common nested
    values.

    Args:
        value: Runtime metadata value to serialize.

    Returns:
        A serialized representation of the metadata value.
    """

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            key: _serialize_metadata_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_serialize_metadata_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_metadata_value(item) for item in value]
    return value


@dataclass(frozen=True)
class RuntimeState:
    """Represents the immutable runtime state for the prototype.

    RuntimeState is a passive data container. It stores the current
    observation, the current belief, and opaque runtime metadata. It
    intentionally exposes no convenience APIs for orchestration or
    lifecycle management.

    Attributes:
        observation: Current immutable observation.
        belief: Current immutable belief state.
        metadata: Opaque runtime metadata container for the prototype.
    """

    observation: Observation
    belief: Belief
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the runtime state to a dictionary.

        Nested serialization is delegated to the Observation and Belief
        models to keep the serialization strategy consistent across the
        core runtime models.

        Returns:
            A dictionary representation of the runtime state.
        """

        return {
            "observation": self.observation.to_dict(),
            "belief": self.belief.to_dict(),
            "metadata": _serialize_metadata_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeState":
        """Deserialize a runtime state from a dictionary.

        Nested reconstruction is delegated to the Observation and Belief
        models to keep the reconstruction strategy consistent across the
        core runtime models.

        Args:
            data: Serialized runtime state data.

        Returns:
            A reconstructed runtime state instance.
        """

        return cls(
            observation=Observation.from_dict(data["observation"]),
            belief=Belief.from_dict(data["belief"]),
            metadata=dict(data["metadata"]),
        )


class RuntimeController:
    """Manages the MIND-Lite runtime state lifecycle.

    RuntimeController is a stateless behavior component responsible
    for creating and updating RuntimeState instances. It coordinates
    RuntimeState and future runtime components while maintaining
    strict separation of state and behavior.

    RuntimeController never stores internal state. Every call to
    initialize() or update() constructs and returns a new RuntimeState
    instance.
    """

    @staticmethod
    def initialize(
        observation: Optional[Observation] = None,
        belief: Optional[Belief] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> RuntimeState:
        """Creates an initial RuntimeState instance.

        If no Observation or Belief is provided, default instances are
        created using their respective constructors. Metadata defaults
        to an empty dictionary when not provided.

        Args:
            observation: Optional initial immutable observation.
            belief: Optional initial immutable belief state.
            metadata: Optional opaque runtime metadata.

        Returns:
            A newly constructed immutable RuntimeState instance.
        """

        if observation is None:
            observation = Observation(
                source="",
                content=None,
            )

        if belief is None:
            belief = Belief(
                state={},
                confidence={},
                version=0,
            )

        if metadata is None:
            metadata = {}

        return RuntimeState(
            observation=observation,
            belief=belief,
            metadata=metadata,
        )

    @staticmethod
    def update(
        runtime_state: RuntimeState,
        observation: Optional[Observation] = None,
        belief: Optional[Belief] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> RuntimeState:
        """Constructs a new RuntimeState by updating specified components.

        The existing RuntimeState is treated as the source of truth. Only
        the components explicitly provided by the caller are replaced. Any
        None arguments preserve the corresponding value from the existing
        RuntimeState.

        Args:
            runtime_state: The existing immutable runtime state to use as base.
            observation: Optional new immutable observation to replace.
            belief: Optional new immutable belief state to replace.
            metadata: Optional new opaque runtime metadata to replace.

        Returns:
            A newly constructed immutable RuntimeState instance with updated
            components where specified.
        """

        if observation is None:
            observation = runtime_state.observation

        if belief is None:
            belief = runtime_state.belief

        if metadata is None:
            metadata = dict(runtime_state.metadata)

        return RuntimeState(
            observation=observation,
            belief=belief,
            metadata=metadata,
        )

    @staticmethod
    def apply_inference(
        runtime_state: RuntimeState,
        observation: Observation,
    ) -> RuntimeState:
        """Apply inference and return the resulting immutable runtime state.

        The controller coordinates the transition only: belief transformation is
        delegated to ``InferenceEngine``, and state construction is delegated to
        the existing ``update()`` mechanism.

        Args:
            runtime_state: The current immutable runtime state.
            observation: The immutable observation to incorporate.

        Returns:
            A newly constructed runtime state containing the observation and the
            belief produced by ``InferenceEngine.infer()``.
        """

        updated_belief = InferenceEngine.infer(
            observation,
            runtime_state.belief,
        )
        return RuntimeController.update(
            runtime_state,
            observation=observation,
            belief=updated_belief,
        )

    @staticmethod
    def apply_decision(
        runtime_state: RuntimeState,
    ) -> RuntimeState:
        """Apply one decision transition and return a new runtime state.

        Policy generation and action execution remain delegated to their
        dedicated stateless components. The generated Policy is transient, and
        state construction is delegated to the existing ``update()`` mechanism.

        Args:
            runtime_state: The current immutable runtime state.

        Returns:
            A newly constructed runtime state containing the Observation
            returned by ``ActionExecutor.execute()``.

        Raises:
            ValueError: Propagated when ActionExecutor rejects the generated
                Policy action.
        """

        policy = PolicyEngine.generate(runtime_state.belief)
        action_observation = ActionExecutor.execute(policy)
        return RuntimeController.update(
            runtime_state,
            observation=action_observation,
        )

    @staticmethod
    def run_cycle(
        runtime_state: RuntimeState,
        observation: Observation,
    ) -> RuntimeState:
        """Run one inference-and-decision runtime cycle.

        Args:
            runtime_state: The current immutable runtime state.
            observation: The incoming immutable observation for inference.

        Returns:
            The final runtime state returned by decision integration.
        """

        inferred_state = RuntimeController.apply_inference(
            runtime_state,
            observation,
        )
        return RuntimeController.apply_decision(inferred_state)

    @staticmethod
    def run(
        runtime_state: RuntimeState,
        observation: Observation,
        max_cycles: int,
    ) -> RuntimeState:
        """Run a finite number of runtime cycles.

        Args:
            runtime_state: The initial immutable runtime state.
            observation: The initial immutable observation.
            max_cycles: The explicit number of cycles to execute.

        Returns:
            The original state for zero cycles, otherwise the final cycle state.

        Raises:
            TypeError: If max_cycles is not an int or is a bool.
            ValueError: If max_cycles is negative.
        """

        if isinstance(max_cycles, bool) or not isinstance(max_cycles, int):
            raise TypeError("max_cycles must be an int, not bool")
        if max_cycles < 0:
            raise ValueError("max_cycles must not be negative")

        current_state = runtime_state
        current_observation = observation
        for _ in range(max_cycles):
            current_state = RuntimeController.run_cycle(
                current_state,
                current_observation,
            )
            current_observation = current_state.observation
        return current_state
