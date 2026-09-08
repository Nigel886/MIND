"""Contract tests for the formal M16 Cohort A held-out suite registration."""

from __future__ import annotations

from dataclasses import replace
from collections import Counter
from typing import Mapping
import unittest

from evaluation.tasks.m14_cohort_a_fixtures import get_m14_cohort_a_fixtures
from evaluation.tasks.m16_cohort_a_held_out import get_m16_cohort_a_held_out_suite
from src.evaluation.contracts import EvaluationAction, EvaluationActionType
from src.evaluation.execution import EvaluationBudget, EvaluationBudgetState
from src.evaluation.m16_cohort_a_suite import (
    M16CohortADifficulty,
    M16CohortAHeldOutSuite,
    M16CohortATaskFamily,
    M16_COHORT_A_SUITE_VERSION,
    M16_PROTOCOL_VERSION,
    m16_cohort_a_suite_manifest,
)
from src.evaluation.m16_leakage_free import (
    M16ExactCompletionJudge,
    M16PrivateEnvironmentSpecification,
    M16PrivateEvaluationEnvironment,
)


class M16CohortAHeldOutSuiteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = get_m16_cohort_a_held_out_suite()

    def test_exact_count_balance_versions_and_stable_order(self) -> None:
        self.assertEqual(len(self.suite.cases), 96)
        counts = Counter((case.task_family, case.difficulty) for case in self.suite.cases)
        self.assertEqual(len(counts), 6)
        self.assertTrue(all(count == 16 for count in counts.values()))
        self.assertEqual(self.suite.protocol_version, "1.1.0")
        self.assertEqual(self.suite.suite_version, "1.0.0")
        self.assertEqual([case.evaluation_id for case in self.suite.cases], sorted(case.evaluation_id for case in self.suite.cases))

    def test_all_cases_are_held_out_unique_and_pre_outcome_eligible(self) -> None:
        identifiers = [case.evaluation_id for case in self.suite.cases]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        for case in self.suite.cases:
            with self.subTest(case=case.evaluation_id):
                self.assertTrue(case.held_out)
                marker = case.evaluation_case.task.metadata["m16_cohort_a"]
                self.assertFalse(marker["requires_planning"])
                self.assertFalse(marker["requires_multi_tool"])
                self.assertFalse(marker["requires_dependent_multistep"])
                self.assertFalse(marker["requires_recovery"])

    def test_public_schemas_and_truth_privacy(self) -> None:
        for case in self.suite.cases:
            with self.subTest(case=case.evaluation_id):
                task_data = case.evaluation_case.task.to_dict()
                self.assertNotIn("expected_answer", task_data["input"])
                self.assertNotIn("expected_answer", task_data["metadata"])
                if case.task_family is M16CohortATaskFamily.DIRECT_ANSWER:
                    self.assertEqual(set(task_data["input"]), {"value"})
                    self.assertEqual(task_data["input"]["value"], case.private_truth.to_private_dict()["expected_answer"])
                else:
                    self.assertEqual(set(task_data["input"]), {"operation", "operands"})
                    self.assertIn(task_data["input"]["operation"], {"add", "multiply"})
                    operands = task_data["input"]["operands"]
                    self.assertEqual(len(operands), 2)
                    self.assertTrue(all(isinstance(value, int) and not isinstance(value, bool) for value in operands))
                    expected = operands[0] + operands[1] if task_data["input"]["operation"] == "add" else operands[0] * operands[1]
                    self.assertEqual(expected, case.private_truth.to_private_dict()["expected_answer"])

    def test_difficulty_rules_are_visible_in_constructed_public_data(self) -> None:
        direct_easy = [case for case in self.suite.cases if case.task_family is M16CohortATaskFamily.DIRECT_ANSWER and case.difficulty is M16CohortADifficulty.EASY]
        direct_medium = [case for case in self.suite.cases if case.task_family is M16CohortATaskFamily.DIRECT_ANSWER and case.difficulty is M16CohortADifficulty.MEDIUM]
        direct_hard = [case for case in self.suite.cases if case.task_family is M16CohortATaskFamily.DIRECT_ANSWER and case.difficulty is M16CohortADifficulty.HARD]
        self.assertTrue(all(not isinstance(case.evaluation_case.task.input["value"], (dict, tuple)) for case in direct_easy))
        self.assertTrue(all(isinstance(case.evaluation_case.task.input["value"], Mapping) for case in direct_medium))
        self.assertTrue(all("payload" in case.evaluation_case.task.input["value"] for case in direct_hard))
        calculator_easy = [case for case in self.suite.cases if case.task_family is M16CohortATaskFamily.CALCULATOR and case.difficulty is M16CohortADifficulty.EASY]
        calculator_medium = [case for case in self.suite.cases if case.task_family is M16CohortATaskFamily.CALCULATOR and case.difficulty is M16CohortADifficulty.MEDIUM]
        calculator_hard = [case for case in self.suite.cases if case.task_family is M16CohortATaskFamily.CALCULATOR and case.difficulty is M16CohortADifficulty.HARD]
        self.assertTrue(all(all(0 <= value <= 9 for value in case.evaluation_case.task.input["operands"]) for case in calculator_easy))
        self.assertTrue(all(any(value < 0 for value in case.evaluation_case.task.input["operands"]) and max(abs(value) for value in case.evaluation_case.task.input["operands"]) < 1_000 for case in calculator_medium))
        self.assertTrue(all(max(abs(value) for value in case.evaluation_case.task.input["operands"]) >= 1_000 for case in calculator_hard))

    def test_private_judge_and_environment_compatibility_without_agent_execution(self) -> None:
        for case in self.suite.cases:
            with self.subTest(case=case.evaluation_id):
                environment = M16PrivateEvaluationEnvironment(case.environment_specification)
                reset = environment.reset(case.evaluation_case)
                self.assertNotIn("completion_context", reset.payload)
                judge = M16ExactCompletionJudge(case.private_truth)
                answer = EvaluationAction(EvaluationActionType.ANSWER, {"answer": case.private_truth.expected_answer})
                outcome = judge.evaluate(case.evaluation_case, (), EvaluationBudgetState(EvaluationBudget(1, 0)), answer)
                if case.task_family is M16CohortATaskFamily.DIRECT_ANSWER:
                    self.assertEqual(outcome.outcome_type.value, "success")

    def test_generation_and_hashes_are_stable_and_manifest_is_public_safe(self) -> None:
        again = get_m16_cohort_a_held_out_suite()
        self.assertEqual(self.suite, again)
        self.assertEqual(self.suite.suite_hash, again.suite_hash)
        self.assertEqual(self.suite.held_out_split_hash, again.held_out_split_hash)
        self.assertEqual(len(self.suite.suite_hash), 64)
        self.assertEqual(len(self.suite.held_out_split_hash), 64)
        manifest = m16_cohort_a_suite_manifest(self.suite)
        self.assertEqual(manifest["protocol_version"], M16_PROTOCOL_VERSION)
        self.assertEqual(manifest["suite_version"], M16_COHORT_A_SUITE_VERSION)
        self.assertNotIn("expected_answer", str(manifest))

    def test_full_hash_changes_for_material_private_environment_change(self) -> None:
        first = self.suite.cases[0]
        changed = replace(
            first,
            environment_specification=M16PrivateEnvironmentSpecification(
                first.environment_specification.environment_id,
                {"revision": "changed"},
            ),
        )
        altered = M16CohortAHeldOutSuite((changed,) + self.suite.cases[1:])
        self.assertNotEqual(self.suite.suite_hash, altered.suite_hash)
        self.assertEqual(self.suite.held_out_split_hash, altered.held_out_split_hash)

    def test_duplicate_ids_and_complete_cases_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            M16CohortAHeldOutSuite((self.suite.cases[0], self.suite.cases[0]) + self.suite.cases[2:])

    def test_no_m14_development_fixture_is_reused(self) -> None:
        m14_ids = {fixture.task_id for fixture in get_m14_cohort_a_fixtures()}
        formal_ids = {case.evaluation_id for case in self.suite.cases}
        self.assertFalse(m14_ids & formal_ids)
        self.assertTrue(all(case.held_out for case in self.suite.cases))


if __name__ == "__main__":
    unittest.main()
