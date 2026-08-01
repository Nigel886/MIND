"""Tests for the provider-independent M13 LLM boundary."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from src.core.task import Goal, Task
from src.integration.llm_provider import (
    FakeLLMProvider,
    LLMProvider,
    ProviderFailure,
    ProviderFailureCategory,
    ProviderResponse,
)


def _task() -> Task:
    return Task(Goal("finish", ("done",)), {"value": "ready"})


class ProviderResponseTests(unittest.TestCase):
    def test_response_is_immutable_serializable_and_detached(self) -> None:
        payload = {"intent": "calculate", "nested": {"items": [1]}}
        response = ProviderResponse(payload)
        payload["nested"]["items"].append(2)

        self.assertEqual((1,), response.payload["nested"]["items"])
        self.assertEqual(response, ProviderResponse.from_dict(response.to_dict()))
        with self.assertRaises(FrozenInstanceError):
            response.payload = {}  # type: ignore[misc]
        with self.assertRaises(TypeError):
            response.payload["intent"] = "other"  # type: ignore[index]

    def test_response_rejects_invalid_payload(self) -> None:
        with self.assertRaises(TypeError):
            ProviderResponse([])  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            ProviderResponse({"unsupported": object()})


class ProviderFailureTests(unittest.TestCase):
    def test_failure_round_trip_and_all_categories(self) -> None:
        for category in ProviderFailureCategory:
            with self.subTest(category=category):
                failure = ProviderFailure(category, {"reason": category.value})
                self.assertEqual(failure, ProviderFailure.from_dict(failure.to_dict()))

    def test_failure_is_immutable_and_detached(self) -> None:
        evidence = {"nested": {"attempt": 1}}
        failure = ProviderFailure(ProviderFailureCategory.TIMEOUT, evidence)
        evidence["nested"]["attempt"] = 2

        self.assertEqual(1, failure.evidence["nested"]["attempt"])
        with self.assertRaises(FrozenInstanceError):
            failure.category = ProviderFailureCategory.UNAVAILABLE  # type: ignore[misc]
        with self.assertRaises(TypeError):
            failure.evidence["nested"] = {}  # type: ignore[index]


class FakeLLMProviderTests(unittest.TestCase):
    def test_fake_provider_returns_fixed_response_without_task_mutation(self) -> None:
        task = _task()
        provider = FakeLLMProvider(ProviderResponse({"intent": "direct"}))

        first = provider.interpret(task)
        second = provider.interpret(task)

        self.assertIsInstance(provider, LLMProvider)
        self.assertEqual(first, second)
        self.assertIs(first, second)
        self.assertEqual(task, Task.from_dict(task.to_dict()))
        self.assertFalse(hasattr(provider, "_task"))

    def test_fake_provider_returns_fixed_failure(self) -> None:
        failure = ProviderFailure(ProviderFailureCategory.UNAVAILABLE, {"outcome": "failure"})
        provider = FakeLLMProvider(failure)

        self.assertEqual(failure, provider.interpret(_task()))

    def test_fake_provider_rejects_invalid_boundary_values(self) -> None:
        with self.assertRaises(TypeError):
            FakeLLMProvider("result")  # type: ignore[arg-type]
        provider = FakeLLMProvider(ProviderResponse({}))
        with self.assertRaises(TypeError):
            provider.interpret("task")  # type: ignore[arg-type]

    def test_provider_module_has_no_agent_or_runtime_dependencies(self) -> None:
        dependencies = LLMProvider.interpret.__annotations__

        self.assertNotIn("Agent", str(dependencies))
        self.assertNotIn("Runtime", str(dependencies))
