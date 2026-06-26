"""Unit tests for the belief module."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import timezone

from src.core.belief import Belief, BeliefRecord


class BeliefRecordTest(unittest.TestCase):
    """Tests for BeliefRecord."""

    def test_belief_record_creation(self) -> None:
        """Creates a belief record with expected values."""

        record = BeliefRecord(
            identifier="NeedLiteratureSearch",
            probability=0.82,
            confidence=0.91,
            evidence={"source": "user"},
        )

        self.assertEqual(record.identifier, "NeedLiteratureSearch")
        self.assertEqual(record.probability, 0.82)
        self.assertEqual(record.confidence, 0.91)
        self.assertEqual(record.evidence, {"source": "user"})
        self.assertEqual(record.timestamp.tzinfo, timezone.utc)

    def test_belief_record_is_immutable(self) -> None:
        """Prevents mutation of a belief record after creation."""

        record = BeliefRecord(
            identifier="TaskComplexity",
            probability=0.5,
            confidence=0.6,
        )

        with self.assertRaises(FrozenInstanceError):
            record.probability = 0.7

    def test_belief_record_serialization_round_trip(self) -> None:
        """Serializes and deserializes a belief record losslessly."""

        record = BeliefRecord(
            identifier="NeedPlanning",
            probability=0.77,
            confidence=0.84,
            evidence={
                "observations": [
                    {"source": "user", "content": "plan this task"},
                ],
            },
        )

        restored = BeliefRecord.from_dict(record.to_dict())

        self.assertEqual(restored, record)
        self.assertEqual(restored.timestamp.tzinfo, timezone.utc)


class BeliefTest(unittest.TestCase):
    """Tests for the immutable Belief container."""

    def test_belief_creation(self) -> None:
        """Creates a belief state with nested belief records."""

        record = BeliefRecord(
            identifier="NeedRetrieval",
            probability=0.88,
            confidence=0.79,
        )
        belief = Belief(
            state={"NeedRetrieval": record},
            confidence={"NeedRetrieval": 0.79},
            version=3,
        )

        self.assertEqual(belief.state["NeedRetrieval"], record)
        self.assertEqual(belief.confidence["NeedRetrieval"], 0.79)
        self.assertEqual(belief.version, 3)

    def test_belief_is_immutable(self) -> None:
        """Prevents mutation of the belief container after creation."""

        belief = Belief()

        with self.assertRaises(FrozenInstanceError):
            belief.version = 1

    def test_belief_has_minimal_public_api(self) -> None:
        """Exposes only data and serialization interfaces."""

        self.assertFalse(hasattr(Belief, "evolve"))
        self.assertFalse(hasattr(Belief, "update"))
        self.assertFalse(hasattr(Belief, "clone"))
        self.assertTrue(hasattr(Belief, "to_dict"))
        self.assertTrue(hasattr(Belief, "from_dict"))

    def test_belief_serialization_round_trip(self) -> None:
        """Serializes and deserializes nested belief records recursively."""

        search_record = BeliefRecord(
            identifier="NeedSearch",
            probability=0.81,
            confidence=0.93,
            evidence={
                "reasons": ["missing context", "external knowledge needed"],
            },
        )
        plan_record = BeliefRecord(
            identifier="NeedPlanning",
            probability=0.64,
            confidence=0.75,
            evidence=["multi-step task"],
        )
        belief = Belief(
            state={
                "NeedSearch": search_record,
                "NeedPlanning": plan_record,
            },
            confidence={
                "NeedSearch": 0.93,
                "NeedPlanning": 0.75,
            },
            version=5,
        )

        data = belief.to_dict()
        restored = Belief.from_dict(data)

        self.assertEqual(data["state"]["NeedSearch"]["identifier"], "NeedSearch")
        self.assertEqual(data["state"]["NeedPlanning"]["identifier"], "NeedPlanning")
        self.assertEqual(restored, belief)
        self.assertEqual(restored.version, 5)
        self.assertEqual(restored.confidence, belief.confidence)

    def test_belief_deserialization_preserves_records(self) -> None:
        """Restores belief records as BeliefRecord instances."""

        data = {
            "state": {
                "NeedCoding": {
                    "identifier": "NeedCoding",
                    "probability": 0.95,
                    "confidence": 0.9,
                    "evidence": {"source": "runtime"},
                    "timestamp": "2026-06-26T12:00:00+00:00",
                },
            },
            "confidence": {
                "NeedCoding": 0.9,
            },
            "version": 7,
        }

        belief = Belief.from_dict(data)

        self.assertIsInstance(belief.state["NeedCoding"], BeliefRecord)
        self.assertEqual(belief.state["NeedCoding"].timestamp.tzinfo, timezone.utc)
        self.assertEqual(belief.version, 7)
