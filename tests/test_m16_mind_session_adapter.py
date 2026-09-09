import unittest
from src.evaluation.m16_mind_session_adapter import M16MINDSessionEvaluationAdapter
from src.core.meta_inference import DecisionEvidence, MetaInferenceDecision, MetaInferenceDecisionStatus
from src.integration.meta_inference_adapter import IntegrationSelected
from src.evaluation.execution import AgentStepInput, EvaluationBudget, EvaluationBudgetState
from src.evaluation.contracts import EvaluationFeedback, EvaluationFeedbackType, EvaluationActionType
from evaluation.tasks.m16_benchmark_dry_run_fixtures import get_m16_benchmark_dry_run_cases
class MindAdapterTests(unittest.TestCase):
 def test_requires_callable(self):
  with self.assertRaises(TypeError): M16MINDSessionEvaluationAdapter(None)
 def test_public_admission_precedes_private_projection(self):
  seen=[]
  def resolve(task, state):
   seen.append(task.to_dict()); return IntegrationSelected(MetaInferenceDecision(MetaInferenceDecisionStatus.SELECTED,"development",(DecisionEvidence("development","selected"),)))
  case=get_m16_benchmark_dry_run_cases()[0].case
  result=M16MINDSessionEvaluationAdapter(resolve).step(AgentStepInput(case,EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT,{}),EvaluationBudgetState(EvaluationBudget(2,1))))
  self.assertEqual(result.action.action_type,EvaluationActionType.ANSWER)
  self.assertNotIn("expected_answer",seen[0]["input"])
