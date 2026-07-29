import unittest
from src.core.agent import GoalDirectedAgent
from src.core.result import AgentStatus, TerminationReason
from src.core.task import Goal, Task
from src.core.tool import ToolRegistry
from src.tools.calculator import CalculatorTool
class AgentTest(unittest.TestCase):
    def setUp(self): self.goal=Goal("g",("c",)); self.registry=ToolRegistry(); self.registry.register(CalculatorTool()); self.agent=GoalDirectedAgent(self.registry)
    def test_direct_and_zero(self):
        task=Task(self.goal,{"value":"ready","expected_answer":"ready"}); done=self.agent.run(task,2); zero=self.agent.run(task,0)
        self.assertEqual(done.status,AgentStatus.COMPLETED); self.assertEqual(done.answer,"ready"); self.assertEqual(done.cycles_completed,1)
        self.assertEqual(zero.status,AgentStatus.INCOMPLETE); self.assertEqual(zero.cycles_completed,0)
    def test_direct_mismatch_calculator_and_failure(self):
        mismatch=self.agent.run(Task(self.goal,{"value":"x","expected_answer":"y"}),3)
        calc=self.agent.run(Task(self.goal,{"operation":"multiply","operands":[17,23],"expected_answer":391}),1)
        bad=self.agent.run(Task(self.goal,{}),1)
        self.assertEqual(mismatch.status,AgentStatus.INCOMPLETE); self.assertEqual(mismatch.cycles_completed,1)
        self.assertEqual(calc.status,AgentStatus.COMPLETED); self.assertEqual(calc.answer,391); self.assertEqual(calc.final_state.observation.source,"tool:calculator")
        self.assertEqual(bad.termination_reason,TerminationReason.UNSUPPORTED_TASK)
    def test_validation_and_missing_tool(self):
        with self.assertRaises(TypeError): GoalDirectedAgent({})
        with self.assertRaises(TypeError): self.agent.run({},1)
        with self.assertRaises(TypeError): self.agent.run(Task(self.goal,{}),True)
        with self.assertRaises(ValueError): self.agent.run(Task(self.goal,{}),-1)
        empty=GoalDirectedAgent(ToolRegistry()).run(Task(self.goal,{"operation":"add","operands":[1,2],"expected_answer":3}),1)
        self.assertEqual(empty.termination_reason,TerminationReason.TOOL_FAILURE)
