"""Provider-free shared-runtime tests for the explicit M18 v2 condition."""
from __future__ import annotations
import unittest

from src.evaluation.contracts import EvaluationAction, EvaluationActionType
from src.evaluation.m18_plan_and_execute import M18PlanAndExecuteBaseline
from src.evaluation.m18_execution_harness import M18SharedExecutionHarness, M18ExecutionMode
from src.evaluation.m18_suite_freeze import formal_suite, pilot_suite
from src.evaluation.m18_task_generation import M18Cohort, M18Difficulty, M18FailureSubtype, M18Namespace
from src.evaluation.m18_v2_runtime import (
    M18BenchmarkRuntimeCondition, M18V2ProviderCallGate, M18V2ResultProvenance,
    M18V2RuntimeTerminal, M18V2SharedExecutionHarness, M18_V2_RUNTIME_ID,
    M18_V2_SYSTEMS,
)
from src.evaluation.m18_v2_semantics import (
    M18V2BudgetError, M18V2EvaluationCategory, M18_V2_SUITE_VERSION,
    generate_m18_v2_case, reference_public_trajectory,
)

HASH = "a" * 64

class ScriptedAdapter:
    def __init__(self, system_condition, actions, *, transport_attempts=1):
        self.system_condition=system_condition; self._actions=list(actions); self.transport_attempts=transport_attempts
        self.public_case=None; self.feedback=[]
    def initialize(self, case): self.public_case=case.public.to_dict()
    def next_decision(self, feedback, budget, provider_gate):
        self.feedback.append(feedback.to_dict())
        return provider_gate.invoke(lambda: self._actions.pop(0), transport_attempts=self.transport_attempts)

def runtime():
    condition=M18BenchmarkRuntimeCondition.v2()
    provenance=M18V2ResultProvenance(condition,M18_V2_RUNTIME_ID,HASH,"provider_free_comparator_condition")
    return M18V2SharedExecutionHarness(condition,provenance)

def public_actions(case):
    trace=reference_public_trajectory(case)
    actions=[EvaluationAction(EvaluationActionType.TOOL_CALL,{"tool_name":a["tool_name"],"parameters":a["parameters"]}) for a in trace.actions]
    actions.append(EvaluationAction(EvaluationActionType.ANSWER,{"answer":trace.final_public_result}))
    return actions,trace

def v2_from_v1(case):
    subtype=M18FailureSubtype(case.evaluator.failure_schedule["subtype"]) if case.cohort is M18Cohort.C else None
    return generate_m18_v2_case(case.cohort,case.difficulty,case.generation_seed,case.namespace,int(case.case_id.rsplit(".",1)[1]),subtype)

