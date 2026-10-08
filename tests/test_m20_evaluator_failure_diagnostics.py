from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from src.evaluation.m20_evaluator_failure_diagnostics import (
    M20_EVALUATOR_FAILURE_DIAGNOSTIC_SCHEMA, M20EvaluatorDiagnosticStore,
    M20EvaluatorFailureDiagnostic, diagnose_after_evaluator_handoff,
)
from src.evaluation.m20_harness import M20IntegrityError, M20Outcome, M20Proposal, M20ProposalKind
from src.evaluation.m20_real_case_source import M20RealEnvironment, M20RealEvaluator, real_cases


class EvaluatorFailureDiagnosticsTest(unittest.TestCase):
    def setUp(self):
        self.case = next(x for x in real_cases() if x.public.cohort == "multi_step_stateful")
        self.env, self.evaluator = M20RealEnvironment(), M20RealEvaluator()
        self.initial = self.env.initial_public_state(self.case.public); self.ready = self.initial
        for _ in range(self.ready["required_progress"]):
            self.ready = self.env.apply(self.case.public, self.ready, M20Proposal(M20ProposalKind.ACT, "advance")).state

    def _diagnostic(self, execution, state, answer):
        outcome = self.evaluator.evaluate(self.case, state, answer)
        value = diagnose_after_evaluator_handoff(execution, self.case, state, answer, self.evaluator.evaluator_id, outcome)
        self.assertEqual(outcome is M20Outcome.SUCCESS, value.classification == "success")
        return value

    def test_h1_h2_h3_and_success_preserve_evaluator_outcome(self):
        target = self.case.private.target
        self.assertEqual(self._diagnostic("success", self.ready, target).classification, "success")
        self.assertEqual(self._diagnostic("h1", self.ready, "wrong").classification, "answer_payload_failure")
        self.assertEqual(self._diagnostic("h2", self.initial, target).classification, "prerequisite_failure")
        self.assertEqual(self._diagnostic("h3", self.initial, "wrong").classification, "combined_failure")

    def test_missing_malformed_conflicting_and_missing_witness_fail_closed(self):
        outcome = self.evaluator.evaluate(self.case, self.ready, "wrong")
        self.assertEqual(diagnose_after_evaluator_handoff("missing", self.case, self.ready, None, self.evaluator.evaluator_id, outcome).classification, "unknown_other")
        self.assertEqual(diagnose_after_evaluator_handoff("conflict", self.case, self.ready, "wrong", self.evaluator.evaluator_id, M20Outcome.SUCCESS).validation_status, "conflicting")
        missing_witness = SimpleNamespace(private=SimpleNamespace(reference_witness=(), target=self.case.private.target))
        self.assertEqual(diagnose_after_evaluator_handoff("witness", missing_witness, self.ready, "wrong", self.evaluator.evaluator_id, outcome).classification, "unknown_other")
        with self.assertRaises(M20IntegrityError):
            M20EvaluatorFailureDiagnostic("bad", self.evaluator.evaluator_id, "unsupported", True, "pass", "present", "success", "complete", {"authority": "x"})

    def test_private_sidecar_is_idempotent_and_rejects_conflicts_without_leakage(self):
        value = self._diagnostic("persisted", self.ready, "private-canary-answer")
        with TemporaryDirectory() as directory:
            store = M20EvaluatorDiagnosticStore(Path(directory)); store.persist(value); store.persist(value)
            self.assertEqual(store.load("persisted"), value)
            with self.assertRaises(M20IntegrityError): store.persist(replace(value, classification="combined_failure", prerequisite_status="fail"))
            serial = (Path(directory) / "persisted.json").read_text(encoding="utf-8")
        self.assertNotIn(self.case.private.target, serial); self.assertNotIn("private-canary-answer", serial)
        self.assertNotIn("target", value.canonical()); self.assertNotIn("witness", value.canonical())
