import unittest
from types import SimpleNamespace
from src.evaluation.m16_formal_execution import adapt_formal_envelope, validate_formal_preflight
from src.evaluation.m16_leakage_free import M16PrivateEnvironmentSpecification, M16PrivateTruth
from src.evaluation.contracts import EvaluationCase
from src.core.task import Goal, Task

class FormalEntryTests(unittest.TestCase):
 def test_adapter_is_mechanical_and_private(self):
  task=Task(Goal('x',('x',)),{'value':'public'})
  env=SimpleNamespace(evaluation_case=EvaluationCase('synthetic',task),environment_specification=M16PrivateEnvironmentSpecification('synthetic'),private_truth=M16PrivateTruth('secret','synthetic'),task_family=SimpleNamespace(value='direct_answer'),difficulty=SimpleNamespace(value='easy'))
  adapted=adapt_formal_envelope(env)
  self.assertEqual(adapted.case.evaluation_id,'synthetic'); self.assertEqual(adapted.task_family,'direct_answer')
  self.assertNotIn('secret',str(adapted.case.to_dict()))
 def test_static_preflight_only(self):
  manifest,cases,definitions=validate_formal_preflight()
  self.assertEqual((len(cases),len(definitions)),(96,960)); self.assertEqual(len({x.run_id for x in definitions}),960)
