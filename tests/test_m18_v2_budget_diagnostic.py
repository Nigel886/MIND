from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.contracts import EvaluationAction, EvaluationActionType
from src.evaluation.m18_task_generation import M18Cohort, M18Difficulty, M18FailureSubtype, M18Namespace
from src.evaluation.m18_v2_budget_diagnostic import (
    M18_V2_BUDGET_DIAGNOSTIC_CONDITION, M18V2BudgetDiagnosticObserver,
    M18V2BudgetDiagnosticPlan, M18V2BudgetDiagnosticStore, build_diagnostic_record,
    derive_diagnostic_run_id,
)
from src.evaluation.m18_v2_pilot_runner import M18V2PilotPlan, M18V2PilotResultStore
from src.evaluation.m18_v2_provenance import M18_V2_COMPARATOR_CONDITIONS
from src.evaluation.m18_v2_runtime import M18BenchmarkRuntimeCondition, M18V2ResultProvenance, M18V2SharedExecutionHarness
from src.evaluation.m18_v2_semantics import M18V2BudgetError, generate_m18_v2_case, reference_public_trajectory

HASH="d"*64
BASELINE="59506751b66f22bed5106db68a51b1089975c419"
class Script:
    system_condition="direct_tool_calling"
    def __init__(self, actions): self.actions=list(actions)
    def initialize(self, case): pass
    def next_decision(self, feedback, budget, gate): return self.actions.pop(0)
class GateFailure(Script):
    def __init__(self, reason): self.reason=reason
    def next_decision(self, feedback, budget, gate): raise M18V2BudgetError(self.reason)

def runtime(provider_hash=HASH):
    c=M18BenchmarkRuntimeCondition.v2(); return M18V2SharedExecutionHarness(c,M18V2ResultProvenance(c,"m18_shared_execution_runtime_v2",provider_hash,"m18_direct_tool_calling_v1"))
def case(cohort=M18Cohort.A,difficulty=M18Difficulty.HARD,subtype=None): return generate_m18_v2_case(cohort,difficulty,99101,M18Namespace.PILOT,991,subtype)
def ref_actions(value, answer=True):
    trace=reference_public_trajectory(value)
    result=[EvaluationAction(EvaluationActionType.TOOL_CALL,{"tool_name":a["tool_name"],"parameters":a["parameters"]}) for a in trace.actions]
    return result+([EvaluationAction(EvaluationActionType.ANSWER,{"answer":trace.final_public_result})] if answer else [])
def run(value, actions):
    observer=M18V2BudgetDiagnosticObserver(value,"m18_direct_tool_calling_v1")
    result=runtime().dry_run(value,Script(actions),execution_baseline=BASELINE,diagnostic_observer=observer)
    return result,build_diagnostic_record(value,"m18_direct_tool_calling_v1",result,observer)

class M18V2BudgetDiagnosticTests(unittest.TestCase):
    def test_identity_universe_and_canonical_collision_firewall(self):
        plan=M18V2BudgetDiagnosticPlan.from_repository(Path("."))
        self.assertEqual(M18_V2_BUDGET_DIAGNOSTIC_CONDITION,"m18_v2_budget_diagnostic_v1")
        self.assertEqual((len(plan.expected),len(set(plan.run_ids))), (72,72))
        self.assertFalse(set(plan.run_ids)&{x.run_id for x in plan.pilot.expected})
        self.assertNotEqual(derive_diagnostic_run_id(plan.expected[0][0],plan.expected[0][1],1),plan.pilot.expected[0].run_id)

    def test_ideal_path_preserves_public_behavior_and_records_answer(self):
        value=case(); normal=runtime().dry_run(value,Script(ref_actions(value)))
        diagnosed,record=run(value,ref_actions(value))
        self.assertEqual((normal.evaluator_outcome,normal.budget),(diagnosed.evaluator_outcome,diagnosed.budget))
        self.assertEqual(record.terminal_outcome,"answer_submitted")
        self.assertEqual(record.exhausted_budget_dimension,"none")
        self.assertTrue(record.telemetry["answer_emitted"])
        self.assertTrue(record.telemetry["public_completion_before_first_answer"])
        self.assertNotIn("expected_final_result",json.dumps(record.to_dict()))

    def test_tool_and_invalid_and_recoverable_limits_are_distinguished(self):
        hard=case(); extra=ref_actions(hard,False)+[ref_actions(hard,False)[-1]]
        _,tool=run(hard,extra); self.assertEqual(tool.exhausted_budget_dimension,"tool_attempt_limit")
        invalid=case(M18Cohort.C,M18Difficulty.EASY,M18FailureSubtype.INVALID)
        _,bad=run(invalid,ref_actions(invalid,False)+[ref_actions(invalid,False)[-1]])
        self.assertEqual(bad.exhausted_budget_dimension,"invalid_action_limit")
        recovery=case(M18Cohort.C,M18Difficulty.EASY,M18FailureSubtype.RECOVERABLE)
        observer=M18V2BudgetDiagnosticObserver(recovery,"m18_direct_tool_calling_v1")
        result=runtime().dry_run(recovery,GateFailure("recoverable_failure_threshold_reached"),execution_baseline=BASELINE,diagnostic_observer=observer)
        recover=build_diagnostic_record(recovery,"m18_direct_tool_calling_v1",result,observer)
        self.assertEqual(recover.exhausted_budget_dimension,"recoverable_failure_limit")

    def test_provider_dimension_and_atomic_resume_admission(self):
        plan=M18V2BudgetDiagnosticPlan.from_repository(Path(".")); value=plan.pilot.cases[0]; observer=M18V2BudgetDiagnosticObserver(value,"m18_direct_tool_calling_v1")
        result=runtime(plan.pilot.suite_manifest["provider_config_hash"]).dry_run(value,GateFailure("logical_provider_call_limit"),execution_baseline=BASELINE,diagnostic_observer=observer)
        record=build_diagnostic_record(value,"m18_direct_tool_calling_v1",result,observer)
        self.assertEqual(record.exhausted_budget_dimension,"logical_provider_call_limit")
        observer=M18V2BudgetDiagnosticObserver(value,"m18_direct_tool_calling_v1")
        result=runtime(plan.pilot.suite_manifest["provider_config_hash"]).dry_run(value,GateFailure("action_cycle_limit"),execution_baseline=BASELINE,diagnostic_observer=observer)
        self.assertEqual(build_diagnostic_record(value,"m18_direct_tool_calling_v1",result,observer).exhausted_budget_dimension,"action_cycle_limit")
        with TemporaryDirectory() as tmp:
            store=M18V2BudgetDiagnosticStore(Path(tmp),plan); store.initialize()
            admitted=store.persist(record); self.assertEqual(store.records(),(admitted,)); self.assertEqual(len(store.missing()),71)
            with self.assertRaises(Exception): store.persist(record)

    def test_historical_pilot_is_unchanged_and_formal_namespace_empty(self):
        plan=M18V2PilotPlan.from_repository(Path(".")); store=M18V2PilotResultStore(Path("evaluation/m18/results/v2/pilot/m18_suite_v2"),plan.expected,plan.suite_manifest)
        self.assertEqual((len(store.records()),store.digest()),(360,"50caa6c9afaaf3712e10c5f75f397bb1f8306ebe12b0fd305a8f076a4a79473c"))
        self.assertFalse(Path("evaluation/m18/results/v2/formal").exists())

if __name__=="__main__": unittest.main()
