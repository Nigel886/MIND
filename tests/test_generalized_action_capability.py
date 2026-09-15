import unittest

from src.core.cognitive_session import CognitiveActionRequest, _project_policy
from src.core.policy import Policy
from src.core.tool import CapabilityDescriptor, ToolRegistry


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
        registry = ToolRegistry(); registry.register(_Legacy()); registry.register(_Synthetic())
        legacy, synthetic = registry.capability_descriptors()
        self.assertEqual((legacy.tool_id, legacy.parameter_schema), ("legacy", None))
        self.assertEqual(synthetic.to_dict()["parameter_schema"]["required"], ["payload"])
        with self.assertRaises(TypeError): synthetic.parameter_schema["x"] = 1

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
        descriptor = CapabilityDescriptor("x", parameter_schema={"properties": {"value": {}}})
        self.assertEqual(CapabilityDescriptor.from_dict(descriptor.to_dict()), descriptor)
        with self.assertRaises(ValueError): CapabilityDescriptor("x", parameter_schema={"expected_answer": "private"})


if __name__ == "__main__": unittest.main()
