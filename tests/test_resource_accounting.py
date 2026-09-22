"""Focused tests for pure immutable M19 resource accounting."""

from dataclasses import FrozenInstanceError
from math import inf, nan
import unittest

from src.core.resource_accounting import ResourceAllocation, ResourceDimension, ResourceState


def resource_state() -> ResourceState:
    return ResourceState(
        tuple(ResourceAllocation(dimension, 3) for dimension in ResourceDimension),
        "allocation:m19:1", "m19_resource_v1", "transition:resource:0",
        {"cost_unit": "abstract", "weights": [1]},
    )


class ResourceAccountingTest(unittest.TestCase):
    def test_valid_state_is_immutable_and_has_no_policy_or_execution_api(self) -> None:
        state = resource_state()
        self.assertEqual(state.allocation(ResourceDimension.REASONING_STEP).remaining, 3)
        with self.assertRaises(FrozenInstanceError):
            state.version = "other"
        for name in ("should_stop", "can_answer", "should_observe", "utility", "choose_decision", "execute"):
            self.assertFalse(hasattr(state, name))

    def test_each_dimension_consumes_purely_and_original_is_unchanged(self) -> None:
        for dimension in ResourceDimension:
            original = resource_state()
            updated = original.consume(dimension, 1, f"transition:{dimension.value}:1")
            self.assertEqual(original.allocation(dimension).consumed, 0)
            self.assertEqual(updated.allocation(dimension).consumed, 1)
            self.assertEqual(updated.allocation(dimension).remaining, 2)

    def test_multi_unit_exact_exhaustion_and_over_consumption_fail_closed(self) -> None:
        state = resource_state().consume(ResourceDimension.TOOL_ATTEMPT, 3, "transition:tool:1")
        tool = state.allocation(ResourceDimension.TOOL_ATTEMPT)
        self.assertTrue(tool.exhausted)
        self.assertEqual(tool.remaining, 0)
        with self.assertRaises(ValueError):
            state.consume(ResourceDimension.TOOL_ATTEMPT, 1, "transition:tool:2")
        with self.assertRaises(ValueError):
            resource_state().consume(ResourceDimension.TOOL_ATTEMPT, 4, "transition:tool:3")

    def test_negative_zero_and_malformed_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ResourceAllocation(ResourceDimension.REASONING_STEP, -1)
        with self.assertRaises(ValueError):
            ResourceAllocation(ResourceDimension.REASONING_STEP, 1, -1)
        with self.assertRaises(ValueError):
            resource_state().consume(ResourceDimension.REASONING_STEP, 0, "transition:1")
        with self.assertRaises(ValueError):
            resource_state().consume(ResourceDimension.REASONING_STEP, -1, "transition:1")
        with self.assertRaises(TypeError):
            ResourceAllocation(ResourceDimension.REASONING_STEP, nan)
        with self.assertRaises(TypeError):
            ResourceAllocation(ResourceDimension.REASONING_STEP, inf)

    def test_serialization_round_trips_and_rejects_inconsistent_derived_values(self) -> None:
        original = resource_state().consume(ResourceDimension.PROVIDER_INTERACTION, 2, "transition:provider:1")
        serialized = original.to_dict()
        self.assertEqual(serialized, original.to_dict())
        self.assertEqual(ResourceState.from_dict(serialized), original)
        serialized["allocations"][0]["remaining"] = 99
        with self.assertRaises(ValueError):
            ResourceState.from_dict(serialized)

    def test_consumption_never_resurrects_resource_or_changes_allocation_identity(self) -> None:
        original = resource_state().consume(ResourceDimension.REASONING_STEP, 1, "transition:1")
        updated = original.consume(ResourceDimension.REASONING_STEP, 1, "transition:2")
        self.assertEqual(updated.allocation_identity, original.allocation_identity)
        self.assertEqual(updated.allocation(ResourceDimension.REASONING_STEP).capacity, 3)
        self.assertGreater(updated.allocation(ResourceDimension.REASONING_STEP).consumed, original.allocation(ResourceDimension.REASONING_STEP).consumed)
        self.assertLess(updated.allocation(ResourceDimension.REASONING_STEP).remaining, original.allocation(ResourceDimension.REASONING_STEP).remaining)


if __name__ == "__main__":
    unittest.main()
