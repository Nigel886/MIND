"""Synthetic fidelity tests for the M18 Plan-and-Execute baseline."""
from __future__ import annotations
import unittest
from src.core.task import Goal,Task
from src.core.tool import CapabilityDescriptor
from src.evaluation.contracts import EvaluationCase,EvaluationFeedback,EvaluationFeedbackType
from src.evaluation.execution import AgentStepInput,EvaluationBudget,EvaluationBudgetState
from src.evaluation.m18_plan_and_execute import M18PlanAndExecuteBaseline,M18PlanConditionError,M18PlanTerminationReason,PublicExecutionPlan,m18_plan_artifacts

class FakeProvider:
    def __init__(self,plans,actions):self.plans=list(plans);self.actions=list(actions);self.plan_requests=[];self.executor_requests=[]
    def plan(self,r):self.plan_requests.append(r);return self.plans.pop(0)
    def execute(self,r):self.executor_requests.append(r);return self.actions.pop(0)
def _keys(v):
    if isinstance(v,dict):return set(v)|set().union(*(_keys(x) for x in v.values()))
    if isinstance(v,list):return set().union(*(_keys(x) for x in v)) if v else set()
    return set()
PLAN='{"steps":[{"step_id":"one","subgoal":"get value","capability_id":"first"},{"step_id":"two","subgoal":"transform value","capability_id":"transform"},{"step_id":"three","subgoal":"submit result","capability_id":null}]}'
REVISED='{"steps":[{"step_id":"revised","subgoal":"try transform","capability_id":"transform"}]}'
class PlanExecuteTests(unittest.TestCase):
 def setUp(self):
  self.case=EvaluationCase("m18.plan.synthetic",Task(Goal("complete",("answer",)),{"value":4,"expected_answer":"private"},metadata={"difficulty":"private"}))
  self.tools=(CapabilityDescriptor("first","First","distractor",{"type":"object"}),CapabilityDescriptor("transform","Transform","public tool",{"type":"object"}))
 def step(self,fb,used=0):return AgentStepInput(self.case,fb,EvaluationBudgetState(EvaluationBudget(5,3),steps_used=used))
 def test_initial_planner_creates_immutable_plan_and_executor_receives_it(self):
  p=FakeProvider([PLAN],['{"action":"tool_call","tool_name":"first","parameters":{"value":4}}']) ; b=M18PlanAndExecuteBaseline(p,self.tools)
  result=b.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
  self.assertEqual(b.plan.to_dict(),PublicExecutionPlan.from_dict(__import__('json').loads(PLAN)).to_dict());self.assertEqual(p.planner_calls if hasattr(p,'planner_calls') else len(p.plan_requests),1)
  self.assertEqual(p.executor_requests[0].to_dict()["plan"],b.plan.to_dict());self.assertFalse(result.request_termination)
  with self.assertRaises(Exception):b.plan.steps[0].step_id="x"
 def test_dependent_multitool_progression_uses_observation_and_nonfirst_tool(self):
  p=FakeProvider([PLAN],['{"action":"tool_call","tool_name":"first","parameters":{}}','{"action":"tool_call","tool_name":"transform","parameters":{"value":8}}','{"action":"answer","answer":16}']);b=M18PlanAndExecuteBaseline(p,self.tools)
  b.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
  b.step(self.step(EvaluationFeedback(EvaluationFeedbackType.TOOL_RESPONSE,{"output":8,"ground_truth":"private"}),1))
  final=b.step(self.step(EvaluationFeedback(EvaluationFeedbackType.TOOL_RESPONSE,{"output":16}),2))
  self.assertEqual(final.action.to_dict()["payload"],{"answer":16});self.assertEqual(b.cursor,2);self.assertEqual(b.tool_calls,2)
  self.assertEqual(p.executor_requests[1].to_dict()["current_feedback"],{"feedback_type":"tool_response","payload":{"output":8}});self.assertNotIn("ground_truth",_keys(p.executor_requests[1].to_dict()))
 def test_recoverable_failure_and_invalid_action_each_allow_one_replan(self):
  p=FakeProvider([PLAN,REVISED],['{"action":"tool_call","tool_name":"first","parameters":{}}','{"action":"tool_call","tool_name":"transform","parameters":{}}']);b=M18PlanAndExecuteBaseline(p,self.tools)
  b.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
  b.step(self.step(EvaluationFeedback(EvaluationFeedbackType.TOOL_FAILURE,{"category":"recoverable_failure","correct_tool":"private"}),1))
  self.assertEqual(b.replan_calls,1);self.assertEqual(b.plan.to_dict(),PublicExecutionPlan.from_dict(__import__('json').loads(REVISED)).to_dict());self.assertNotIn("correct_tool",_keys(p.plan_requests[1].to_dict()))
  terminal=b.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INVALID_ACTION,{"correct_action":"private"}),2))
  self.assertTrue(terminal.request_termination);self.assertEqual(terminal.action.to_dict()["payload"]["reason"],"replan_limit_reached");self.assertEqual(b.replan_calls,1)
 def test_unrecoverable_and_budget_terminate_without_provider(self):
  p=FakeProvider([],[]);b=M18PlanAndExecuteBaseline(p,self.tools)
  self.assertTrue(b.step(self.step(EvaluationFeedback(EvaluationFeedbackType.TOOL_FAILURE,{"category":"unrecoverable_failure"}))).request_termination)
  self.assertTrue(b.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT),5)).request_termination);self.assertEqual(len(p.plan_requests),0)
 def test_strict_planner_and_executor_outputs_have_no_retry(self):
  p=FakeProvider(['text {"steps":[]}'],[]);b=M18PlanAndExecuteBaseline(p,self.tools)
  with self.assertRaises(M18PlanConditionError):b.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
  self.assertEqual(len(p.plan_requests),1)
  p=FakeProvider([PLAN],['{"action":"answer","answer":"x","rationale":"bad"}']);b=M18PlanAndExecuteBaseline(p,self.tools)
  with self.assertRaises(M18PlanConditionError):b.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
  self.assertEqual(len(p.executor_requests),1)
 def test_no_react_history_mind_state_or_truth_and_artifacts_deterministic(self):
  p=FakeProvider([PLAN],['{"action":"answer","answer":"ok"}']);b=M18PlanAndExecuteBaseline(p,self.tools)
  b.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT,{"evaluator_success":True})))
  self.assertFalse({"_history","_scratchpad","_runtime_state","_belief","_provider_history"}&set(vars(b)));self.assertNotIn("evaluator_success",_keys(p.plan_requests[0].to_dict()))
  self.assertEqual(m18_plan_artifacts(),m18_plan_artifacts());self.assertTrue(all(len(x)==64 for x in m18_plan_artifacts().to_dict().values()))
if __name__=="__main__":unittest.main()
