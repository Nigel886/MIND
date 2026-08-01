"""Tests for M13 validated-requirement delegation to the existing M9 engine."""

from __future__ import annotations

import unittest

from src.core.belief import Belief
from src.core.inference_registry import InferenceStrategyRegistry
from src.core.inference_strategy import InferenceStrategy
from src.core.observation import Observation
from src.core.runtime import RuntimeController
from src.core.task import Goal, Task
from src.core.task_interpretation import CapabilitySnapshot, ValidatedRequirement
from src.integration.meta_inference_adapter import (
    IntegrationFailure,
    IntegrationFailureCategory,
    IntegrationSelected,
    MetaInferenceAdapter,
)


class StubImplementation:
    def __init__(self) -> None:
        self.calls = 0

    def infer(self, observation: Observation, belief: Belief) -> Belief:
        self.calls += 1
        return belief


def _registry(*descriptors: tuple[str, tuple[str, ...]]) -> tuple[InferenceStrategyRegistry, list[StubImplementation]]:
    registry = InferenceStrategyRegistry()
    implementations: list[StubImplementation] = []
    for name, capabilities in descriptors:
        implementation = StubImplementation()
        registry.register(InferenceStrategy(name, name, capabilities), implementation)
        implementations.append(implementation)
    return registry, implementations


def _snapshot(registry: InferenceStrategyRegistry) -> CapabilitySnapshot:
    return CapabilitySnapshot(
        tuple((name, registry.get(name).capabilities) for name in registry.list_names()),
    )


def _task(required: tuple[str, ...] | None = None) -> Task:
    metadata = {} if required is None else {"required_inference_capabilities": list(required)}
    return Task(Goal("finish", ("done",)), {"value": "ready"}, metadata=metadata)


class MetaInferenceAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = RuntimeController.initialize()

    def test_successfully_delegates_to_existing_engine_without_execution(self) -> None:
        registry, implementations = _registry(("calculator", ("calculator",)))
        task = _task()
        state_before = self.state.to_dict()
        result = MetaInferenceAdapter(registry).resolve(
            task,
            self.state,
            ValidatedRequirement(("calculator",)),
            _snapshot(registry),
        )

        self.assertIsInstance(result, IntegrationSelected)
        self.assertEqual("calculator", result.decision.selected_strategy)
        self.assertEqual(0, implementations[0].calls)
        self.assertEqual(task, Task.from_dict(task.to_dict()))
        self.assertEqual(state_before, self.state.to_dict())

    def test_stale_snapshot_refuses_to_call_engine(self) -> None:
        registry, implementations = _registry(("calculator", ("calculator",)))
        stale = CapabilitySnapshot(())
        result = MetaInferenceAdapter(registry).resolve(
            _task(), self.state, ValidatedRequirement(("calculator",)), stale,
        )

        self.assertIsInstance(result, IntegrationFailure)
        self.assertEqual(IntegrationFailureCategory.SNAPSHOT_STALE, result.category)
        self.assertEqual(0, implementations[0].calls)

    def test_task_requirement_conflict_is_rejected(self) -> None:
        registry, implementations = _registry(("calculator", ("calculator",)))
        result = MetaInferenceAdapter(registry).resolve(
            _task(("other",)),
            self.state,
            ValidatedRequirement(("calculator",)),
            _snapshot(registry),
        )

        self.assertIsInstance(result, IntegrationFailure)
        self.assertEqual(IntegrationFailureCategory.TASK_REQUIREMENT_CONFLICT, result.category)
        self.assertEqual(0, implementations[0].calls)

    def test_unavailable_decision_maps_to_integration_failure(self) -> None:
        registry, _ = _registry()
        result = MetaInferenceAdapter(registry).resolve(
            _task(), self.state, ValidatedRequirement(), _snapshot(registry),
        )

        self.assertIsInstance(result, IntegrationFailure)
        self.assertEqual(IntegrationFailureCategory.META_INFERENCE_UNAVAILABLE, result.category)

    def test_rejected_decision_maps_to_integration_failure(self) -> None:
        registry, implementations = _registry(
            ("first", ("calculator",)),
            ("second", ("calculator",)),
        )
        result = MetaInferenceAdapter(registry).resolve(
            _task(), self.state, ValidatedRequirement(("calculator",)), _snapshot(registry),
        )

        self.assertIsInstance(result, IntegrationFailure)
        self.assertEqual(IntegrationFailureCategory.META_INFERENCE_REJECTED, result.category)
        self.assertEqual([0, 0], [item.calls for item in implementations])

    def test_adapter_rejects_invalid_boundaries(self) -> None:
        registry, _ = _registry()
        adapter = MetaInferenceAdapter(registry)
        with self.assertRaises(TypeError):
            adapter.resolve({}, self.state, ValidatedRequirement(), _snapshot(registry))  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            MetaInferenceAdapter({})  # type: ignore[arg-type]
