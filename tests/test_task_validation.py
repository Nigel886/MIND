"""Tests for M13 deterministic task-interpretation validation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from src.core.task_interpretation import CapabilitySnapshot, TaskInterpretationProposal, ValidatedRequirement
from src.core.task_validation import (
    ValidationFailure,
    ValidationFailureCategory,
    validate_proposal,
)


class ValidationProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = CapabilitySnapshot((("calculator_strategy", ("calculator", "math")),))

    def test_valid_proposal_produces_validated_requirement(self) -> None:
        proposal = TaskInterpretationProposal(
            "calculate",
            ("calculator", "math"),
            {"format": {"kind": "number"}},
            {"provider": "untrusted"},
        )

        result = validate_proposal(proposal, self.snapshot)

        self.assertIsInstance(result, ValidatedRequirement)
        self.assertEqual(("calculator", "math"), result.required_capabilities)
        self.assertEqual("valid", result.validation_evidence["outcome"])
        self.assertNotIn("provider", result.validation_evidence)

    def test_unknown_capability_returns_explicit_failure(self) -> None:
        result = validate_proposal(
            TaskInterpretationProposal("search", ("search",)),
            self.snapshot,
        )

        self.assertIsInstance(result, ValidationFailure)
        self.assertEqual(ValidationFailureCategory.UNSUPPORTED_CAPABILITY, result.category)
        self.assertEqual("search", result.evidence["capability"])

    def test_invalid_boundary_types_are_rejected(self) -> None:
        with self.assertRaises(TypeError):
            validate_proposal("proposal", self.snapshot)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            validate_proposal(TaskInterpretationProposal("calculate"), "snapshot")  # type: ignore[arg-type]

    def test_invalid_constraint_returns_explicit_failure(self) -> None:
        proposal = TaskInterpretationProposal("calculate", constraints={"valid": True})
        object.__setattr__(proposal, "constraints", {"invalid": object()})

        result = validate_proposal(proposal, self.snapshot)

        self.assertIsInstance(result, ValidationFailure)
        self.assertEqual(ValidationFailureCategory.INVALID_CONSTRAINT, result.category)

    def test_constraint_normalization_is_deterministic_and_preserves_input(self) -> None:
        source = {"nested": {"items": [1, 2]}}
        proposal = TaskInterpretationProposal("calculate", constraints=source)
        first = validate_proposal(proposal, self.snapshot)
        second = validate_proposal(proposal, self.snapshot)
        source["nested"]["items"].append(3)

        self.assertEqual(first, second)
        self.assertIsInstance(first, ValidatedRequirement)
        self.assertEqual((1, 2), first.constraints["nested"]["items"])
        self.assertEqual((1, 2), proposal.constraints["nested"]["items"])

    def test_validation_failure_is_immutable_and_serializable(self) -> None:
        failure = ValidationFailure(
            ValidationFailureCategory.INVALID_PROPOSAL,
            {"nested": {"reason": "schema"}},
        )

        restored = ValidationFailure.from_dict(failure.to_dict())

        self.assertEqual(failure, restored)
        with self.assertRaises(FrozenInstanceError):
            failure.category = ValidationFailureCategory.INVALID_CONSTRAINT  # type: ignore[misc]
        with self.assertRaises(TypeError):
            failure.evidence["nested"] = {}  # type: ignore[index]

    def test_validator_does_not_expose_interpretation_evidence(self) -> None:
        proposal = TaskInterpretationProposal(
            "calculate",
            evidence={"private_interpretation": "not-for-validator"},
        )
        result = validate_proposal(proposal, self.snapshot)

        self.assertIsInstance(result, ValidatedRequirement)
        self.assertNotIn("private_interpretation", result.validation_evidence)
