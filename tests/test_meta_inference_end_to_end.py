"""End-to-end validation for the completed M9 Meta-Inference layer."""
from __future__ import annotations
import unittest
from src.core.agent import GoalDirectedAgent
from src.core.inference_registry import InferenceStrategyRegistry
from src.core.inference_strategy import InferenceStrategy
from src.core.meta_engine import MetaInferenceEngine
from src.core.result import AgentStatus, TerminationReason
from src.core.task import Goal, Task
from src.core.tool import ToolRegistry
from src.tools.calculator import CalculatorTool
class Stub:
    def __init__(self): self.calls=0
    def infer(self, observation, belief): self.calls+=1; return belief
def task(data, required=()): return Task(Goal("complete",("correct",)),data,metadata={"required_inference_capabilities":list(required)})
def engine(*entries):
    registry=InferenceStrategyRegistry(); implementations=[]
    for name,caps in entries:
        impl=Stub(); implementations.append(impl); registry.register(InferenceStrategy(name,name,caps),impl)
    return MetaInferenceEngine(registry),implementations
class MetaInferenceEndToEndTest(unittest.TestCase):
    def test_selected_direct_is_deterministic_and_never_executes_strategy(self):
        selected, implementations=engine(("append",("incremental",))); agent=GoalDirectedAgent(ToolRegistry(),selected)
        first=agent.run(task({"value":"ready","expected_answer":"ready"},("incremental",)),1)
        second=agent.run(task({"value":"ready","expected_answer":"ready"},("incremental",)),1)
        self.assertEqual((first.status,first.answer,first.evidence[0]),(AgentStatus.COMPLETED,"ready",{"type":"meta_inference","status":"selected","selected_strategy":"append"}))
        self.assertEqual((first.status,first.termination_reason,first.answer,first.evidence),(second.status,second.termination_reason,second.answer,second.evidence))
        self.assertEqual(implementations[0].calls,0)
    def test_unavailable_and_ambiguous_fail_without_fallback(self):
        unavailable=GoalDirectedAgent(ToolRegistry(),engine()[0]).run(task({"value":"ready","expected_answer":"ready"},("x",)),1)
        ambiguous=GoalDirectedAgent(ToolRegistry(),engine(("a",("x",)),("b",("x",)))[0]).run(task({"value":"ready","expected_answer":"ready"},("x",)),1)
        for result,status in ((unavailable,"unavailable"),(ambiguous,"rejected")):
            self.assertEqual((result.status,result.termination_reason,result.cycles_completed),(AgentStatus.FAILED,TerminationReason.POLICY_FAILURE,0))
            self.assertEqual(result.evidence[0]["status"],status); self.assertFalse(any(item["type"]=="policy" for item in result.evidence))
    def test_selected_calculator_preserves_tool_completion_flow(self):
        tools=ToolRegistry(); tools.register(CalculatorTool())
        result=GoalDirectedAgent(tools,engine(("append",("incremental",)))[0]).run(task({"operation":"multiply","operands":[17,23],"expected_answer":391},("incremental",)),1)
        self.assertEqual((result.status,result.answer),(AgentStatus.COMPLETED,391)); self.assertEqual(result.evidence[0]["selected_strategy"],"append")
        self.assertTrue(any(item["type"]=="tool" and item["success"] for item in result.evidence))
    def test_m8_paths_and_agent_registries_remain_isolated(self):
        direct=GoalDirectedAgent(ToolRegistry()).run(task({"value":"ready","expected_answer":"ready"}),1)
        unsupported=GoalDirectedAgent(ToolRegistry()).run(task({"unsupported":True}),1)
        bounded=GoalDirectedAgent(ToolRegistry()).run(task({"value":"wrong","expected_answer":"right"}),0)
        self.assertEqual(direct.status,AgentStatus.COMPLETED); self.assertEqual(unsupported.termination_reason,TerminationReason.UNSUPPORTED_TASK); self.assertEqual(bounded.termination_reason,TerminationReason.MAX_CYCLES_REACHED)
        self.assertFalse(any(item["type"]=="meta_inference" for item in direct.evidence))
        left=GoalDirectedAgent(ToolRegistry(),engine(("left",("x",)))[0]).run(task({"value":"ready","expected_answer":"ready"},("x",)),1)
        right=GoalDirectedAgent(ToolRegistry(),engine(("right",("x",)))[0]).run(task({"value":"ready","expected_answer":"ready"},("x",)),1)
        self.assertEqual((left.evidence[0]["selected_strategy"],right.evidence[0]["selected_strategy"]),("left","right"))
if __name__=="__main__": unittest.main()
