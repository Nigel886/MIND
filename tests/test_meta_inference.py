"""Unit tests for M9 Meta-Inference decision and evidence value models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from math import nan
from types import MappingProxyType
import unittest

from src.core.meta_inference import (
    DecisionEvidence,
    MetaInferenceDecision,
    MetaInferenceDecisionStatus,
)


class DecisionEvidenceTest(unittest.TestCase):
    """Tests for compact immutable selection-rationale evidence."""

    def test_valid_minimal_and_nested_evidence(self) -> None:
        """Creates evidence with an empty default and rich JSON-compatible data."""

        minimal = DecisionEvidence("availability", "strategy is registered")
        detailed = DecisionEvidence(
            "task_property",
            "incremental update required",
            {"task": {"properties": ["incremental", True]}},
        )

        self.assertEqual(minimal.to_dict()["data"], {})
        self.assertEqual(
            detailed.to_dict()["data"],
            {"task": {"properties": ["incremental", True]}},
        )
        self.assertIsInstance(detailed.data, MappingProxyType)

    def test_evidence_rejects_invalid_fields_and_executable_values(self) -> None:
        """Rejects malformed text, mapping fields, and non-data runtime values."""

        with self.assertRaises(TypeError):
            DecisionEvidence(1, "description")
        for evidence_type in ("", "   "):
            with self.assertRaises(ValueError):
                DecisionEvidence(evidence_type, "description")
        with self.assertRaises(TypeError):
            DecisionEvidence("type", 1)
        for description in ("", "   "):
            with self.assertRaises(ValueError):
                DecisionEvidence("type", description)
        with self.assertRaises(TypeError):
            DecisionEvidence("type", "description", [])
        with self.assertRaises(TypeError):
            DecisionEvidence("type", "description", {1: "value"})
        with self.assertRaises(ValueError):
            DecisionEvidence("type", "description", {"value": nan})
        with self.assertRaises(ValueError):
            DecisionEvidence("type", "description", {"callable": lambda: None})

    def test_evidence_is_deeply_immutable_and_serialization_is_isolated(self) -> None:
        """Protects nested caller data and fresh serialized output."""

        payload = {"nested": {"values": [1]}}
        evidence = DecisionEvidence("context", "context was inspected", payload)
        payload["nested"]["values"].append(2)
        with self.assertRaises(FrozenInstanceError):
            evidence.description = "other"
        with self.assertRaises(TypeError):
            evidence.data["nested"]["values"][0] = 0

        serialized = evidence.to_dict()
        restored = DecisionEvidence.from_dict(serialized)
        serialized["data"]["nested"]["values"].append(3)

        self.assertEqual(evidence.to_dict()["data"], {"nested": {"values": [1]}})
        self.assertEqual(restored, evidence)

    def test_evidence_deserialization_rejects_malformed_input(self) -> None:
        """Uses direct predictable errors for malformed serialized evidence."""

        with self.assertRaises(TypeError):
            DecisionEvidence.from_dict([])
        with self.assertRaises(KeyError):
            DecisionEvidence.from_dict({"evidence_type": "type"})
        with self.assertRaises(TypeError):
            DecisionEvidence.from_dict(
                {"evidence_type": "type", "description": "description", "data": []},
            )


class MetaInferenceDecisionTest(unittest.TestCase):
    """Tests for selection-only Meta-Inference decision results."""

    def setUp(self) -> None:
        self.evidence = DecisionEvidence("availability", "strategy is registered")

    def test_status_values_are_exact_and_invalid_values_are_rejected(self) -> None:
        """Exposes exactly the frozen selection outcome vocabulary."""

        self.assertEqual(
            {status.value for status in MetaInferenceDecisionStatus},
            {"selected", "unavailable", "rejected"},
        )
        with self.assertRaises(ValueError):
            MetaInferenceDecisionStatus("failed")

    def test_valid_selected_unavailable_and_rejected_decisions(self) -> None:
        """Creates each supported selection-only outcome."""

        selected = MetaInferenceDecision(
            MetaInferenceDecisionStatus.SELECTED,
            "append_evidence_v1",
            (self.evidence,),
        )
        unavailable = MetaInferenceDecision(
            MetaInferenceDecisionStatus.UNAVAILABLE,
            None,
            (self.evidence,),
        )
        rejected = MetaInferenceDecision(
            MetaInferenceDecisionStatus.REJECTED,
            None,
            (self.evidence,),
        )

        self.assertEqual(selected.selected_strategy, "append_evidence_v1")
        self.assertIsNone(unavailable.selected_strategy)
        self.assertIsNone(rejected.selected_strategy)

    def test_decision_rejects_invalid_status_strategy_and_evidence_combinations(self) -> None:
        """Enforces the exact status and selected-strategy invariants."""

        with self.assertRaises(TypeError):
            MetaInferenceDecision("selected", "append", (self.evidence,))
        with self.assertRaises(TypeError):
            MetaInferenceDecision(MetaInferenceDecisionStatus.SELECTED, None, (self.evidence,))
        for strategy in ("", "   "):
            with self.assertRaises(ValueError):
                MetaInferenceDecision(MetaInferenceDecisionStatus.SELECTED, strategy, (self.evidence,))
        with self.assertRaises(ValueError):
            MetaInferenceDecision(MetaInferenceDecisionStatus.UNAVAILABLE, "append", (self.evidence,))
        with self.assertRaises(ValueError):
            MetaInferenceDecision(MetaInferenceDecisionStatus.REJECTED, "append", (self.evidence,))
        with self.assertRaises(ValueError):
            MetaInferenceDecision(MetaInferenceDecisionStatus.SELECTED, "append", ())
        with self.assertRaises(TypeError):
            MetaInferenceDecision(MetaInferenceDecisionStatus.SELECTED, "append", ({},))

    def test_decision_is_immutable_and_serialization_round_trips(self) -> None:
        """Protects metadata/evidence and reconstructs equal independent values."""

        metadata = {"nested": {"labels": ["M9"]}}
        decision = MetaInferenceDecision(
            MetaInferenceDecisionStatus.SELECTED,
            "append_evidence_v1",
            [DecisionEvidence("task_property", "incremental", {"values": [1]})],
            metadata,
        )
        metadata["nested"]["labels"].append("later")
        with self.assertRaises(FrozenInstanceError):
            decision.selected_strategy = "other"
        with self.assertRaises(TypeError):
            decision.metadata["nested"]["labels"][0] = "other"
        with self.assertRaises(TypeError):
            decision.evidence[0].data["values"][0] = 0

        serialized = decision.to_dict()
        restored = MetaInferenceDecision.from_dict(serialized)
        serialized["metadata"]["nested"]["labels"].append("changed")
        serialized["evidence"][0]["data"]["values"].append(2)

        self.assertEqual(restored, decision)
        self.assertEqual(decision.to_dict()["metadata"], {"nested": {"labels": ["M9"]}})
        self.assertEqual(decision.to_dict()["evidence"][0]["data"], {"values": [1]})

    def test_decision_deserialization_rejects_malformed_data_and_ignores_unknown_fields(self) -> None:
        """Rejects malformed decision data and permits forward-compatible extras."""

        with self.assertRaises(TypeError):
            MetaInferenceDecision.from_dict([])
        with self.assertRaises(ValueError):
            MetaInferenceDecision.from_dict(
                {"status": "failed", "selected_strategy": None, "evidence": []},
            )
        with self.assertRaises(KeyError):
            MetaInferenceDecision.from_dict(
                {"status": "selected", "selected_strategy": "append"},
            )
        restored = MetaInferenceDecision.from_dict(
            {
                "status": "selected",
                "selected_strategy": "append",
                "evidence": [
                    {"evidence_type": "availability", "description": "registered"},
                ],
                "unknown": "ignored",
            },
        )
        self.assertEqual(restored.metadata, {})

    def test_decision_has_no_engine_selection_or_registry_behavior(self) -> None:
        """Keeps decisions as data rather than a Meta-Inference runtime."""

        decision = MetaInferenceDecision(
            MetaInferenceDecisionStatus.SELECTED,
            "append_evidence_v1",
            (self.evidence,),
        )
        for method in ("execute", "select", "score", "register", "lookup"):
            self.assertFalse(hasattr(decision, method))


if __name__ == "__main__":
    unittest.main()