class M18V2SharedRuntimeTests(unittest.TestCase):
    def case(self, cohort, difficulty, subtype=None): return generate_m18_v2_case(cohort,difficulty,6101,M18Namespace.PILOT,1,subtype)
    def execute_runtime(self, case, system="direct_tool_calling", transport=1):
        actions,trace=public_actions(case); adapter=ScriptedAdapter(system,actions,transport_attempts=transport)
        return runtime().dry_run(case,adapter),trace,adapter

    def test_explicit_binding_and_mixed_conditions_fail_closed(self):
        self.assertEqual(M18BenchmarkRuntimeCondition.v1().suite_version,"m18_suite_v1")
        self.assertEqual(M18BenchmarkRuntimeCondition.v2().suite_version,M18_V2_SUITE_VERSION)
        with self.assertRaises(ValueError): M18BenchmarkRuntimeCondition("m18_runtime_condition_v2",M18_V2_SUITE_VERSION,"m18_environment_v1","m18_evaluator_v2","m18_budget_v2")
        with self.assertRaises(ValueError): M18BenchmarkRuntimeCondition("m18_runtime_condition_v1","m18_suite_v1","m18_environment_v1","m18_evaluator_v2","m18_budget_v1_historical_3_1")
        with self.assertRaises(ValueError): M18BenchmarkRuntimeCondition("unknown","x","x","x","x")
        v1=M18SharedExecutionHarness(HASH,mode=M18ExecutionMode.SYNTHETIC)
        self.assertEqual((v1.budget.max_steps,v1.budget.max_tool_calls),(3,1))
        self.assertEqual(type(v1.environment).__name__,"M18DeterministicEnvironment")

    def test_real_runtime_a_hard_and_reference_equivalence(self):
        result,trace,_=self.execute_runtime(self.case(M18Cohort.A,M18Difficulty.HARD))
        self.assertEqual((result.terminal,result.evaluator_outcome),(M18V2RuntimeTerminal.ANSWER_SUBMITTED,M18V2EvaluationCategory.SUCCESS))
        self.assertEqual((result.budget.action_cycles,result.budget.tool_attempts),(5,4))
        self.assertEqual(result.final_public_state["current_value"],trace.final_public_result)
        self.assertEqual(result.environment_outcomes,trace.observations)
        self.assertEqual(result.logical_provider_calls,5)

    def test_real_runtime_b_and_distractor_negative(self):
        case=self.case(M18Cohort.B,M18Difficulty.MEDIUM); result,_,_=self.execute_runtime(case)
        self.assertEqual(result.evaluator_outcome,M18V2EvaluationCategory.SUCCESS)
        public=case.public.to_dict(); relevant=public["task_config"]["steps"][0]["tool_id"]
        wrong=next(x["tool_id"] for x in public["capabilities"] if x["tool_id"]!=relevant)
        adapter=ScriptedAdapter("direct_tool_calling",[EvaluationAction(EvaluationActionType.TOOL_CALL,{"tool_name":wrong,"parameters":{"value":public["task_config"]["initial_value"]}}),EvaluationAction(EvaluationActionType.ANSWER,{"answer":0})])
        failed=runtime().dry_run(case,adapter); self.assertEqual(failed.evaluator_outcome,M18V2EvaluationCategory.INTERACTION_INCOMPLETE)

    def test_real_runtime_c_recoverable_and_invalid_are_finite(self):
        for subtype in M18FailureSubtype:
            for difficulty in M18Difficulty:
                with self.subTest(subtype=subtype,difficulty=difficulty):
                    result,trace,_=self.execute_runtime(self.case(M18Cohort.C,difficulty,subtype))
                    self.assertEqual(result.evaluator_outcome,M18V2EvaluationCategory.SUCCESS)
                    self.assertEqual((result.budget.action_cycles,result.budget.tool_attempts),(3,2) if difficulty is M18Difficulty.EASY else (4,3))
                    self.assertEqual(result.final_public_state["current_value"],trace.final_public_result)

    def test_answer_and_real_budget_boundaries(self):
        case=self.case(M18Cohort.A,M18Difficulty.EASY)
        shortcut=runtime().dry_run(case,ScriptedAdapter("direct_tool_calling",[EvaluationAction(EvaluationActionType.ANSWER,{"answer":1})]))
        self.assertEqual(shortcut.evaluator_outcome,M18V2EvaluationCategory.INTERACTION_INCOMPLETE)
        # Four legal attempts consume the tool allowance; the fifth is rejected by the runtime episode.
        hard=self.case(M18Cohort.A,M18Difficulty.HARD); actions,_=public_actions(hard)
        extra=actions[:-1]+[EvaluationAction(EvaluationActionType.TOOL_CALL,{"tool_name":"extra","parameters":{"value":0}})]
        result=runtime().dry_run(hard,ScriptedAdapter("direct_tool_calling",extra)); self.assertEqual(result.terminal,M18V2RuntimeTerminal.BUDGET_EXHAUSTED)

    def test_provider_ceiling_transport_separation_and_all_systems(self):
        case=self.case(M18Cohort.B,M18Difficulty.EASY)
        for system in M18_V2_SYSTEMS:
            with self.subTest(system=system):
                result,_,adapter=self.execute_runtime(case,system,transport=3)
                self.assertEqual(result.logical_provider_calls,2); self.assertEqual(result.transport_attempts,6)
                self.assertNotIn("expected_final_result",str(adapter.public_case)); self.assertNotIn(str(case.evaluator.expected_final_result),str(adapter.public_case))
        gate=M18V2ProviderCallGate(__import__('src.evaluation.m18_v2_semantics',fromlist=['M18V2BudgetState']).M18V2BudgetState())
        for _ in range(8): gate.invoke(lambda: None,transport_attempts=2)
        with self.assertRaisesRegex(M18V2BudgetError,"logical_provider_call_limit"): gate.invoke(lambda: None)

    def test_timeout_provenance_and_plan_separation(self):
        case=self.case(M18Cohort.B,M18Difficulty.EASY); actions,_=public_actions(case)
        result=runtime().dry_run(case,ScriptedAdapter("react",actions),elapsed_seconds=180)
        self.assertEqual((result.terminal,result.evaluator_outcome),(M18V2RuntimeTerminal.TIMEOUT,M18V2EvaluationCategory.TIMEOUT))
        p=result.provenance.to_dict(); self.assertEqual(p["condition"]["budget_id"],"m18_budget_v2"); self.assertEqual(p["execution_harness_id"],M18_V2_RUNTIME_ID)
        self.assertEqual(M18PlanAndExecuteBaseline.max_replans,1)

    def test_real_runtime_sweeps_all_memberships(self):
        for suite,expected in ((pilot_suite(),18),(formal_suite(),162)):
            passed=0
            for old in suite:
                case=v2_from_v1(old); result,trace,adapter=self.execute_runtime(case,"mind_lite_v11")
                self.assertEqual(result.evaluator_outcome,M18V2EvaluationCategory.SUCCESS)
                self.assertEqual(result.final_public_state["current_value"],trace.final_public_result)
                self.assertLessEqual(result.budget.action_cycles,6); self.assertLessEqual(result.budget.tool_attempts,4)
                self.assertNotIn("expected_final_result",str(adapter.public_case)); passed+=1
            self.assertEqual(passed,expected)

if __name__=="__main__": unittest.main()
