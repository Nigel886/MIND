import unittest
from src.evaluation.direct_tool_calling import FakeDirectActionProvider, DirectActionProviderResponse, DirectToolCallingEvaluationAgent
from src.evaluation.contracts import EvaluationActionType, EvaluationFeedbackType
from src.evaluation.m16_benchmark_contracts import *
from src.evaluation.m16_benchmark_runner import M16BenchmarkRunner, M16RunActor
from src.evaluation.m16_mind_session_adapter import M16MINDSessionEvaluationAdapter
from src.core.meta_inference import DecisionEvidence, MetaInferenceDecision, MetaInferenceDecisionStatus
from src.integration.meta_inference_adapter import IntegrationSelected
from evaluation.tasks.m16_benchmark_dry_run_fixtures import get_m16_benchmark_dry_run_cases
class RunnerTests(unittest.TestCase):
 def test_direct_run(self):
  m=M16FormalExecutionManifest("1.1.0","1.0.0","suite","split","1","config",repetition_count=1)
  def actor():
   p=FakeDirectActionProvider({EvaluationFeedbackType.INITIAL_INPUT:DirectActionProviderResponse(EvaluationActionType.ANSWER,{"answer":"copper-fern"})})
   return M16RunActor(DirectToolCallingEvaluationAgent(p,{"calculator":{}},"dev"),[])
  r=M16BenchmarkRunner(m,{M16BaselineID.MIND_LITE_V1:actor,M16BaselineID.DIRECT_TOOL_CALLING:actor}); case=get_m16_benchmark_dry_run_cases()[0]
  d=[x for x in r.schedule((case,)) if x.baseline_id is M16BaselineID.DIRECT_TOOL_CALLING][0]
  self.assertTrue(r.execute(case,d).success)
 def test_mind_direct_run(self):
  m=M16FormalExecutionManifest("1.1.0","1.0.0","suite","split","1","config",repetition_count=1)
  def mind():
   def resolve(task,state): return IntegrationSelected(MetaInferenceDecision(MetaInferenceDecisionStatus.SELECTED,"development",(DecisionEvidence("development","selected"),)))
   return M16RunActor(M16MINDSessionEvaluationAdapter(resolve),[])
  r=M16BenchmarkRunner(m,{M16BaselineID.MIND_LITE_V1:mind,M16BaselineID.DIRECT_TOOL_CALLING:mind}); case=get_m16_benchmark_dry_run_cases()[0]
  d=[x for x in r.schedule((case,)) if x.baseline_id is M16BaselineID.MIND_LITE_V1][0]
  self.assertTrue(r.execute(case,d).success)
 def test_direct_calculator_two_step_run(self):
  m=M16FormalExecutionManifest("1.1.0","1.0.0","suite","split","1","config",repetition_count=1)
  def actor():
   p=FakeDirectActionProvider({EvaluationFeedbackType.INITIAL_INPUT:DirectActionProviderResponse(EvaluationActionType.TOOL_CALL,{"tool_name":"calculator","parameters":{"operation":"add","operands":[19,-7]}}),EvaluationFeedbackType.TOOL_RESPONSE:DirectActionProviderResponse(EvaluationActionType.ANSWER,{"answer":12})})
   return M16RunActor(DirectToolCallingEvaluationAgent(p,{"calculator":{}},"dev"),[])
  r=M16BenchmarkRunner(m,{M16BaselineID.MIND_LITE_V1:actor,M16BaselineID.DIRECT_TOOL_CALLING:actor}); case=get_m16_benchmark_dry_run_cases()[1]
  d=[x for x in r.schedule((case,)) if x.baseline_id is M16BaselineID.DIRECT_TOOL_CALLING][0]; result=r.execute(case,d)
  self.assertTrue(result.success); self.assertEqual((result.agent_steps,result.tool_calls),(2,1))
 def test_mind_calculator_run(self):
  m=M16FormalExecutionManifest("1.1.0","1.0.0","suite","split","1","config",repetition_count=1)
  def mind():
   def resolve(task,state): return IntegrationSelected(MetaInferenceDecision(MetaInferenceDecisionStatus.SELECTED,"development",(DecisionEvidence("development","selected"),)))
   return M16RunActor(M16MINDSessionEvaluationAdapter(resolve),[])
  r=M16BenchmarkRunner(m,{M16BaselineID.MIND_LITE_V1:mind,M16BaselineID.DIRECT_TOOL_CALLING:mind}); case=get_m16_benchmark_dry_run_cases()[1]
  d=[x for x in r.schedule((case,)) if x.baseline_id is M16BaselineID.MIND_LITE_V1][0]
  self.assertTrue(r.execute(case,d).success)
