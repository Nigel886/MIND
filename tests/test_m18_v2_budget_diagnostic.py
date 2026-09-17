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
    derive_diagnostic_run_id, replay_public_completion, M18V2BudgetDiagnosticRunner,
)
from src.evaluation.m18_v2_provider_diagnostics import M18V2SystematicProviderStop
from src.evaluation.m18_v2_pilot_runner import M18V2PilotPlan, M18V2PilotResultStore
from src.evaluation.m18_v2_provenance import M18_V2_COMPARATOR_CONDITIONS
from src.evaluation.m18_v2_runtime import M18BenchmarkRuntimeCondition, M18V2ResultProvenance, M18V2SharedExecutionHarness
from src.evaluation.m18_v2_semantics import M18V2BudgetError, generate_m18_v2_case, reference_public_trajectory
from src.evaluation.m18_v2_runtime import M18V2MINDAdapter, M18V2DirectAdapter, M18V2ReActAdapter, M18V2PlanAdapter

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
class BrokenObserver:
    def observe(self,*args,**kwargs): raise RuntimeError("telemetry failure")
class DecoderFailure(Script):
    def next_decision(self,*args): raise ValueError("strict decoder rejected output")
class SequenceProvider:
    def __init__(self,responses): self.responses=list(responses); self.transport_attempts_per_logical_call=1
    def generate(self,request): return self.responses.pop(0)
class PlanProvider:
    def __init__(self,plan,responses): self.plan_text=plan; self.responses=list(responses); self.transport_attempts_per_logical_call=1
    def plan(self,request): return self.plan_text
    def execute(self,request): return self.responses.pop(0)
class StructuralFailure(RuntimeError): category="malformed_json"
class FailingPlanProvider:
    transport_attempts_per_logical_call=1
    def generate(self,request): raise StructuralFailure("diagnostic-secret sk-test-123")
    def plan(self,request): raise StructuralFailure("diagnostic-secret sk-test-123")
    def execute(self,request): raise StructuralFailure("diagnostic-secret sk-test-123")

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
def concrete_payloads(value, *, include_answer=True):
    trace=reference_public_trajectory(value)
    actions=[json.dumps({"action":"tool_call","tool_name":a["tool_name"],"parameters":a["parameters"]},separators=(",",":")) for a in trace.actions]
    if include_answer: actions.append(json.dumps({"action":"answer","answer":trace.final_public_result},separators=(",",":")))
    caps=value.public.to_dict()["capabilities"]
    plan=json.dumps({"steps":[{"step_id":f"s{i}","subgoal":"public execution","capability_id":caps[i%len(caps)]["tool_id"]} for i in range(8)]},separators=(",",":"))
    return actions,plan
def concrete(kind,value,responses=None):
    actions,plan=concrete_payloads(value)
    values=actions if responses is None else responses
    if kind=="mind_lite_v11": return M18V2MINDAdapter(SequenceProvider(values))
    if kind=="direct_tool_calling": return M18V2DirectAdapter(SequenceProvider(values))
    if kind=="react": return M18V2ReActAdapter(SequenceProvider(values))
    return M18V2PlanAdapter(PlanProvider(plan,values))
