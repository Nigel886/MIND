"""Unit tests for controlled M9 inference strategy registry behavior."""

from __future__ import annotations

import unittest

from src.core.belief import Belief
from src.core.inference_registry import InferenceStrategyRegistry
from src.core.inference_strategy import InferenceStrategy
from src.core.observation import Observation


class StubImplementation:
    """A protocol-conforming test double that records prohibited invocation."""

    def __init__(self) -> None:
        self.calls = 0

    def infer(self, observation: Observation, belief: Belief) -> Belief:
        self.calls += 1
        return belief


def _strategy(name: str) -> InferenceStrategy:
    return InferenceStrategy(name, f"{name} description", ("evidence",))


class InferenceStrategyRegistryTest(unittest.TestCase):
    """Tests for explicit registration, resolution, isolation, and boundaries."""

    def test_empty_registry(self) -> None:
        registry = InferenceStrategyRegistry()
        self.assertEqual(registry.list_names(), ())

    def test_registers_and_resolves_descriptor_and_implementation(self) -> None:
        registry = InferenceStrategyRegistry()
        strategy = _strategy("append_evidence_v1")
        implementation = StubImplementation()
        registry.register(strategy, implementation)
        self.assertIs(registry.get(strategy.name), strategy)
        self.assertIs(registry.get_implementation(strategy.name), implementation)
        self.assertTrue(registry.contains(strategy.name))

    def test_rejects_invalid_and_duplicate_registration(self) -> None:
        registry = InferenceStrategyRegistry()
        strategy = _strategy("append_evidence_v1")
        registry.register(strategy, StubImplementation())
        with self.assertRaises(TypeError):
            registry.register({}, StubImplementation())
        with self.assertRaises(TypeError):
            registry.register(_strategy("other"), object())
        with self.assertRaises(ValueError):
            registry.register(strategy, StubImplementation())

    def test_unknown_lookup_and_invalid_names_fail_explicitly(self) -> None:
        registry = InferenceStrategyRegistry()
        for lookup in (registry.get, registry.get_implementation):
            with self.assertRaises(LookupError):
                lookup("missing")
        for name in (None, "", " padded "):
            with self.assertRaises((TypeError, ValueError)):
                registry.contains(name)

    def test_names_are_exact_ordered_and_instances_are_isolated(self) -> None:
        first = InferenceStrategyRegistry()
        second = InferenceStrategyRegistry()
        first.register(_strategy("append_evidence_v1"), StubImplementation())
        first.register(_strategy("replace_evidence_v1"), StubImplementation())
        second.register(_strategy("Append_Evidence_V1"), StubImplementation())
        self.assertEqual(first.list_names(), ("append_evidence_v1", "replace_evidence_v1"))
        self.assertEqual(second.list_names(), ("Append_Evidence_V1",))
        self.assertFalse(first.contains("Append_Evidence_V1"))

    def test_registry_never_executes_registered_implementation(self) -> None:
        registry = InferenceStrategyRegistry()
        implementation = StubImplementation()
        registry.register(_strategy("append_evidence_v1"), implementation)
        registry.get("append_evidence_v1")
        registry.get_implementation("append_evidence_v1")
        registry.contains("append_evidence_v1")
        registry.list_names()
        self.assertEqual(implementation.calls, 0)
        for forbidden in ("execute", "select", "score", "discover", "load"):
            self.assertFalse(hasattr(registry, forbidden))


if __name__ == "__main__":
    unittest.main()
