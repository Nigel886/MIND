"""Tests for deterministic M13 provider-response interpretation."""

from __future__ import annotations

import unittest

from src.core.task import Goal, Task
from src.core.task_interpretation import TaskInterpretationProposal
from src.integration.llm_provider import FakeLLMProvider, ProviderFailure, ProviderFailureCategory, ProviderResponse
from src.integration.task_interpreter import (
    InterpreterFailure,
    InterpreterFailureCategory,
    TaskInterpreter,
)


def _task() -> Task:
    return Task(Goal("finish", ("done",)), {"value": "ready"})


class TaskInterpreterTests(unittest.TestCase):
    def test_valid_response_maps_deterministically_to_proposal(self) -> None:
        interpreter = TaskInterpreter(
            FakeLLMProvider(
                ProviderResponse(
                    {
                        "intent": "calculate",
                        "required_capabilities": ["calculator"],
                        "constraints": {"format": "number"},
                        "evidence": {"source": "fake"},
                    },
                ),
            ),
        )

        first = interpreter.interpret(_task())
        second = interpreter.interpret(_task())

        self.assertIsInstance(first, TaskInterpretationProposal)
        self.assertEqual(first, second)
        self.assertEqual(("calculator",), first.required_capabilities)
        self.assertEqual("fake", first.evidence["source"])

    def test_malformed_payload_returns_interpreter_failure(self) -> None:
        interpreter = TaskInterpreter(FakeLLMProvider(ProviderResponse({"unknown": "value"})))

        result = interpreter.interpret(_task())

        self.assertIsInstance(result, InterpreterFailure)
        self.assertEqual(InterpreterFailureCategory.INVALID_OUTPUT_FORMAT, result.category)

    def test_invalid_proposal_construction_returns_interpreter_failure(self) -> None:
        interpreter = TaskInterpreter(FakeLLMProvider(ProviderResponse({"intent": " "})))

        result = interpreter.interpret(_task())

        self.assertIsInstance(result, InterpreterFailure)
        self.assertEqual(InterpreterFailureCategory.INVALID_PROPOSAL, result.category)

    def test_provider_failure_is_preserved_without_interpretation(self) -> None:
        failure = ProviderFailure(ProviderFailureCategory.TIMEOUT, {"outcome": "failure"})
        result = TaskInterpreter(FakeLLMProvider(failure)).interpret(_task())

        self.assertIs(failure, result)

    def test_interpreter_rejects_invalid_boundaries(self) -> None:
        with self.assertRaises(TypeError):
            TaskInterpreter("provider")  # type: ignore[arg-type]
        interpreter = TaskInterpreter(FakeLLMProvider(ProviderResponse({"intent": "direct"})))
        with self.assertRaises(TypeError):
            interpreter.interpret("task")  # type: ignore[arg-type]
