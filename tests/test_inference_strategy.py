"""Unit tests for immutable M9 InferenceStrategy descriptors."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from math import nan
from types import MappingProxyType
import unittest

from src.core.inference_strategy import InferenceStrategy


class InferenceStrategyTest(unittest.TestCase):
    """Tests for strategy validation, immutability, and serialization."""

    def test_valid_minimal_strategy_uses_immutable_defaults(self) -> None:
        """Creates a descriptor with required values and empty mappings."""

        strategy = InferenceStrategy("append_evidence_v1", "Append evidence", ("append",))

        self.assertEqual(strategy.name, "append_evidence_v1")
        self.assertEqual(strategy.capabilities, ("append",))
        self.assertEqual(strategy.to_dict()["configuration"], {})
        self.assertEqual(strategy.to_dict()["metadata"], {})
        self.assertIsInstance(strategy.configuration, MappingProxyType)

    def test_valid_full_strategy_preserves_nested_data(self) -> None:
        """Stores rich configuration and metadata without changing their values."""

        strategy = InferenceStrategy(
            "replace_evidence_v1",
            "Replace matching evidence",
            ["replace", "evidence"],
            {"mode": "replace", "limits": {"records": [1, 2]}},
            {"source": {"phase": "M9"}, "enabled": True},
        )

        self.assertEqual(strategy.capabilities, ("replace", "evidence"))
        self.assertEqual(
            strategy.to_dict()["configuration"],
            {"mode": "replace", "limits": {"records": [1, 2]}},
        )
        self.assertEqual(
            strategy.to_dict()["metadata"],
            {"source": {"phase": "M9"}, "enabled": True},
        )

    def test_rejects_invalid_name_and_description(self) -> None:
        """Uses predictable type and value errors for required text fields."""

        with self.assertRaises(TypeError):
            InferenceStrategy(1, "description", ("append",))
        for name in ("", "   ", " append"):
            with self.assertRaises(ValueError):
                InferenceStrategy(name, "description", ("append",))
        with self.assertRaises(TypeError):
            InferenceStrategy("append", 1, ("append",))
        for description in ("", "   "):
            with self.assertRaises(ValueError):
                InferenceStrategy("append", description, ("append",))

    def test_rejects_invalid_capabilities(self) -> None:
        """Rejects non-sequences, invalid items, empties, and duplicates."""

        invalid_capabilities = (
            None,
            "append",
            (),
            (1,),
            ("",),
            (" append",),
            ("append", "append"),
        )
        for capabilities in invalid_capabilities:
            with self.assertRaises((TypeError, ValueError)):
                InferenceStrategy("append", "description", capabilities)

    def test_rejects_invalid_mapping_fields(self) -> None:
        """Rejects invalid mappings, keys, nonfinite values, and executable data."""

        with self.assertRaises(TypeError):
            InferenceStrategy("append", "description", ("append",), [])
        with self.assertRaises(TypeError):
            InferenceStrategy("append", "description", ("append",), {1: "value"})
        with self.assertRaises(TypeError):
            InferenceStrategy("append", "description", ("append",), {}, [])
        with self.assertRaises(ValueError):
            InferenceStrategy("append", "description", ("append",), {"value": nan})
        with self.assertRaises(ValueError):
            InferenceStrategy("append", "description", ("append",), {"callable": lambda: None})

    def test_attribute_and_nested_mapping_mutation_are_blocked(self) -> None:
        """Rejects direct mutation through the frozen descriptor or its mappings."""

        strategy = InferenceStrategy(
            "append",
            "description",
            ("append",),
            {"nested": {"values": [1]}},
            {"nested": {"labels": ["M9"]}},
        )

        with self.assertRaises(FrozenInstanceError):
            strategy.name = "other"
        with self.assertRaises(TypeError):
            strategy.configuration["new"] = "value"
        with self.assertRaises(TypeError):
            strategy.configuration["nested"]["new"] = "value"
        with self.assertRaises(TypeError):
            strategy.metadata["nested"]["labels"][0] = "other"

    def test_caller_mutation_cannot_change_strategy(self) -> None:
        """Removes aliases to caller-owned nested configuration and metadata."""

        configuration = {"nested": {"items": [1]}}
        metadata = {"nested": {"items": ["M9"]}}
        strategy = InferenceStrategy(
            "append",
            "description",
            ("append",),
            configuration,
            metadata,
        )
        configuration["nested"]["items"].append(2)
        metadata["nested"]["items"].append("later")

        self.assertEqual(strategy.to_dict()["configuration"], {"nested": {"items": [1]}})
        self.assertEqual(strategy.to_dict()["metadata"], {"nested": {"items": ["M9"]}})

    def test_serialization_round_trip_and_output_isolation(self) -> None:
        """Round-trips equivalent values and returns independent output containers."""

        strategy = InferenceStrategy(
            "append",
            "description",
            ("append",),
            {"nested": {"items": [1]}},
            {"nested": {"items": ["M9"]}},
        )

        serialized = strategy.to_dict()
        restored = InferenceStrategy.from_dict(serialized)
        serialized["configuration"]["nested"]["items"].append(2)
        serialized["metadata"]["nested"]["items"].append("later")

        self.assertEqual(restored, strategy)
        self.assertEqual(strategy.to_dict()["configuration"], {"nested": {"items": [1]}})
        self.assertEqual(strategy.to_dict()["metadata"], {"nested": {"items": ["M9"]}})

    def test_from_dict_rejects_malformed_input_and_ignores_unknown_fields(self) -> None:
        """Preserves strict required-field behavior and forward-compatible extras."""

        with self.assertRaises(TypeError):
            InferenceStrategy.from_dict([])
        with self.assertRaises(KeyError):
            InferenceStrategy.from_dict({"name": "append"})
        with self.assertRaises(TypeError):
            InferenceStrategy.from_dict(
                {
                    "name": "append",
                    "description": "description",
                    "capabilities": ["append"],
                    "metadata": [],
                },
            )

        restored = InferenceStrategy.from_dict(
            {
                "name": "append",
                "description": "description",
                "capabilities": ["append"],
                "unknown": "ignored",
            },
        )
        self.assertEqual(restored.to_dict()["metadata"], {})

    def test_model_exposes_no_execution_or_selection_behavior(self) -> None:
        """Keeps the descriptor as data rather than a strategy runtime component."""

        strategy = InferenceStrategy("append", "description", ("append",))

        for method in ("execute", "select", "score", "register"):
            self.assertFalse(hasattr(strategy, method))


if __name__ == "__main__":
    unittest.main()