def signature(result):
    return (result.terminal,result.evaluator_outcome,result.actions,result.feedback,result.environment_outcomes,
            result.final_public_state,result.budget,result.logical_provider_calls,result.transport_attempts)

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
        broken=runtime().dry_run(value,Script(ref_actions(value)),diagnostic_observer=BrokenObserver())
        self.assertEqual((normal.terminal,normal.evaluator_outcome,normal.budget),(broken.terminal,broken.evaluator_outcome,broken.budget))
        replay=replay_public_completion(value.public.to_dict(),record.public_trace)
        self.assertEqual(replay["first_completion_step"],len(record.public_trace)-1)

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
            path=Path(tmp)/(record.run_id+".json"); payload=json.loads(path.read_text()); payload["telemetry"]["unknown"]=1; path.write_text(json.dumps(payload))
            with self.assertRaises(Exception): store.records()

    def test_historical_pilot_is_unchanged_and_formal_namespace_empty(self):
        plan=M18V2PilotPlan.from_repository(Path(".")); store=M18V2PilotResultStore(Path("evaluation/m18/results/v2/pilot/m18_suite_v2"),plan.expected,plan.suite_manifest)
        self.assertEqual((len(store.records()),store.digest()),(360,"50caa6c9afaaf3712e10c5f75f397bb1f8306ebe12b0fd305a8f076a4a79473c"))
        self.assertFalse(Path("evaluation/m18/results/v2/formal").exists())

    def test_decoder_failure_is_observed_but_reraised_without_action(self):
        value=case(M18Cohort.B,M18Difficulty.EASY); observer=M18V2BudgetDiagnosticObserver(value,"m18_direct_tool_calling_v1")
        with self.assertRaises(ValueError): runtime().dry_run(value,DecoderFailure([]),diagnostic_observer=observer)
        self.assertEqual((observer.last_action_type,observer.decoder_failure,observer.decoder_failure_kind),(None,True,"invalid_action_encoding"))
        with self.assertRaises(ValueError): runtime().dry_run(value,DecoderFailure([]),diagnostic_observer=BrokenObserver())

    def test_ideal_behavior_equivalence_all_concrete_comparator_structures(self):
        """The complete 4 x 4 ideal matrix: observer presence is behavior-free."""
        structures=(case(M18Cohort.A,M18Difficulty.HARD),case(M18Cohort.B,M18Difficulty.MEDIUM),
                    case(M18Cohort.C,M18Difficulty.MEDIUM,M18FailureSubtype.RECOVERABLE),
                    case(M18Cohort.C,M18Difficulty.MEDIUM,M18FailureSubtype.INVALID))
        for value in structures:
            for kind in ("mind_lite_v11","direct_tool_calling","react","plan_and_execute"):
                with self.subTest(case=value.case_id,comparator=kind):
                    normal=runtime().dry_run(value,concrete(kind,value))
                    observer=M18V2BudgetDiagnosticObserver(value,"m18_"+kind+"_v1")
                    diagnosed=runtime().dry_run(value,concrete(kind,value),diagnostic_observer=observer)
                    self.assertEqual(signature(normal),signature(diagnosed))

    def test_completion_then_continue_all_concrete_comparator_structures(self):
        structures=(case(M18Cohort.A,M18Difficulty.HARD),case(M18Cohort.B,M18Difficulty.MEDIUM),
                    case(M18Cohort.C,M18Difficulty.MEDIUM,M18FailureSubtype.RECOVERABLE),
                    case(M18Cohort.C,M18Difficulty.MEDIUM,M18FailureSubtype.INVALID))
        for value in structures:
            base,_=concrete_payloads(value,include_answer=False)
            # Replaying the last legal action after the public terminal state
            # is a legal submitted tool request; frozen runtime owns rejection.
            continued=base+[base[-1],base[-1]]
            for kind in ("mind_lite_v11","direct_tool_calling","react","plan_and_execute"):
                with self.subTest(case=value.case_id,comparator=kind):
                    observer=M18V2BudgetDiagnosticObserver(value,"m18_"+kind+"_v1")
                    result=runtime().dry_run(value,concrete(kind,value,continued),diagnostic_observer=observer)
                    replay=replay_public_completion(value.public.to_dict(),tuple(observer.trace))
                    self.assertTrue(replay["completion_reached"])
                    self.assertGreater(replay["post_completion_actions"],0)
                    self.assertFalse(replay["answer_emitted_by_completion"])
                    self.assertIn(observer.last_action_type,{"tool_call","fail"})
                    self.assertEqual(result.terminal.value,"budget_exhausted")

    def test_tool_and_invalid_exhaustion_actual_concrete_paths(self):
        hard=case(M18Cohort.A,M18Difficulty.HARD)
        invalid=case(M18Cohort.C,M18Difficulty.MEDIUM,M18FailureSubtype.INVALID)
        for kind in ("mind_lite_v11","direct_tool_calling","react","plan_and_execute"):
            for value, expected in ((hard,"tool_attempt_limit"),(invalid,"invalid_action_limit")):
                base,_=concrete_payloads(value,include_answer=False)
                observer=M18V2BudgetDiagnosticObserver(value,"m18_"+kind+"_v1")
                result=runtime().dry_run(value,concrete(kind,value,base+[base[-1],base[-1]]),diagnostic_observer=observer)
                record=build_diagnostic_record(value,"m18_direct_tool_calling_v1",result,observer)
                with self.subTest(comparator=kind,cause=expected):
                    self.assertEqual((result.terminal.value,observer.exhaustion_cause,record.exhausted_budget_dimension),
                                     ("budget_exhausted",expected,expected))
                    self.assertEqual(record.telemetry["action_cycles_used"],result.budget.action_cycles)
                    self.assertEqual(record.telemetry["tool_attempts_used"],result.budget.tool_attempts)

    def test_decoder_failure_equivalence_and_last_action_provenance(self):
        value=case(M18Cohort.B,M18Difficulty.EASY)
        malformed="{not-json"
        for kind in ("mind_lite_v11","direct_tool_calling","react","plan_and_execute"):
            with self.subTest(comparator=kind):
                with self.assertRaises(Exception) as normal: runtime().dry_run(value,concrete(kind,value,[malformed]))
                observer=M18V2BudgetDiagnosticObserver(value,"m18_"+kind+"_v1")
                with self.assertRaises(type(normal.exception)): runtime().dry_run(value,concrete(kind,value,[malformed]),diagnostic_observer=observer)
                self.assertEqual((observer.last_action_type,observer.decoder_failure,observer.decoder_failure_kind),(None,True,"malformed_output"))
        # A submitted tool remains the last action even if the next decode fails.
        actions,_=concrete_payloads(value,include_answer=False)
        observer=M18V2BudgetDiagnosticObserver(value,"m18_direct_tool_calling_v1")
        with self.assertRaises(Exception): runtime().dry_run(value,concrete("direct_tool_calling",value,[actions[0],malformed]),diagnostic_observer=observer)
        self.assertEqual((observer.last_action_type,observer.decoder_failure_kind),("tool_call","malformed_output"))

    def test_plan_planner_and_executor_stage_provenance_and_observer_isolation(self):
        value=case(M18Cohort.B,M18Difficulty.EASY); malformed="{not-json"
        # Planner is supplied by the trusted Plan wrapper, so a malformed
        # planner result never becomes a public action.
        class BadPlanner(PlanProvider):
            def plan(self,request): return malformed
        observer=M18V2BudgetDiagnosticObserver(value,"m18_plan_and_execute_v1")
        with self.assertRaises(Exception): runtime().dry_run(value,M18V2PlanAdapter(BadPlanner("",[])),diagnostic_observer=observer)
        self.assertEqual((observer.last_action_type,observer.decoder_failure_stage),(None,"plan_planner"))
        valid_plan=concrete_payloads(value)[1]
        observer=M18V2BudgetDiagnosticObserver(value,"m18_plan_and_execute_v1")
        with self.assertRaises(Exception): runtime().dry_run(value,M18V2PlanAdapter(PlanProvider(valid_plan,[malformed])),diagnostic_observer=observer)
        self.assertEqual((observer.last_action_type,observer.decoder_failure_stage),(None,"plan_executor"))
        with self.assertRaises(Exception): runtime().dry_run(value,M18V2PlanAdapter(BadPlanner("",[])),diagnostic_observer=BrokenObserver())

    def test_plan_replan_stage_provenance_preserves_decoder_semantics(self):
        value=case(M18Cohort.C,M18Difficulty.EASY,M18FailureSubtype.INVALID)
        caps=value.public.to_dict()["capabilities"]
        valid=json.dumps({"steps":[{"step_id":"s0","subgoal":"public","capability_id":caps[0]["tool_id"]}]})
        wrong=json.dumps({"action":"tool_call","tool_name":caps[1]["tool_id"],"parameters":{"value":value.public.to_dict()["task_config"]["initial_value"]}})
        class ReplanProvider:
            transport_attempts_per_logical_call=1
            def __init__(self): self.plans=[valid,"{bad"]; self.actions=[wrong]; self.calls=0
            def plan(self,request): self.calls+=1; return self.plans.pop(0)
            def execute(self,request): self.calls+=1; return self.actions.pop(0)
        normal_provider=ReplanProvider()
        with self.assertRaises(Exception) as normal: runtime().dry_run(value,M18V2PlanAdapter(normal_provider))
        diagnostic_provider=ReplanProvider(); observer=M18V2BudgetDiagnosticObserver(value,"m18_plan_and_execute_v1")
        with self.assertRaises(type(normal.exception)): runtime().dry_run(value,M18V2PlanAdapter(diagnostic_provider),diagnostic_observer=observer)
        self.assertEqual((normal_provider.calls,diagnostic_provider.calls,observer.last_action_type,observer.decoder_failure_stage),(3,3,"tool_call","plan_replan"))
        with self.assertRaises(type(normal.exception)): runtime().dry_run(value,M18V2PlanAdapter(ReplanProvider()),diagnostic_observer=BrokenObserver())

    def test_diagnostic_runner_systematic_stop_persists_and_transients_do_not_stop(self):
        plan=M18V2BudgetDiagnosticPlan.from_repository(Path("."))
        with TemporaryDirectory() as tmp:
            runner=M18V2BudgetDiagnosticRunner(plan,result_root=Path(tmp))
            with self.assertRaises(M18V2SystematicProviderStop): runner.execute(lambda _: FailingPlanProvider(),limit=5)
            stop=runner.store.systematic_stop(); self.assertIsNotNone(stop)
            self.assertEqual(stop.evidence_count,2); self.assertGreater(len(runner.store.missing()),0)
            self.assertNotIn("diagnostic-secret",runner.store.systematic_stop_path.read_text())
            with self.assertRaises(M18V2SystematicProviderStop): M18V2BudgetDiagnosticRunner(plan,result_root=Path(tmp)).execute(lambda _: FailingPlanProvider(),limit=1)

    def test_strict_tamper_trace_bound_and_secret_firewall(self):
        value=case(); result,record=run(value,ref_actions(value))
        payload=record.to_dict()
        protected=("exhausted_budget_dimension","action_cycles_used","tool_attempts_used","invalid_actions","recoverable_failures","logical_provider_calls","transport_attempts","last_action_type","decoder_failure_kind","answer_emitted","first_answer_step","public_completion_before_first_answer")
        for name in protected:
            bad=json.loads(json.dumps(payload))
            if name in bad["telemetry"]: bad["telemetry"][name] = 99 if isinstance(bad["telemetry"][name],int) else "tampered"
            elif name=="exhausted_budget_dimension": bad[name]="action_cycle_limit"
            with self.subTest(field=name):
                with self.assertRaises(ValueError): type(record).from_dict(bad)
        observer=M18V2BudgetDiagnosticObserver(value,"m18_direct_tool_calling_v1")
        action=ref_actions(value,False)[0].to_dict()
        action["payload"]["parameters"]["token"]="diagnostic-secret sk-test-123 BearerSecretXYZ supersecretvalue"
        for _ in range(7):
            observer.observe("interaction",action=action,outcome={"category":"success"},public_state={"completed_steps":0},budget=result.budget)
        self.assertEqual(len(observer.trace),6)
        text=json.dumps(observer.trace)
        for secret in ("diagnostic-secret","sk-test-123","BearerSecretXYZ","supersecretvalue"):
            self.assertNotIn(secret,text)

        # Hash-bound admission covers top-level condition, unknown keys, and
        # the complete ordered public trace, not merely telemetry counters.
        for mutate in (
            lambda x: x.__setitem__("condition_id","tampered"),
            lambda x: x.__setitem__("unknown_key",True),
            lambda x: x["public_trace"][0].__setitem__("step_index",2),
            lambda x: x["public_trace"][0].__setitem__("action_cycles_used",99),
            lambda x: x["public_trace"].append(dict(x["public_trace"][0])),
        ):
            bad=json.loads(json.dumps(payload)); mutate(bad)
            with self.assertRaises(ValueError): type(record).from_dict(bad)

    def test_observer_exceptions_at_first_intermediate_and_terminal_are_behavior_free(self):
        value=case(M18Cohort.A,M18Difficulty.HARD); actions=ref_actions(value)
        normal=runtime().dry_run(value,Script(actions))
        class FailingAt:
            def __init__(self,at): self.at=at; self.calls=0
            def observe(self,*args,**kwargs):
                self.calls+=1
                if self.calls==self.at: raise RuntimeError("observer failure")
        for at in (1,2,5,6):
            with self.subTest(event=at):
                observed=runtime().dry_run(value,Script(actions),diagnostic_observer=FailingAt(at))
                self.assertEqual(signature(normal),signature(observed))
        # A terminal budget branch is also observationally fail-safe.
        observer=FailingAt(1)
        result=runtime().dry_run(value,GateFailure("action_cycle_limit"),diagnostic_observer=observer)
        self.assertEqual(result.terminal.value,"budget_exhausted")

    def test_exhaustion_source_mapping_is_complete(self):
        # These are the only external budget-exhaustion reasons emitted by the
        # frozen episode/call-gate.  Every one projects to a typed dimension.
        expected={"action_cycle_limit":"action_cycle_limit","tool_attempt_limit":"tool_attempt_limit",
                  "logical_provider_call_limit":"logical_provider_call_limit",
                  "invalid_action_threshold_reached":"invalid_action_limit",
                  "recoverable_failure_threshold_reached":"recoverable_failure_limit"}
        from src.evaluation.m18_v2_runtime import m18_v2_exhaustion_cause
        self.assertEqual({reason:m18_v2_exhaustion_cause(reason).value for reason in expected},expected)

if __name__=="__main__": unittest.main()
