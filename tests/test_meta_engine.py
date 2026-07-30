"""Tests for deterministic, selection-only M9 MetaInferenceEngine."""

from __future__ import annotations
import unittest
from src.core.belief import Belief
from src.core.inference_registry import InferenceStrategyRegistry
from src.core.inference_strategy import InferenceStrategy
from src.core.meta_engine import MetaInferenceEngine
from src.core.meta_inference import MetaInferenceDecisionStatus
from src.core.observation import Observation
from src.core.runtime import RuntimeController
from src.core.task import Goal, Task

class Stub:
    def __init__(self): self.calls = 0
    def infer(self, observation: Observation, belief: Belief) -> Belief:
        self.calls += 1; return belief

def task(required=()):
    return Task(Goal("goal", ("done",)), {"value": "ready"}, metadata={"required_inference_capabilities": list(required)})
def strategy(name, caps):
    return InferenceStrategy(name, name, caps)

class MetaInferenceEngineTest(unittest.TestCase):
    def setUp(self):
        self.state = RuntimeController.initialize()
    def test_one_match_and_extra_capabilities(self):
        reg = InferenceStrategyRegistry(); impl = Stub()
        reg.register(strategy("append", ("incremental", "extra")), impl)
        decision = MetaInferenceEngine(reg).select(task(("incremental",)), self.state)
        self.assertEqual(decision.status, MetaInferenceDecisionStatus.SELECTED)
        self.assertEqual(decision.selected_strategy, "append")
        self.assertEqual(decision.evidence[0].evidence_type, "capability_match")
        self.assertEqual(impl.calls, 0)
    def test_empty_and_nonmatching_registries_are_unavailable(self):
        self.assertEqual(MetaInferenceEngine(InferenceStrategyRegistry()).select(task(("x",)), self.state).status, MetaInferenceDecisionStatus.UNAVAILABLE)
        reg = InferenceStrategyRegistry(); reg.register(strategy("append", ("incremental",)), Stub())
        self.assertEqual(MetaInferenceEngine(reg).select(task(("missing",)), self.state).status, MetaInferenceDecisionStatus.UNAVAILABLE)
    def test_multiple_matches_are_rejected_without_arbitrary_choice(self):
        reg = InferenceStrategyRegistry(); reg.register(strategy("a", ("incremental",)), Stub()); reg.register(strategy("b", ("incremental", "extra")), Stub())
        decision = MetaInferenceEngine(reg).select(task(("incremental",)), self.state)
        self.assertEqual(decision.status, MetaInferenceDecisionStatus.REJECTED); self.assertIsNone(decision.selected_strategy)
    def test_engines_are_registry_isolated_and_validate_inputs(self):
        left = InferenceStrategyRegistry(); left.register(strategy("left", ("x",)), Stub())
        right = InferenceStrategyRegistry(); right.register(strategy("right", ("x",)), Stub())
        self.assertEqual(MetaInferenceEngine(left).select(task(("x",)), self.state).selected_strategy, "left")
        self.assertEqual(MetaInferenceEngine(right).select(task(("x",)), self.state).selected_strategy, "right")
        with self.assertRaises(TypeError): MetaInferenceEngine({})
        with self.assertRaises(TypeError): MetaInferenceEngine(left).select({}, self.state)

if __name__ == "__main__": unittest.main()
