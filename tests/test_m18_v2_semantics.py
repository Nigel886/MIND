"""Provider-free reachability and accounting tests for the un-frozen M18 v2."""
from __future__ import annotations
import unittest

from src.evaluation.m18_plan_and_execute import M18PlanAndExecuteBaseline
from src.evaluation.m18_task_generation import M18Cohort, M18Difficulty, M18FailureSubtype, M18Namespace, generate_m18_case
from src.evaluation.m18_v2_semantics import (
    M18EvaluatorV2, M18V2Budget, M18V2BudgetError, M18V2BudgetState,
    M18V2Episode, M18V2EvaluationCategory, M18V2OutcomeCategory,
    M18_V2_BUDGET_ID, M18_V2_ENVIRONMENT_ID, M18_V2_EVALUATOR_ID,
    M18_V2_SUITE_VERSION, generate_m18_v2_case, initial_public_state,
    reference_public_trajectory, v2_case_hash,
)
from src.evaluation.m18_suite_v2 import generate_m18_case_for_version

class M18V2SemanticsTests(unittest.TestCase):
    def make(self, cohort, difficulty, subtype=None):
        return generate_m18_v2_case(cohort, difficulty, 8101, M18Namespace.PILOT, 2, subtype)

    def test_explicit_v2_identities_and_budget_serialization(self):
        budget=M18V2Budget()
        self.assertEqual((budget.identity,M18_V2_ENVIRONMENT_ID,M18_V2_EVALUATOR_ID,M18_V2_SUITE_VERSION),(M18_V2_BUDGET_ID,"m18_environment_v2","m18_evaluator_v2","m18_suite_v2"))
        self.assertEqual((budget.max_action_cycles,budget.max_tool_attempts,budget.episode_timeout_seconds),(6,4,180))
        self.assertTrue(budget.answer_consumes_action_cycle); self.assertFalse(budget.plan_replans_consume_public_action_cycle)

    def test_v1_generator_and_membership_are_unchanged(self):
        old=generate_m18_case(M18Cohort.A,M18Difficulty.HARD,8101,M18Namespace.PILOT,2)
        new=self.make(M18Cohort.A,M18Difficulty.HARD)
        self.assertEqual(old.case_id,new.case_id); self.assertEqual(old.generation_seed,new.generation_seed)
        self.assertNotEqual(old.environment_version,new.environment_id)
        self.assertEqual(generate_m18_case_for_version("m18_suite_v1",M18Cohort.A,M18Difficulty.HARD,8101,M18Namespace.PILOT,2).case_id,old.case_id)
        self.assertEqual(generate_m18_case_for_version(M18_V2_SUITE_VERSION,M18Cohort.A,M18Difficulty.HARD,8101,M18Namespace.PILOT,2).case_id,new.case_id)
        with self.assertRaises(ValueError): generate_m18_case_for_version("ambiguous",M18Cohort.A,M18Difficulty.HARD,8101,M18Namespace.PILOT,2)

    def test_full_reachability_matrix_and_structural_bounds(self):
        cells=[(M18Cohort.A,d,None) for d in M18Difficulty]+[(M18Cohort.B,d,None) for d in M18Difficulty]
        cells += [(M18Cohort.C,d,s) for s in M18FailureSubtype for d in M18Difficulty]
        expected={(M18Cohort.A,M18Difficulty.EASY):(3,2),(M18Cohort.A,M18Difficulty.MEDIUM):(4,3),(M18Cohort.A,M18Difficulty.HARD):(5,4)}
        for cohort,difficulty,subtype in cells:
            with self.subTest(cohort=cohort,difficulty=difficulty,subtype=subtype):
                case=self.make(cohort,difficulty,subtype); trace=reference_public_trajectory(case)
                bounds=expected.get((cohort,difficulty),(2,1) if cohort is M18Cohort.B else ((3,2) if difficulty is M18Difficulty.EASY else (4,3)))
                self.assertEqual((trace.action_cycles,trace.tool_attempts),bounds)
                self.assertEqual(trace.evaluation,M18V2EvaluationCategory.SUCCESS)
                self.assertEqual(trace.final_public_result,case.evaluator.expected_final_result)
                self.assertLessEqual(trace.action_cycles,6); self.assertLessEqual(trace.tool_attempts,4)

    def test_distractor_and_answer_shortcut_do_not_succeed(self):
        case=self.make(M18Cohort.B,M18Difficulty.EASY); state=initial_public_state(case)
        relevant=case.public.to_dict()["task_config"]["steps"][0]["tool_id"]
        distractor=next(tool["tool_id"] for tool in case.public.to_dict()["capabilities"] if tool["tool_id"]!=relevant)
        episode=M18V2Episode(case)
        episode.submit_tool({"action":"tool_call","tool_name":distractor,"parameters":{"value":state["current_value"]}})
        self.assertEqual(episode.submit_answer(0),M18V2EvaluationCategory.INTERACTION_INCOMPLETE)
        self.assertEqual(M18V2Episode(self.make(M18Cohort.A,M18Difficulty.EASY)).submit_answer(1),M18V2EvaluationCategory.INTERACTION_INCOMPLETE)

    def test_evaluator_rejects_wrong_and_malformed_answer(self):
        case=self.make(M18Cohort.A,M18Difficulty.EASY); trace=reference_public_trajectory(case); episode=M18V2Episode(case)
        for action in trace.actions: episode.submit_tool(action)
        self.assertEqual(episode.submit_answer("wrong"),M18V2EvaluationCategory.MALFORMED_ANSWER)
        self.assertEqual(M18EvaluatorV2().evaluate(case,trace.final_public_result+1,episode.public_state),M18V2EvaluationCategory.WRONG_ANSWER)

    def test_budget_boundaries_and_thresholds(self):
        state=M18V2BudgetState()
        for _ in range(6): state=state.consume_action()
        with self.assertRaisesRegex(M18V2BudgetError,"action_cycle_limit"): state.consume_action()
        state=M18V2BudgetState()
        for _ in range(4): state=state.consume_action(True)
        with self.assertRaisesRegex(M18V2BudgetError,"tool_attempt_limit"): state.consume_action(True)
        for _ in range(8): state=state.record_logical_provider_call()
        with self.assertRaisesRegex(M18V2BudgetError,"logical_provider_call_limit"): state.record_logical_provider_call()
        state,stop=M18V2BudgetState().record_outcome(M18V2OutcomeCategory.INVALID_ACTION); self.assertIsNone(stop)
        _,stop=state.record_outcome(M18V2OutcomeCategory.INVALID_ACTION); self.assertEqual(stop,"invalid_action_threshold_reached")
        state,stop=M18V2BudgetState().record_outcome(M18V2OutcomeCategory.RECOVERABLE_FAILURE); self.assertIsNone(stop)
        _,stop=state.record_outcome(M18V2OutcomeCategory.RECOVERABLE_FAILURE); self.assertEqual(stop,"recoverable_failure_threshold_reached")

    def test_timeout_determinism_truth_firewall_and_plan_compatibility(self):
        case=self.make(M18Cohort.C,M18Difficulty.EASY,M18FailureSubtype.RECOVERABLE); episode=M18V2Episode(case)
        episode.enforce_elapsed_seconds(180); self.assertEqual(episode.terminal_reason,"timeout")
        self.assertEqual(reference_public_trajectory(case),reference_public_trajectory(case))
        self.assertEqual(v2_case_hash(case),v2_case_hash(self.make(M18Cohort.C,M18Difficulty.EASY,M18FailureSubtype.RECOVERABLE)))
        public=str(case.public.to_dict()); self.assertNotIn("expected_final_result",public); self.assertNotIn(str(case.evaluator.expected_final_result),public)
        self.assertEqual(M18PlanAndExecuteBaseline.max_replans,1)

if __name__=="__main__": unittest.main()
