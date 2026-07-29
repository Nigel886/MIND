import unittest
from src.core.goal_policy import GoalAwarePolicyEngine
from src.core.policy import PolicyEngine
from src.core.runtime import RuntimeController
from src.core.task import Goal, Task
class GoalPolicyTest(unittest.TestCase):
    def setUp(self): self.goal=Goal("g",("c",)); self.state=RuntimeController.initialize()
    def test_direct_candidate_does_not_decide_completion(self):
        task=Task(self.goal,{"value":"wrong","expected_answer":"right"}); policy=GoalAwarePolicyEngine.generate(task,self.state)
        self.assertEqual(policy.action,"produce_answer"); self.assertEqual(policy.parameters,{"answer":"wrong"}); self.assertNotIn("expected_answer",policy.parameters)
    def test_calculator_and_unsupported(self):
        task=Task(self.goal,{"operation":"multiply","operands":[17,23],"expected_answer":391}); policy=GoalAwarePolicyEngine.generate(task,self.state)
        self.assertEqual(policy.action,"call_tool"); self.assertEqual(policy.parameters["tool_name"],"calculator"); self.assertEqual(policy.parameters["tool_parameters"]["operands"],[17,23])
        self.assertEqual(GoalAwarePolicyEngine.generate(Task(self.goal,{}),self.state).action,"fail_task")
    def test_validation_ambiguity_and_statelessness(self):
        with self.assertRaises(TypeError): GoalAwarePolicyEngine.generate({},self.state)
        with self.assertRaises(TypeError): GoalAwarePolicyEngine.generate(Task(self.goal,{}),{})
        mixed=Task(self.goal,{"value":"x","expected_answer":"x","operation":"add","operands":[1,2]})
        self.assertEqual(GoalAwarePolicyEngine.generate(mixed,self.state).action,"fail_task")
        self.assertIsNotNone(PolicyEngine.generate(self.state.belief))
