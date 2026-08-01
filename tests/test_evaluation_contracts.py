"""Tests for immutable M14 evaluation interface contracts."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from types import MappingProxyType

from src.core.task import Goal, Task
from src.evaluation.contracts import (
    EvaluationAction,
    EvaluationActionType,
    EvaluationCase,
    EvaluationFeedback,
    EvaluationFeedbackType,
    EvaluationOutcome,
    EvaluationOutcomeType,
    EvaluationTrace,
)


class EvaluationContractsTest(unittest.TestCase):
    """Verify public construction, validation, and serialization contracts."""

    def setUp(self) -> None:
        self.task = Task(Goal("return ready", ("answer is ready",)), {"value": "ready"})

    def test_evaluation_case_is_immutable_and_round_trips(self) -> None:
        environment = {"tool_state": {"items": ["calculator"]}}
        case = EvaluationCase("m14.direct.001", self.task, environment)
        environment["tool_state"]["items"].append("later")

        self.assertEqual(case.to_dict()["environment_config"], {"tool_state": {"items": ["calculator"]}})
        self.assertIsInstance(case.environment_config, MappingProxyType)
        with self.assertRaises(TypeError):
            case.environment_config["new"] = "value"
        with self.assertRaises(FrozenInstanceError):
            case.evaluation_id = "other"

        data = case.to_dict()
        restored = EvaluationCase.from_dict(data)
        data["environment_config"]["tool_state"]["items"].append("mutated")
        self.assertEqual(restored, case)

    def test_action_feedback_and_outcome_round_trip_deterministically(self) -> None:
        action = EvaluationAction(
            EvaluationActionType.TOOL_CALL,
            {"tool_name": "calculator", "parameters": {"operation": "multiply", "operands": [17, 23]}},
        )
        feedback = EvaluationFeedback(EvaluationFeedbackType.TOOL_RESPONSE, {"output": 391})
        outcome = EvaluationOutcome(EvaluationOutcomeType.SUCCESS, {"answer": 391})

        self.assertEqual(EvaluationAction.from_dict(action.to_dict()), action)
        self.assertEqual(EvaluationFeedback.from_dict(feedback.to_dict()), feedback)
        self.assertEqual(EvaluationOutcome.from_dict(outcome.to_dict()), outcome)
        self.assertEqual(action.to_dict(), action.to_dict())

    def test_trace_is_immutable_serializable_and_has_no_input_aliases(self) -> None:
        payload = {"answer": {"values": ["ready"]}}
        usage = {"steps": 1, "tool_calls": 0, "tokens": {"input": 3}}
        trace = EvaluationTrace(
            actions=(EvaluationAction(EvaluationActionType.ANSWER, payload),),
            feedback=(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT, {"task": "ready"}),),
            outcome=EvaluationOutcome(EvaluationOutcomeType.SUCCESS, {"answer": "ready"}),
            resource_usage=usage,
        )
        payload["answer"]["values"].append("later")
        usage["tokens"]["input"] = 99

        self.assertEqual(trace.to_dict()["actions"][0]["payload"], {"answer": {"values": ["ready"]}})
        self.assertEqual(trace.to_dict()["resource_usage"], {"steps": 1, "tool_calls": 0, "tokens": {"input": 3}})
        with self.assertRaises(FrozenInstanceError):
            trace.outcome = EvaluationOutcome(EvaluationOutcomeType.FAILURE)
        with self.assertRaises(TypeError):
            trace.resource_usage["steps"] = 2

        data = trace.to_dict()
        restored = EvaluationTrace.from_dict(data)
        data["resource_usage"]["tokens"]["input"] = 10
        self.assertEqual(restored, trace)

    def test_invalid_values_and_trace_boundary_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            EvaluationCase(" m14.case ", self.task)
        with self.assertRaises(TypeError):
            EvaluationCase("m14.case", {})
        with self.assertRaises(TypeError):
            EvaluationAction("answer")
        with self.assertRaises(ValueError):
            EvaluationAction(EvaluationActionType.TOOL_CALL, {"tool_name": "calculator"})
        with self.assertRaises(ValueError):
            EvaluationAction(EvaluationActionType.TOOL_CALL, {"tool_name": " calculator ", "parameters": {}})
        with self.assertRaises(TypeError):
            EvaluationFeedback("initial_input")
        with self.assertRaises(TypeError):
            EvaluationOutcome("success")
        with self.assertRaises(TypeError):
            EvaluationTrace((), (), EvaluationOutcome(EvaluationOutcomeType.SUCCESS), [])
        with self.assertRaises(ValueError):
            EvaluationTrace(
                (),
                (EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT, {"prompt": "private"}),),
                EvaluationOutcome(EvaluationOutcomeType.FAILURE),
            )

    def test_deserialization_errors_are_explicit(self) -> None:
        with self.assertRaises(TypeError):
            EvaluationCase.from_dict([])
        with self.assertRaises(ValueError):
            EvaluationAction.from_dict({"action_type": "unknown"})
        with self.assertRaises(ValueError):
            EvaluationFeedback.from_dict({"feedback_type": "unknown"})
        with self.assertRaises(ValueError):
            EvaluationOutcome.from_dict({"outcome_type": "unknown"})
        with self.assertRaises(KeyError):
            EvaluationTrace.from_dict({"actions": []})


if __name__ == "__main__":
    unittest.main()
