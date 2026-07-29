"""Tests for immutable AgentResult and CompletionDecision values."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from types import MappingProxyType
from uuid import uuid4

from src.core.result import AgentResult, AgentStatus, CompletionDecision, TerminationReason
from src.core.runtime import RuntimeController


class CompletionDecisionTest(unittest.TestCase):
    def test_valid_decisions_and_serialization(self) -> None:
        satisfied = CompletionDecision(True, {"value": [1]}, ({"kind": "match"},))
        unsatisfied = CompletionDecision(False, None, ())
        self.assertTrue(satisfied.is_satisfied)
        self.assertFalse(unsatisfied.is_satisfied)
        self.assertEqual(CompletionDecision.from_dict(satisfied.to_dict()), satisfied)

    def test_validation_and_alias_protection(self) -> None:
        answer = {"value": [1]}
        evidence = ({"nested": [1]},)
        decision = CompletionDecision(True, answer, evidence)
        answer["value"].append(2)
        evidence[0]["nested"].append(2)
        self.assertEqual(decision.to_dict()["answer"], {"value": [1]})
        self.assertEqual(decision.to_dict()["evidence"], [{"nested": [1]}])
        with self.assertRaises(FrozenInstanceError):
            decision.answer = None
        with self.assertRaises(ValueError):
            CompletionDecision(True)
        with self.assertRaises(TypeError):
            CompletionDecision(1)
        with self.assertRaises(TypeError):
            CompletionDecision(False, evidence=("bad",))


class AgentResultTest(unittest.TestCase):
    def setUp(self) -> None:
        self.task_id = uuid4()
        self.state = RuntimeController.initialize()

    def test_valid_status_reason_combinations(self) -> None:
        completed = AgentResult(self.task_id, AgentStatus.COMPLETED, "ready", self.state, TerminationReason.GOAL_SATISFIED, 0)
        incomplete = AgentResult(self.task_id, AgentStatus.INCOMPLETE, None, self.state, TerminationReason.MAX_CYCLES_REACHED, 2)
        pre_runtime_failure = AgentResult(self.task_id, AgentStatus.FAILED, None, None, TerminationReason.UNSUPPORTED_TASK, 0)
        runtime_failure = AgentResult(self.task_id, AgentStatus.FAILED, None, self.state, TerminationReason.POLICY_FAILURE, 1)
        self.assertEqual(completed.status, AgentStatus.COMPLETED)
        self.assertEqual(incomplete.termination_reason, TerminationReason.MAX_CYCLES_REACHED)
        self.assertIsNone(pre_runtime_failure.final_state)
        self.assertEqual(runtime_failure.cycles_completed, 1)

    def test_rejects_invalid_types_values_and_combinations(self) -> None:
        args = (self.task_id, AgentStatus.COMPLETED, "answer", self.state, TerminationReason.GOAL_SATISFIED, 1)
        with self.assertRaises(TypeError): AgentResult("bad", *args[1:])
        with self.assertRaises(TypeError): AgentResult(self.task_id, "completed", *args[2:])
        with self.assertRaises(TypeError): AgentResult(*args[:4], "goal_satisfied", 1)
        with self.assertRaises(ValueError): AgentResult(self.task_id, AgentStatus.COMPLETED, "answer", self.state, TerminationReason.MAX_CYCLES_REACHED, 1)
        with self.assertRaises(ValueError): AgentResult(self.task_id, AgentStatus.COMPLETED, None, self.state, TerminationReason.GOAL_SATISFIED, 1)
        with self.assertRaises(ValueError): AgentResult(self.task_id, AgentStatus.INCOMPLETE, None, None, TerminationReason.MAX_CYCLES_REACHED, 1)
        with self.assertRaises(TypeError): AgentResult(*args[:5], True)
        with self.assertRaises(ValueError): AgentResult(*args[:5], -1)

    def test_deep_immutability_and_round_trip(self) -> None:
        answer = {"id": "payload", "timestamp": "payload-time", "nested": [1]}
        evidence = ({"step": {"items": [1]}},)
        metadata = {"status": "payload", "nested": [1]}
        result = AgentResult(self.task_id, AgentStatus.COMPLETED, answer, self.state, TerminationReason.GOAL_SATISFIED, 1, evidence, metadata)
        answer["nested"].append(2); evidence[0]["step"]["items"].append(2); metadata["nested"].append(2)
        self.assertEqual(result.to_dict()["answer"]["nested"], [1])
        self.assertEqual(result.to_dict()["evidence"], [{"step": {"items": [1]}}])
        self.assertEqual(result.to_dict()["metadata"]["nested"], [1])
        self.assertIsInstance(result.metadata, MappingProxyType)
        with self.assertRaises(FrozenInstanceError): result.answer = None
        data = result.to_dict(); restored = AgentResult.from_dict(data)
        data["answer"]["nested"].append(3)
        self.assertEqual(restored, result)
        self.assertIn("AgentResult(", repr(result))

    def test_serialized_and_evidence_errors(self) -> None:
        with self.assertRaises(TypeError): AgentResult(self.task_id, AgentStatus.FAILED, None, None, TerminationReason.UNSUPPORTED_TASK, 0, ({1: "bad"},))
        with self.assertRaises(TypeError): AgentResult.from_dict([])
        with self.assertRaises(ValueError): AgentResult.from_dict({"task_id": "bad"})
        valid = AgentResult(self.task_id, AgentStatus.FAILED, None, None, TerminationReason.UNSUPPORTED_TASK, 0).to_dict()
        valid["status"] = "bad"
        with self.assertRaises(ValueError): AgentResult.from_dict(valid)


if __name__ == "__main__":
    unittest.main()
