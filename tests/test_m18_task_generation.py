"""Contract tests for M18 deterministic generation/evaluator foundations."""
from __future__ import annotations
import unittest
from src.evaluation.m18_task_generation import *
class M18GenerationTests(unittest.TestCase):
 def make(self,c,d,seed=701,ns=M18Namespace.PILOT,sub=None):return generate_m18_case(c,d,seed,ns,2,sub)
 def test_schema_and_structural_public_projection(self):
  c=self.make(M18Cohort.A,M18Difficulty.MEDIUM); public=c.public_view().to_dict(); full=c.to_dict()
  self.assertEqual(full["cohort"],"multi_step");self.assertNotIn("difficulty",public);self.assertNotIn("evaluator",public);self.assertNotIn("generation_seed",public)
  self.assertTrue(public["environment_config"]["requires_observation_dependency"])
 def test_a_has_structural_easy_medium_hard_depths(self):
  depths=[self.make(M18Cohort.A,d).public.environment_config["transition_depth"] for d in M18Difficulty]
  self.assertEqual(depths,[1,2,3]);self.assertTrue(self.make(M18Cohort.A,M18Difficulty.HARD).public.environment_config["requires_observation_dependency"])
 def test_b_distractors_and_position_vary_by_seed(self):
  a=self.make(M18Cohort.B,M18Difficulty.HARD,701);b=self.make(M18Cohort.B,M18Difficulty.HARD,702)
  self.assertEqual(len(a.public.tools),4);self.assertNotEqual(a.public.tools,b.public.tools);self.assertEqual(a.public.tools[0]["parameter_schema"],b.public.tools[0]["parameter_schema"])
 def test_c_subtypes_and_environment_are_deterministic_and_identity_neutral(self):
  for sub,category in ((M18FailureSubtype.RECOVERABLE,M18EnvironmentCategory.RECOVERABLE_FAILURE),(M18FailureSubtype.INVALID,M18EnvironmentCategory.INVALID_ACTION)):
   c=self.make(M18Cohort.C,M18Difficulty.EASY,sub=sub);env=M18DeterministicEnvironment();action={"action":"tool_call","tool_name":"x","parameters":{}}
   self.assertEqual(env.apply(c,action,"MIND").category,category);self.assertEqual(env.apply(c,action,"ReAct").to_dict(),env.apply(c,action,"Direct").to_dict())
 def test_evaluator_is_external_trajectory_independent_and_neutral(self):
  c=self.make(M18Cohort.A,M18Difficulty.EASY);e=M18Evaluator();self.assertTrue(e.evaluate(c,c.evaluator.target_answer).success);self.assertTrue(e.evaluate(c,c.evaluator.target_state).success);self.assertEqual(e.evaluate(c,"wrong").category,M18EvaluationCategory.WRONG_ANSWER);self.assertEqual(e.evaluate(c,terminal_reason="budget_exhausted").category,M18EvaluationCategory.BUDGET_EXHAUSTED)
 def test_canonical_hash_seed_and_namespace_separation(self):
  a=self.make(M18Cohort.B,M18Difficulty.MEDIUM,900);same=self.make(M18Cohort.B,M18Difficulty.MEDIUM,900);other=self.make(M18Cohort.B,M18Difficulty.MEDIUM,901);formal=self.make(M18Cohort.B,M18Difficulty.MEDIUM,900,M18Namespace.FORMAL)
  self.assertEqual(a.to_dict(),same.to_dict());self.assertEqual(case_hash(a),case_hash(same));self.assertNotEqual(case_hash(a),case_hash(other));self.assertNotEqual(a.case_id,formal.case_id);self.assertEqual(len(collection_hash((a,same))),64)
 def test_nested_leakage_is_structurally_blocked(self):
  c=self.make(M18Cohort.C,M18Difficulty.HARD,sub=M18FailureSubtype.INVALID);p=c.public_view().to_dict();text=canonical_json(p)
  for key in ("target_answer","target_state","correct_tool","correct_action","difficulty","failure_schedule","evaluator_rule","generation_seed"):self.assertNotIn(key,text)
 def test_primary_fallback_representable_without_generating_suite(self):
  self.assertEqual(M18SuiteDesign(18).case_count,162);self.assertEqual(M18SuiteDesign(10).case_count,90)
 def test_infrastructure_invalid_is_distinct(self):self.assertEqual(M18Evaluator().evaluate("bad").category,M18EvaluationCategory.INFRASTRUCTURE_INVALID)
if __name__=="__main__":unittest.main()
