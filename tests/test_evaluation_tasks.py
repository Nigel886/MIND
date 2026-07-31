"""Tests for immutable, non-executing M10 evaluation task definitions."""

from __future__ import annotations
from dataclasses import FrozenInstanceError
import unittest
from evaluation.tasks.evaluation_task import EvaluationScenario, EvaluationTask
from evaluation.tasks.scenarios import SCENARIO_ORDER
from src.core.task import Goal, Task

def task() -> Task: return Task(Goal("return", ("correct",)), {"value":"ready"})
def evaluation_task(metadata=None) -> EvaluationTask: return EvaluationTask("direct_success","direct value",task(),"direct","completed",{} if metadata is None else metadata)

class EvaluationTaskTest(unittest.TestCase):
    def test_creation_serialization_and_nested_isolation(self):
        metadata={"nested":{"values":[1]}}; item=evaluation_task(metadata); metadata["nested"]["values"].append(2)
        self.assertEqual(item.to_dict()["metadata"],{"nested":{"values":[1]}})
        restored=EvaluationTask.from_dict(item.to_dict()); output=item.to_dict(); output["metadata"]["nested"]["values"].append(3)
        self.assertEqual(restored,item)
        with self.assertRaises(FrozenInstanceError): item.name="other"
        with self.assertRaises(TypeError): item.metadata["nested"]["values"][0]=0
    def test_validation_rejects_invalid_values(self):
        with self.assertRaises(TypeError): EvaluationTask(1,"d",task(),"c","e")
        with self.assertRaises(ValueError): EvaluationTask("","d",task(),"c","e")
        with self.assertRaises(TypeError): EvaluationTask("n","d",{}, "c","e")
        with self.assertRaises(TypeError): evaluation_task([])
        with self.assertRaises(ValueError): evaluation_task({"runtime":object()})
        with self.assertRaises(TypeError): EvaluationTask.from_dict([])

class EvaluationScenarioTest(unittest.TestCase):
    def test_scenario_round_trip_order_and_immutability(self):
        scenario=EvaluationScenario("direct_success","direct",evaluation_task({"labels":["m10"]}),"completed",{"repeat":3})
        self.assertEqual(EvaluationScenario.from_dict(scenario.to_dict()),scenario)
        self.assertEqual(SCENARIO_ORDER,tuple(sorted(SCENARIO_ORDER,key=SCENARIO_ORDER.index)))
        with self.assertRaises(FrozenInstanceError): scenario.name="other"
    def test_scenario_rejects_invalid_input(self):
        with self.assertRaises(TypeError): EvaluationScenario("n","d",{},"outcome")
        with self.assertRaises(ValueError): EvaluationScenario("n"," ","x","outcome")
        with self.assertRaises(TypeError): EvaluationScenario.from_dict([])

if __name__=="__main__": unittest.main()
