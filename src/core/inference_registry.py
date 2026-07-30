"""Controlled instance-local registry for inference strategy associations."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.core.belief import Belief
from src.core.inference_strategy import InferenceStrategy
from src.core.observation import Observation


@runtime_checkable
class InferenceStrategyImplementation(Protocol):
    """Type contract for a controlled inference implementation."""

    def infer(self, observation: Observation, belief: Belief) -> Belief:
        """Return a new Belief without mutating the supplied inputs."""


def _validate_name(name: object) -> None:
    """Validate an exact stable strategy name without normalizing it."""

    if not isinstance(name, str):
        raise TypeError("strategy name must be a str")
    if not name.strip() or name != name.strip():
        raise ValueError("strategy name must not be empty or padded")


class InferenceStrategyRegistry:
    """Mutable, explicit, instance-scoped strategy and implementation registry."""

    def __init__(self) -> None:
        """Create an empty registry with independent local storage."""

        self._strategies: dict[str, InferenceStrategy] = {}
        self._implementations: dict[str, InferenceStrategyImplementation] = {}

    def register(
        self,
        strategy: InferenceStrategy,
        implementation: InferenceStrategyImplementation,
    ) -> None:
        """Register one descriptor and its controlled implementation."""

        if not isinstance(strategy, InferenceStrategy):
            raise TypeError("strategy must be an InferenceStrategy")
        _validate_name(strategy.name)
        if not isinstance(implementation, InferenceStrategyImplementation):
            raise TypeError("implementation must satisfy InferenceStrategyImplementation")
        if strategy.name in self._strategies:
            raise ValueError(f"duplicate inference strategy: {strategy.name}")
        self._strategies[strategy.name] = strategy
        self._implementations[strategy.name] = implementation

    def get(self, name: str) -> InferenceStrategy:
        """Return the descriptor registered under an exact strategy name."""

        _validate_name(name)
        if name not in self._strategies:
            raise LookupError(f"unknown inference strategy: {name}")
        return self._strategies[name]

    def get_implementation(self, name: str) -> InferenceStrategyImplementation:
        """Return the controlled implementation registered under an exact name."""

        _validate_name(name)
        if name not in self._implementations:
            raise LookupError(f"unknown inference strategy: {name}")
        return self._implementations[name]

    def contains(self, name: str) -> bool:
        """Return whether an exact valid strategy name is registered."""

        _validate_name(name)
        return name in self._strategies

    def list_names(self) -> tuple[str, ...]:
        """Return exact registered names in registration order."""

        return tuple(self._strategies)
