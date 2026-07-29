"""Tests for deterministic CompletionEvaluator behavior."""

from __future__ import annotations

import unittest

from src.core.completion import CompletionEvaluator
from src.core.runtime import RuntimeController
from src.core.task import Goal, Task


class CompletionEvaluatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.goal = Goal("return the expected result", ("correct",))
        self.state = RuntimeController.initialize()

    def test_matching_string_and_numeric_candidates(self) -> None:
        text_task = Task(self.goal, {"value": "ready", "expected_answer": "ready"})
        number_task = Task(self.goal, {"operation": "multiply", "expected_answer": 391})
        text = CompletionEvaluator.evaluate(text_task, self.state, "ready")
        number = CompletionEvaluator.evaluate(number_task, self.state, 391)
        self.assertTrue(text.is_satisfied)
        self.assertTrue(number.is_satisfied)
        self.assertEqual(text.answer, "ready")
        self.assertTrue(text.to_dict()["evidence"][0]["matched"])

    def test_nonmatching_missing_and_none_candidates_are_unsatisfied(self) -> None:
        expected_task = Task(self.goal, {"expected_answer": "ready"})
        missing_task = Task(self.goal, {"value": "ready"})
        mismatch = CompletionEvaluator.evaluate(expected_task, self.state, "no")
        none = CompletionEvaluator.evaluate(expected_task, self.state, None)
        missing = CompletionEvaluator.evaluate(missing_task, self.state, "ready")
        self.assertFalse(mismatch.is_satisfied)
        self.assertFalse(none.is_satisfied)
        self.assertFalse(missing.is_satisfied)
        self.assertFalse(missing.to_dict()["evidence"][0]["available"])

    def test_structured_equality_and_input_preservation(self) -> None:
        expected = {"value": [1, 2]}
        candidate = {"value": [1, 2]}
        input_data = {"expected_answer": expected}
        task = Task(self.goal, input_data)
        original_state = self.state.to_dict()
        decision = CompletionEvaluator.evaluate(task, self.state, candidate)
        expected["value"].append(3); candidate["value"].append(3); input_data["expected_answer"]["value"].append(4)
        self.assertTrue(decision.is_satisfied)
        self.assertEqual(decision.to_dict()["answer"], {"value": [1, 2]})
        self.assertEqual(task.to_dict()["input"]["expected_answer"], {"value": [1, 2]})
        self.assertEqual(self.state.to_dict(), original_state)

    def test_rejects_invalid_component_inputs_and_has_no_runtime_behavior(self) -> None:
        task = Task(self.goal, {"expected_answer": "ready"})
        with self.assertRaises(TypeError): CompletionEvaluator.evaluate({}, self.state, "ready")
        with self.assertRaises(TypeError): CompletionEvaluator.evaluate(task, {}, "ready")
        self.assertFalse(hasattr(CompletionEvaluator, "generate"))
        self.assertFalse(hasattr(CompletionEvaluator, "execute"))


if __name__ == "__main__":
    unittest.main()
