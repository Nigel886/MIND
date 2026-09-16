"""Concrete MIND/Direct/ReAct/Plan bindings to the M18 v2 runtime."""
from __future__ import annotations
import json
import unittest

from src.evaluation.m18_task_generation import M18Cohort, M18Difficulty, M18FailureSubtype, M18Namespace
from src.evaluation.m18_suite_freeze import formal_suite, pilot_suite
from src.evaluation.m18_v2_runtime import (
    M18BenchmarkRuntimeCondition, M18V2ResultProvenance, M18V2SharedExecutionHarness,
    M18V2MINDAdapter, M18V2DirectAdapter, M18V2ReActAdapter, M18V2PlanAdapter,
    M18V2ProviderCallGate, M18_V2_RUNTIME_ID, m18_v2_concrete_adapters,
)
from src.evaluation.contracts import EvaluationFeedback, EvaluationFeedbackType
from src.evaluation.m18_v2_semantics import M18V2BudgetError, M18V2BudgetState, M18V2EvaluationCategory, generate_m18_v2_case, reference_public_trajectory

HASH="b"*64
class SequenceProvider:
    def __init__(self,responses,attempts=1): self.responses=list(responses); self.transport_attempts_per_logical_call=attempts; self.requests=[]
    def generate(self,request): self.requests.append(request.to_dict()); return self.responses.pop(0)
class PlanProvider:
    def __init__(self,plan,responses,attempts=1): self.plan_text=plan; self.responses=list(responses); self.transport_attempts_per_logical_call=attempts; self.plan_requests=[]; self.execute_requests=[]
    def plan(self,request): self.plan_requests.append(request.to_dict()); return self.plan_text
    def execute(self,request): self.execute_requests.append(request.to_dict()); return self.responses.pop(0)

def runtime():
    c=M18BenchmarkRuntimeCondition.v2(); return M18V2SharedExecutionHarness(c,M18V2ResultProvenance(c,M18_V2_RUNTIME_ID,HASH,"fake_concrete_v2"))
def case(cohort,difficulty,subtype=None): return generate_m18_v2_case(cohort,difficulty,7101,M18Namespace.PILOT,1,subtype)
def raws(value):
    trace=reference_public_trajectory(value); out=[json.dumps({"action":"tool_call","tool_name":a["tool_name"],"parameters":a["parameters"]},separators=(",",":")) for a in trace.actions]
    return out+[json.dumps({"action":"answer","answer":trace.final_public_result},separators=(",",":"))],trace
def plan_for(value):
    caps=value.public.to_dict()["capabilities"]
    return json.dumps({"steps":[{"step_id":f"s{i}","subgoal":"public execution","capability_id":caps[i%len(caps)]["tool_id"]} for i in range(8)]},separators=(",",":"))
def adapter(kind,value,attempts=1):
    data,trace=raws(value)
    if kind=="mind_lite_v11": return M18V2MINDAdapter(SequenceProvider(data,attempts)),trace
    if kind=="direct_tool_calling": return M18V2DirectAdapter(SequenceProvider(data,attempts)),trace
    if kind=="react": return M18V2ReActAdapter(SequenceProvider(data,attempts)),trace
    return M18V2PlanAdapter(PlanProvider(plan_for(value),data,attempts)),trace
def v2_from_v1(old):
    subtype=M18FailureSubtype(old.evaluator.failure_schedule["subtype"]) if old.cohort is M18Cohort.C else None
    return generate_m18_v2_case(old.cohort,old.difficulty,old.generation_seed,old.namespace,int(old.case_id.rsplit(".",1)[1]),subtype)

