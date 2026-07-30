"""Tests for explicit Meta-Inference integration in GoalDirectedAgent."""
from __future__ import annotations
import unittest
from src.core.agent import GoalDirectedAgent
from src.core.inference_registry import InferenceStrategyRegistry
from src.core.inference_strategy import InferenceStrategy
from src.core.meta_engine import MetaInferenceEngine
from src.core.result import AgentStatus, TerminationReason
from src.core.task import Goal, Task
from src.core.tool import ToolRegistry

class Impl:
    def infer(self, observation, belief): return belief
def task(required=()):
    return Task(Goal("return", ("correct",)), {"value":"ready","expected_answer":"ready"}, metadata={"required_inference_capabilities":list(required)})
def engine(*caps):
    reg=InferenceStrategyRegistry()
    for name, values in caps: reg.register(InferenceStrategy(name,name,values), Impl())
    return MetaInferenceEngine(reg)

class AgentMetaInferenceTest(unittest.TestCase):
    def test_none_preserves_legacy_behavior(self):
        result=GoalDirectedAgent(ToolRegistry()).run(task(),1)
        self.assertEqual(result.status,AgentStatus.COMPLETED)
        self.assertFalse(any(item["type"]=="meta_inference" for item in result.evidence))
    def test_selected_engine_continues_and_preserves_compact_evidence(self):
        result=GoalDirectedAgent(ToolRegistry(),engine(("append",("incremental",)))).run(task(("incremental",)),1)
        self.assertEqual(result.status,AgentStatus.COMPLETED)
        self.assertEqual(result.evidence[0],{"type":"meta_inference","status":"selected","selected_strategy":"append"})
    def test_unavailable_fails_without_fallback(self):
        result=GoalDirectedAgent(ToolRegistry(),engine()).run(task(("x",)),1)
        self.assertEqual((result.status,result.termination_reason,result.cycles_completed),(AgentStatus.FAILED,TerminationReason.POLICY_FAILURE,0))
        self.assertEqual(result.evidence[0]["status"],"unavailable")
    def test_rejected_fails_and_agents_are_isolated(self):
        ambiguous=GoalDirectedAgent(ToolRegistry(),engine(("a",("x",)),("b",("x",)))).run(task(("x",)),1)
        selected=GoalDirectedAgent(ToolRegistry(),engine(("only",("x",)))).run(task(("x",)),1)
        self.assertEqual(ambiguous.evidence[0]["status"],"rejected")
        self.assertEqual(selected.status,AgentStatus.COMPLETED)

if __name__ == "__main__": unittest.main()
