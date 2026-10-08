"""Offline-only feasibility evidence for a future evaluator-side diagnostic."""
from __future__ import annotations

from dataclasses import dataclass
import unittest

from src.evaluation.m20_harness import M20Outcome, M20Proposal, M20ProposalKind
from src.evaluation.m20_real_case_source import M20RealEnvironment, M20RealEvaluator, real_cases


@dataclass(frozen=True)
class ProposedDiagnostic:
    """Test-only private evaluator metadata; never a provider-facing object."""
    schema: str
    answer_matches_private_target: bool | None
    prerequisite_status: str | None
    witness_status: str | None
    classification: str


def classify(*, answer_match: bool | None, prerequisite_ok: bool | None,
             witness_ok: bool | None) -> ProposedDiagnostic:
    if witness_ok is not True or answer_match is None or prerequisite_ok is None:
        return ProposedDiagnostic("m20_evaluator_failure_diagnostic_v1", answer_match,
                                  None if prerequisite_ok is None else ("pass" if prerequisite_ok else "fail"),
                                  None if witness_ok is None else ("present" if witness_ok else "missing"), "unknown_other")
    if answer_match and prerequisite_ok: label = "success"
    elif not answer_match and prerequisite_ok: label = "answer_payload_failure"
    elif answer_match and not prerequisite_ok: label = "prerequisite_failure"
    else: label = "combined_failure"
    return ProposedDiagnostic("m20_evaluator_failure_diagnostic_v1", answer_match,
                              "pass" if prerequisite_ok else "fail", "present", label)


class EvaluatorIdentifiabilityFeasibilityTest(unittest.TestCase):
    def setUp(self):
        self.case = next(x for x in real_cases() if x.public.cohort == "multi_step_stateful")
        self.environment, self.evaluator = M20RealEnvironment(), M20RealEvaluator()
        self.initial = self.environment.initial_public_state(self.case.public)
        self.good = self.initial
        for _ in range(self.good["required_progress"]):
            self.good = self.environment.apply(self.case.public, self.good,
                                               M20Proposal(M20ProposalKind.ACT, "advance")).state

    def test_actual_evaluator_collapses_failure_subtypes(self):
        target = self.case.private.target
        self.assertIs(self.evaluator.evaluate(self.case, self.good, target), M20Outcome.SUCCESS)
        self.assertIs(self.evaluator.evaluate(self.case, self.good, "wrong"), M20Outcome.FAILURE_OR_INCORRECT)
        self.assertIs(self.evaluator.evaluate(self.case, self.initial, target), M20Outcome.FAILURE_OR_INCORRECT)
        self.assertIs(self.evaluator.evaluate(self.case, self.initial, "wrong"), M20Outcome.FAILURE_OR_INCORRECT)

    def test_proposed_private_metadata_separates_hypotheses(self):
        self.assertEqual(classify(answer_match=True, prerequisite_ok=True, witness_ok=True).classification, "success")
        self.assertEqual(classify(answer_match=False, prerequisite_ok=True, witness_ok=True).classification, "answer_payload_failure")
        self.assertEqual(classify(answer_match=True, prerequisite_ok=False, witness_ok=True).classification, "prerequisite_failure")
        self.assertEqual(classify(answer_match=False, prerequisite_ok=False, witness_ok=True).classification, "combined_failure")

    def test_absent_malformed_conflicting_or_private_leakage_data_fail_closed(self):
        self.assertEqual(classify(answer_match=None, prerequisite_ok=True, witness_ok=True).classification, "unknown_other")
        self.assertEqual(classify(answer_match=True, prerequisite_ok=None, witness_ok=True).classification, "unknown_other")
        self.assertEqual(classify(answer_match=False, prerequisite_ok=False, witness_ok=False).classification, "unknown_other")
        result = classify(answer_match=False, prerequisite_ok=True, witness_ok=True)
        self.assertNotIn(self.case.private.target, repr(result))
        self.assertNotIn("wrong", repr(result))
