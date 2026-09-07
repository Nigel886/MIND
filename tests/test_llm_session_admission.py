"""Tests for the M13-to-M15 controlled session admission resolver."""

from __future__ import annotations

import unittest

from src.core.inference_registry import InferenceStrategyRegistry
from src.core.inference_strategy import InferenceStrategy
from src.core.runtime import RuntimeController
from src.core.task import Goal, Task
from src.core.task_validation import ValidationFailure, ValidationFailureCategory
from src.integration.llm_provider import (
    FakeLLMProvider,
    ProviderFailure,
    ProviderFailureCategory,
    ProviderResponse,
)
from src.integration.llm_session_admission import M13SessionAdmissionResolver
from src.integration.meta_inference_adapter import IntegrationFailure, IntegrationSelected
from src.integration.task_interpreter import InterpreterFailure, InterpreterFailureCategory, TaskInterpreter


class StubInference:
    def infer(self, observation, belief):
        return belief


def _task() -> Task:
    return Task(Goal("finish", ("return ready",)), {"value": "ready", "expected_answer": "ready"})


def _registry(*capabilities: str) -> InferenceStrategyRegistry:
    registry = InferenceStrategyRegistry()
    if capabilities:
        registry.register(InferenceStrategy("selected", "selected", capabilities), StubInference())
    return registry


class M13SessionAdmissionResolverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.task = _task()
        self.state = RuntimeController.initialize()

    def test_valid_fake_provider_composes_to_integration_selected(self) -> None:
        resolver = M13SessionAdmissionResolver(
            TaskInterpreter(FakeLLMProvider(ProviderResponse({
                "intent": "direct answer", "required_capabilities": ["calculator"],
            }))),
            _registry("calculator"),
        )

        result = resolver(self.task, self.state)

        self.assertIsInstance(result, IntegrationSelected)
        self.assertEqual(result.decision.selected_strategy, "selected")

    def test_existing_provider_interpreter_and_validation_failures_are_preserved(self) -> None:
        provider_failure = ProviderFailure(ProviderFailureCategory.TIMEOUT, {"outcome": "failure"})
        provider = M13SessionAdmissionResolver(TaskInterpreter(FakeLLMProvider(provider_failure)), _registry("calculator"))
        self.assertIs(provider(self.task, self.state), provider_failure)

        malformed = M13SessionAdmissionResolver(
            TaskInterpreter(FakeLLMProvider(ProviderResponse({"unknown": "payload"}))),
            _registry("calculator"),
        )(self.task, self.state)
        self.assertIsInstance(malformed, InterpreterFailure)
        self.assertEqual(malformed.category, InterpreterFailureCategory.INVALID_OUTPUT_FORMAT)

        invalid = M13SessionAdmissionResolver(
            TaskInterpreter(FakeLLMProvider(ProviderResponse({
                "intent": "unknown", "required_capabilities": ["unknown"],
            }))),
            _registry("calculator"),
        )(self.task, self.state)
        self.assertIsInstance(invalid, ValidationFailure)
        self.assertEqual(invalid.category, ValidationFailureCategory.UNSUPPORTED_CAPABILITY)

    def test_adapter_integration_failure_remains_non_success_result(self) -> None:
        result = M13SessionAdmissionResolver(
            TaskInterpreter(FakeLLMProvider(ProviderResponse({"intent": "direct"}))),
            _registry(),
        )(self.task, self.state)

        self.assertIsInstance(result, IntegrationFailure)

    def test_fake_provider_resolution_is_deterministic_and_boundary_validated(self) -> None:
        resolver = M13SessionAdmissionResolver(
            TaskInterpreter(FakeLLMProvider(ProviderResponse({"intent": "direct"}))),
            _registry("calculator"),
        )
        self.assertEqual(resolver(self.task, self.state), resolver(self.task, self.state))
        with self.assertRaises(TypeError):
            M13SessionAdmissionResolver("interpreter", _registry("calculator"))
        with self.assertRaises(TypeError):
            M13SessionAdmissionResolver(TaskInterpreter(FakeLLMProvider(ProviderResponse({"intent": "direct"}))), {})


if __name__ == "__main__":
    unittest.main()
