import unittest
from dataclasses import FrozenInstanceError
from src.core.tool import ToolResult, ToolRegistry, tool_result_to_observation

class FakeTool:
    name = "fake"
    def execute(self, parameters): return ToolResult("fake", True, 1, None, parameters)
class ToolTest(unittest.TestCase):
    def test_result_contract_and_round_trip(self):
        source = {"nested": [1]}; result = ToolResult("fake", True, {"x": [1]}, None, source)
        source["nested"].append(2); self.assertEqual(result.to_dict()["parameters"], {"nested": [1]})
        self.assertEqual(ToolResult.from_dict(result.to_dict()), result)
        with self.assertRaises(FrozenInstanceError): result.success = False
        with self.assertRaises(ValueError): ToolResult("fake", False, 1, "bad", {})
        with self.assertRaises(ValueError): ToolResult("fake", False, None, None, {})
    def test_registry_and_adapter(self):
        first, second = ToolRegistry(), ToolRegistry(); tool = FakeTool(); first.register(tool)
        self.assertIs(first.get("fake"), tool); self.assertTrue(first.contains("fake")); self.assertFalse(second.contains("fake"))
        self.assertEqual(first.list_names(), ("fake",))
        with self.assertRaises(ValueError): first.register(tool)
        with self.assertRaises(LookupError): first.get("none")
        obs = tool_result_to_observation(tool.execute({"id": "x"}))
        self.assertEqual(obs.source, "tool:fake"); self.assertEqual(obs.content["parameters"], {"id": "x"})
        with self.assertRaises(TypeError): tool_result_to_observation({})
