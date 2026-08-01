"""Tests for immutable M13 task-interpretation data models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from src.core.task_interpretation import (
    CapabilitySnapshot,
    TaskInterpretationProposal,
    ValidatedRequirement,
)


class TaskInterpretationProposalTests(unittest.TestCase):
    def test_creation_and_deterministic_equality(self) -> None:
        first = TaskInterpretationProposal(
            intent="calculate",
            required_capabilities=("calculator",),
            constraints={"limit": 1},
            evidence={"source": "mock"},
        )
        second = TaskInterpretationProposal.from_dict(first.to_dict())

        self.assertEqual(first, second)
        self.assertEqual(("calculator",), first.required_capabilities)
        self.assertEqual("mock", first.evidence["source"])

    def test_is_frozen_and_nested_values_are_detached(self) -> None:
        constraints = {"nested": {"items": [1, 2]}}
        evidence = {"details": {"provider": "fake"}}
        proposal = TaskInterpretationProposal("interpret", constraints=constraints, evidence=evidence)
        constraints["nested"]["items"].append(3)
        evidence["details"]["provider"] = "changed"

        with self.assertRaises(FrozenInstanceError):
            proposal.intent = "other"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            proposal.constraints["nested"] = {}  # type: ignore[index]
        self.assertEqual((1, 2), proposal.constraints["nested"]["items"])
        self.assertEqual("fake", proposal.evidence["details"]["provider"])

    def test_serialization_returns_independent_containers(self) -> None:
        proposal = TaskInterpretationProposal(
            "interpret",
            ("calculator",),
            {"nested": [1]},
            {"items": ["a"]},
        )
        serialized = proposal.to_dict()
        serialized["constraints"]["nested"].append(2)
        serialized["evidence"]["items"].append("b")

        self.assertEqual([1], proposal.to_dict()["constraints"]["nested"])
        self.assertEqual(["a"], proposal.to_dict()["evidence"]["items"])

    def test_rejects_invalid_intent_and_capabilities(self) -> None:
        with self.assertRaises(TypeError):
            TaskInterpretationProposal(1)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            TaskInterpretationProposal(" ")
        for capabilities in (("",), (" calculator",), ("calculator", "calculator")):
            with self.subTest(capabilities=capabilities):
                with self.assertRaises(ValueError):
                    TaskInterpretationProposal("interpret", capabilities)
        with self.assertRaises(TypeError):
            TaskInterpretationProposal("interpret", "calculator")


class ValidatedRequirementTests(unittest.TestCase):
    def test_creation_immutability_and_round_trip(self) -> None:
        requirement = ValidatedRequirement(
            ("calculator",),
            {"format": {"kind": "number"}},
            {"valid": True},
        )
        restored = ValidatedRequirement.from_dict(requirement.to_dict())

        self.assertEqual(requirement, restored)
        with self.assertRaises(FrozenInstanceError):
            requirement.required_capabilities = ()  # type: ignore[misc]
        with self.assertRaises(TypeError):
            requirement.validation_evidence["valid"] = False  # type: ignore[index]

    def test_rejects_invalid_data_and_duplicate_capabilities(self) -> None:
        with self.assertRaises(TypeError):
            ValidatedRequirement(constraints=[])  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            ValidatedRequirement(("calculator", "calculator"))
        with self.assertRaises(ValueError):
            ValidatedRequirement(("calculator ",))
        with self.assertRaises(ValueError):
            ValidatedRequirement(validation_evidence={"score": float("nan")})


class CapabilitySnapshotTests(unittest.TestCase):
    def test_creation_ordered_vocabulary_and_round_trip(self) -> None:
        snapshot = CapabilitySnapshot(
            (
                ("first", ("calculator", "math")),
                ("second", ("math", "search")),
            ),
        )

        self.assertEqual(("calculator", "math", "search"), snapshot.vocabulary)
        self.assertEqual(snapshot, CapabilitySnapshot.from_dict(snapshot.to_dict()))
        self.assertEqual(
            ["first", "second"],
            [item["name"] for item in snapshot.to_dict()["strategy_capabilities"]],
        )

    def test_is_frozen_and_does_not_retain_caller_lists(self) -> None:
        source = [("calculator", ["calculator"])]
        snapshot = CapabilitySnapshot(source)
        source[0][1].append("changed")

        with self.assertRaises(FrozenInstanceError):
            snapshot.vocabulary = ()  # type: ignore[misc]
        self.assertEqual(("calculator",), snapshot.strategy_capabilities[0][1])

    def test_rejects_invalid_strategy_capability_data(self) -> None:
        cases = (
            (("", ("calculator",)),),
            (("first", ("calculator",)), ("first", ("search",))),
            (("first", ("",)),),
            (("first", ("calculator", "calculator")),),
        )
        for strategies in cases:
            with self.subTest(strategies=strategies):
                with self.assertRaises(ValueError):
                    CapabilitySnapshot(strategies)
        with self.assertRaises(TypeError):
            CapabilitySnapshot("not-a-sequence")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            CapabilitySnapshot.from_dict(
                {
                    "strategy_capabilities": [{"name": "first", "capabilities": ["calculator"]}],
                    "vocabulary": ["search"],
                },
            )