class M18V2ConcreteAdapterTests(unittest.TestCase):
    def execute_all(self,value):
        results=[]
        for kind in ("mind_lite_v11","direct_tool_calling","react","plan_and_execute"):
            a,t=adapter(kind,value); r=runtime().dry_run(value,a); results.append((kind,r,t,a))
        return results
    def test_all_concrete_adapters_execute_a_hard(self):
        value=case(M18Cohort.A,M18Difficulty.HARD)
        for kind,result,trace,adapter_value in self.execute_all(value):
            with self.subTest(kind=kind):
                self.assertEqual(result.evaluator_outcome,M18V2EvaluationCategory.SUCCESS)
                self.assertEqual((result.budget.action_cycles,result.budget.tool_attempts),(5,4))
                self.assertEqual(result.final_public_state["current_value"],trace.final_public_result)
    def test_b_and_both_c_subtypes_all_concrete(self):
        for value in (case(M18Cohort.B,M18Difficulty.MEDIUM),case(M18Cohort.C,M18Difficulty.MEDIUM,M18FailureSubtype.RECOVERABLE),case(M18Cohort.C,M18Difficulty.MEDIUM,M18FailureSubtype.INVALID)):
            for kind,result,trace,_ in self.execute_all(value):
                with self.subTest(case=value.case_id,kind=kind):
                    self.assertEqual(result.evaluator_outcome,M18V2EvaluationCategory.SUCCESS)
                    self.assertEqual(result.final_public_state["current_value"],trace.final_public_result)
    def test_concrete_transport_and_public_request_firewall(self):
        value=case(M18Cohort.B,M18Difficulty.EASY)
        for kind in ("mind_lite_v11","direct_tool_calling","react","plan_and_execute"):
            a,_=adapter(kind,value,attempts=3); result=runtime().dry_run(value,a)
            self.assertEqual((result.logical_provider_calls,result.transport_attempts),(2 if kind!="plan_and_execute" else 3,(2 if kind!="plan_and_execute" else 3)*3))
            requests = [a.last_request.to_dict()] if kind!="plan_and_execute" else [x.to_dict() for x in a.last_requests if x is not None]
            self.assertNotIn("expected_final_result",str(requests))
    def test_factories_require_all_four_and_v1_is_not_a_v2_adapter(self):
        with self.assertRaises(ValueError): m18_v2_concrete_adapters({})
        value=case(M18Cohort.B,M18Difficulty.EASY); providers={}
        for kind in ("mind_lite_v11","direct_tool_calling","react"): providers[kind]=SequenceProvider(raws(value)[0])
        providers["plan_and_execute"]=PlanProvider(plan_for(value),raws(value)[0])
        self.assertEqual(set(m18_v2_concrete_adapters(providers)),set(providers))
    def test_concrete_provider_gate_blocks_ninth_logical_call(self):
        """Each real comparator's own provider wrapper, not a scripted adapter, is gated."""
        value=case(M18Cohort.B,M18Difficulty.EASY)
        initial=EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)
        for kind in ("mind_lite_v11","direct_tool_calling","react","plan_and_execute"):
            a,_=adapter(kind,value)
            a.initialize(value); gate=M18V2ProviderCallGate(M18V2BudgetState())
            a.next_decision(initial,M18V2BudgetState(),gate)
            a._provider.provider.responses.extend(["{}"] * 8)
            if kind=="plan_and_execute":
                request=a.last_requests[1]
                invoke=lambda: a._provider.execute(request)
                completed=2
            else:
                request=a.last_request
                invoke=lambda: a._provider.generate(request)
                completed=1
            for _ in range(8-completed): invoke()
            self.assertEqual(gate.budget_state.logical_provider_calls,8)
            with self.assertRaises(M18V2BudgetError): invoke()
    def test_immediate_answer_is_not_success_for_all_concrete_adapters(self):
        value=case(M18Cohort.A,M18Difficulty.EASY)
        for kind in ("mind_lite_v11","direct_tool_calling","react","plan_and_execute"):
            if kind=="plan_and_execute":
                a=M18V2PlanAdapter(PlanProvider(plan_for(value),[json.dumps({"action":"answer","answer":0})]))
            else:
                a={"mind_lite_v11":M18V2MINDAdapter,"direct_tool_calling":M18V2DirectAdapter,"react":M18V2ReActAdapter}[kind](SequenceProvider([json.dumps({"action":"answer","answer":0})]))
            with self.subTest(kind=kind):
                self.assertIsNot(runtime().dry_run(value,a).evaluator_outcome,M18V2EvaluationCategory.SUCCESS)
    def test_all_pilot_and_formal_memberships_through_every_concrete_adapter(self):
        totals=[]
        for suite,expected in ((pilot_suite(),18),(formal_suite(),162)):
            complete=0
            for old in suite:
                value=v2_from_v1(old)
                for kind,result,trace,adapter_value in self.execute_all(value):
                    self.assertEqual(result.evaluator_outcome,M18V2EvaluationCategory.SUCCESS)
                    self.assertEqual(result.final_public_state["current_value"],trace.final_public_result)
                    self.assertLessEqual(result.budget.action_cycles,6); self.assertLessEqual(result.budget.tool_attempts,4)
                    complete+=1
            totals.append((complete,expected*4))
        self.assertEqual(totals,[(72,72),(648,648)])

if __name__=="__main__": unittest.main()
