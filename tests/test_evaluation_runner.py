"""Tests for deterministic, evaluation-only comparative runner behavior."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from evaluation.runner.evaluation_runner import EvaluationRunResult, EvaluationRunner
from evaluation.tasks.evaluation_task import EvaluationScenario, EvaluationTask
from src.core.agent import GoalDirectedAgent
from src.core.inference_registry import InferenceStrategyRegistry
from src.core.inference_strategy import InferenceStrategy
from src.core.meta_engine import MetaInferenceEngine
from src.core.task import Goal, Task
from src.core.tool import ToolRegistry
from src.tools.calculator import CalculatorTool


class _NoOpInference:
    def infer(self, observation, belief):
        return belief


def _scenario(name: str = "direct_success", calculator: bool = False) -> EvaluationScenario:
    payload = (
        {"operation": "multiply", "operands": [17, 23], "expected_answer": 391}
        if calculator
        else {"value": "ready", "expected_answer": "ready"}
    )
    task = Task(
        Goal("complete the supplied request", ("return the expected answer",)),
        payload,
        metadata={"required_inference_capabilities": ["incremental"]},
    )
    return EvaluationScenario(
        name,
        "a deterministic evaluation scenario",
        EvaluationTask(name, "evaluate one task", task, "success", "completed"),
        "completed",
    )


def _runner() -> EvaluationRunner:
    tools_a = ToolRegistry()
    tools_a.register(CalculatorTool())
    tools_b = ToolRegistry()
    tools_b.register(CalculatorTool())
    registry = InferenceStrategyRegistry()
    registry.register(
        InferenceStrategy("incremental", "controlled strategy", ("incremental",)),
        _NoOpInference(),
    )
    return EvaluationRunner(
        GoalDirectedAgent(tools_a),
        GoalDirectedAgent(tools_b, MetaInferenceEngine(registry)),
    )


class EvaluationRunnerTest(unittest.TestCase):
    def test_runs_both_baselines_with_compact_summaries(self) -> None:
        scenario = _scenario()
        original = scenario.to_dict()
        baseline_a, baseline_b = _runner().run(scenario, 1)

        self.assertEqual((baseline_a.baseline_name, baseline_b.baseline_name), ("baseline_a", "baseline_b"))
        self.assertTrue(baseline_a.success)
        self.assertTrue(baseline_b.success)
        self.assertIsNone(baseline_a.selected_strategy)
        self.assertEqual(baseline_b.selected_strategy, "incremental")
        self.assertEqual(scenario.to_dict(), original)
        self.assertNotIn("final_state", baseline_a.to_dict())
        self.assertNotIn("answer", baseline_a.to_dict())

    def test_calculator_scenario_and_repeated_semantics_are_deterministic(self) -> None:
        runner = _runner()
        scenario = _scenario("calculator_success", calculator=True)
        first = runner.run(scenario, 1)
        second = runner.run(scenario, 1)

        self.assertTrue(all(result.success for result in first))
        self.assertEqual(
            tuple(result.semantic_signature for result in first),
            tuple(result.semantic_signature for result in second),
        )
        self.assertTrue(all(result.elapsed_time >= 0 for result in first))

    def test_result_is_immutable_serializable_and_has_no_mutable_aliases(self) -> None:
        result = _runner().run(_scenario(), 1)[1]
        serialized = result.to_dict()
        restored = EvaluationRunResult.from_dict(serialized)

        self.assertEqual(restored, result)
        with self.assertRaises(FrozenInstanceError):
            result.success = False
        with self.assertRaises(TypeError):
            result.evidence_summary[0]["type"] = "changed"
        serialized["evidence_summary"][0]["type"] = "changed"
        self.assertNotEqual(serialized["evidence_summary"], result.to_dict()["evidence_summary"])

    def test_validation_and_baseline_isolation(self) -> None:
        runner = _runner()
        scenario = _scenario()
        with self.assertRaises(TypeError):
            EvaluationRunner({}, GoalDirectedAgent(ToolRegistry()))
        with self.assertRaises(TypeError):
            runner.run({}, 1)
        with self.assertRaises(TypeError):
            runner.run(scenario, True)
        with self.assertRaises(ValueError):
            runner.run(scenario, -1)
        with self.assertRaises(ValueError):
            EvaluationRunResult.from_dict({**runner.run(scenario, 1)[0].to_dict(), "semantic_signature": {}})


if __name__ == "__main__":
    unittest.main()
