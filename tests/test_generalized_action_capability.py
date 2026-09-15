import unittest

from src.core.cognitive_session import CognitiveActionRequest, _project_policy
from src.core.policy import Policy
from src.core.tool import CapabilityDescriptor, ToolRegistry
from src.tools.calculator import CalculatorTool


class _Legacy:
    name = "legacy"
    def execute(self, parameters): raise AssertionError("not executed")


class _Synthetic:
    name = "synthetic"
    display_name = "Synthetic Tool"
    description = "Public synthetic contract"
    parameter_schema = {"required": ["payload"], "properties": {"payload": {}}, "additionalProperties": False}
    def execute(self, parameters): raise AssertionError("not executed")


class GeneralizedActionCapabilityTests(unittest.TestCase):
    def test_registry_descriptors_cover_legacy_and_public_schema(self):
        registry = ToolRegistry(); registry.register(_Legacy()); registry.register(_Synthetic()); registry.register(CalculatorTool())
        legacy, synthetic, calculator = registry.capability_descriptors()
        self.assertEqual((legacy.tool_id, legacy.parameter_schema), ("legacy", None))
        self.assertEqual(synthetic.to_dict()["parameter_schema"]["required"], ["payload"])
        self.assertEqual((calculator.tool_id, calculator.parameter_schema), ("calculator", None))
        with self.assertRaises(TypeError): synthetic.parameter_schema["x"] = 1

    def test_registry_projection_reuses_descriptor_public_schema_admission(self):
        class _Unsafe:
            name = "unsafe"
            parameter_schema = {"type": "object", "routing_hint": "private"}
            def execute(self, parameters): raise AssertionError("not executed")
        registry = ToolRegistry(); registry.register(_Unsafe())
        with self.assertRaises(ValueError): registry.capability_descriptors()

    def test_registry_owns_unknown_and_schema_admission(self):
        registry = ToolRegistry(); registry.register(_Synthetic())
        self.assertEqual(registry.validate_call("synthetic", {"payload": {"items": [None, True, 2]}}), {"payload": {"items": [None, True, 2]}})
        with self.assertRaises(LookupError): registry.validate_call("unknown", {})
        with self.assertRaises(ValueError): registry.validate_call("synthetic", {})
        with self.assertRaises(ValueError): registry.validate_call("synthetic", {"payload": 1, "extra": 2})

    def test_session_projection_is_registry_free_and_general_json_safe(self):
        policy = Policy("call_tool", {"tool_name": "unknown_later", "tool_parameters": {"nested": [None, False, {"n": 3.5}]}}, {})
        request = _project_policy(policy)
        self.assertEqual(request.to_dict(), {"action": "tool_call", "parameters": {"tool_name": "unknown_later", "parameters": {"nested": [None, False, {"n": 3.5}]}}})
        with self.assertRaises(TypeError): CognitiveActionRequest("tool_call", {"tool_name": "x", "parameters": {"bad": object()}})

    def test_descriptor_rejects_private_fields_and_round_trips(self):
        source_schema = {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "payload": {
                    "type": "object",
                    "properties": {"label": {"type": "string"}},
                    "required": ["label"],
                    "additionalProperties": False,
                },
            },
            "required": ["value"],
            "additionalProperties": False,
        }
        descriptor = CapabilityDescriptor("x", "X", "Public X", source_schema)
        self.assertEqual(CapabilityDescriptor.from_dict(descriptor.to_dict()), descriptor)
        source_schema["properties"]["value"]["type"] = "string"
        self.assertEqual(descriptor.parameter_schema["properties"]["value"]["type"], "number")
        with self.assertRaises(TypeError): descriptor.parameter_schema["properties"]["payload"]["properties"]["label"]["type"] = "number"

    def test_descriptor_structurally_rejects_private_and_unknown_schema_metadata(self):
        forbidden = (
            "difficulty", "expected_answer", "ground_truth", "correct_tool",
            "correct_action", "evaluator_success", "benchmark_label",
            "routing_hint", "arbitrary_unknown_field",
        )
        for key in forbidden:
            with self.subTest(key=key), self.assertRaises(ValueError):
                CapabilityDescriptor("x", parameter_schema={"type": "object", key: "private"})
            with self.subTest(nested_key=key), self.assertRaises(ValueError):
                CapabilityDescriptor(
                    "x",
                    parameter_schema={"properties": {"value": {key: "private"}}},
                )
        nested_leakage_shapes = (
            {"properties": {"value": {"items": {"difficulty": "private"}}}},
            {"properties": {"payload": {"type": "object", "properties": {"nested": {"difficulty": "private"}}}}},
        )
        for schema in nested_leakage_shapes:
            with self.subTest(nested_schema=schema), self.assertRaises(ValueError):
                CapabilityDescriptor("x", parameter_schema=schema)

    def test_descriptor_rejects_non_public_schema_shapes(self):
        invalid_schemas = (
            {"type": "array"},
            {"type": "string", "properties": {}},
            {"required": ["missing"]},
            {"properties": {"value": "not-a-schema"}},
            {"properties": {"value": {}}, "required": ["value", "value"]},
            {"properties": {"value": {}}, "additionalProperties": "false"},
        )
        for schema in invalid_schemas:
            with self.subTest(schema=schema), self.assertRaises((TypeError, ValueError)):
                CapabilityDescriptor("x", parameter_schema=schema)


if __name__ == "__main__": unittest.main()
