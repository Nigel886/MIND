"""Unit tests for the immutable M8 Task and Goal models."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from types import MappingProxyType
from uuid import UUID, uuid4

from src.core.task import Goal, Task


class GoalTest(unittest.TestCase):
    """Tests for Goal validation, immutability, and serialization."""

    def test_goal_creation_preserves_ordered_fields(self) -> None:
        """Creates a Goal with its description, criteria, and metadata."""

        goal = Goal("  calculate a product  ", ("correct", "formatted"), {"kind": "math"})

        self.assertEqual(goal.description, "  calculate a product  ")
        self.assertEqual(goal.success_criteria, ("correct", "formatted"))
        self.assertEqual(goal.to_dict()["metadata"], {"kind": "math"})
        self.assertIn("Goal(", repr(goal))

    def test_goal_rejects_invalid_required_values(self) -> None:
        """Rejects invalid description, criteria, and metadata values."""

        for description in ("", "   "):
            with self.assertRaises(ValueError):
                Goal(description, ("done",))
        with self.assertRaises(TypeError):
            Goal(1, ("done",))
        with self.assertRaises(TypeError):
            Goal("goal", "done")
        with self.assertRaises(ValueError):
            Goal("goal", ())
        with self.assertRaises(TypeError):
            Goal("goal", (1,))
        with self.assertRaises(ValueError):
            Goal("goal", ("  ",))
        with self.assertRaises(TypeError):
            Goal("goal", ("done",), [])
        with self.assertRaises(TypeError):
            Goal("goal", ("done",), {1: "value"})

    def test_goal_is_deeply_immutable_and_round_trips(self) -> None:
        """Protects nested metadata and reconstructs independent Goal values."""

        metadata = {"nested": {"values": [1, {"key": "value"}]}}
        goal = Goal("calculate", ("correct",), metadata)
        metadata["nested"]["values"].append(2)

        self.assertEqual(goal.to_dict()["metadata"], {"nested": {"values": [1, {"key": "value"}]}})
        self.assertIsInstance(goal.metadata, MappingProxyType)
        with self.assertRaises(TypeError):
            goal.metadata["new"] = "value"
        with self.assertRaises(FrozenInstanceError):
            goal.description = "other"

        serialized = goal.to_dict()
        restored = Goal.from_dict(serialized)
        serialized["metadata"]["nested"]["values"].append("later")
        self.assertEqual(restored, goal)
        self.assertNotIn("later", restored.to_dict()["metadata"]["nested"]["values"])

    def test_goal_deserialization_errors_are_predictable(self) -> None:
        """Raises direct validation errors for malformed serialized Goals."""

        with self.assertRaises(TypeError):
            Goal.from_dict([])
        with self.assertRaises(KeyError):
            Goal.from_dict({"description": "goal"})
        with self.assertRaises(TypeError):
            Goal.from_dict({"description": "goal", "success_criteria": ["done"], "metadata": []})


class TaskTest(unittest.TestCase):
    """Tests for Task validation, identity, immutability, and serialization."""

    def setUp(self) -> None:
        self.goal = Goal("calculate a product", ("correct answer",))

    def test_task_owns_goal_and_generates_unique_identity(self) -> None:
        """Creates Tasks with exact Goal ownership and independent UUIDs."""

        first = Task(self.goal, {"value": "ready"})
        second = Task(self.goal, {"value": "ready"})

        self.assertIs(first.goal, self.goal)
        self.assertIsInstance(first.id, UUID)
        self.assertNotEqual(first.id, second.id)
        self.assertIn("Task(", repr(first))

    def test_task_preserves_payload_id_and_timestamp_keys(self) -> None:
        """Treats user payload keys as data rather than Task identity fields."""

        task = Task(self.goal, {"id": "payload-id", "timestamp": "payload-time"})

        self.assertEqual(
            task.to_dict()["input"],
            {"id": "payload-id", "timestamp": "payload-time"},
        )

    def test_task_is_deeply_immutable_without_input_aliases(self) -> None:
        """Prevents mutation through original payloads or public nested values."""

        input_data = {"operation": "multiply", "operands": [17, {"value": 23}]}
        context = {"sources": ["user"]}
        constraints = {"allowed_tools": ["calculator"]}
        metadata = {"labels": ["example"]}
        task = Task(self.goal, input_data, context, constraints, metadata)
        input_data["operands"].append(99)
        context["sources"].append("later")
        constraints["allowed_tools"].append("other")
        metadata["labels"].append("later")

        data = task.to_dict()
        self.assertEqual(data["input"]["operands"], [17, {"value": 23}])
        self.assertEqual(data["context"], {"sources": ["user"]})
        self.assertEqual(data["constraints"], {"allowed_tools": ["calculator"]})
        self.assertEqual(data["metadata"], {"labels": ["example"]})
        with self.assertRaises(TypeError):
            task.input["new"] = "value"
        with self.assertRaises(FrozenInstanceError):
            task.goal = Goal("other", ("done",))

    def test_task_serialization_round_trip_preserves_explicit_uuid(self) -> None:
        """Serializes and reconstructs Task identity and all distinct mappings."""

        identifier = uuid4()
        task = Task(
            goal=Goal("calculate", ("correct",), {"goal": {"level": 1}}),
            input={"operation": "multiply", "operands": [17, 23]},
            context={"locale": "en"},
            constraints={"format": "integer"},
            metadata={"dataset": "M10"},
            id=identifier,
        )

        data = task.to_dict()
        restored = Task.from_dict(data)
        data["input"]["operands"].append(99)
        data["goal"]["metadata"]["goal"]["level"] = 2

        self.assertEqual(restored, task)
        self.assertEqual(restored.id, identifier)
        self.assertIsNot(restored.goal, task.goal)
        self.assertEqual(restored.to_dict()["input"]["operands"], [17, 23])
        self.assertEqual(restored.to_dict()["goal"]["metadata"], {"goal": {"level": 1}})

    def test_task_rejects_invalid_fields_and_serialized_input(self) -> None:
        """Uses TypeError for wrong types and ValueError for malformed UUIDs."""

        with self.assertRaises(TypeError):
            Task({}, {})
        with self.assertRaises(TypeError):
            Task(self.goal, [])
        with self.assertRaises(TypeError):
            Task(self.goal, {}, context=[])
        with self.assertRaises(TypeError):
            Task(self.goal, {}, constraints=[])
        with self.assertRaises(TypeError):
            Task(self.goal, {}, metadata=[])
        with self.assertRaises(TypeError):
            Task(self.goal, {}, id="not-a-uuid")
        with self.assertRaises(TypeError):
            Task(self.goal, {1: "not allowed"})
        with self.assertRaises(TypeError):
            Task.from_dict([])
        with self.assertRaises(ValueError):
            Task.from_dict({"id": "not-a-uuid"})
        with self.assertRaises(KeyError):
            Task.from_dict({"id": str(uuid4()), "input": {}})


if __name__ == "__main__":
    unittest.main()
