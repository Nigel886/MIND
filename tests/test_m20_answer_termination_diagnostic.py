"""Independent non-network authorization checks for the tiny termination diagnostic."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m20_answer_termination_diagnostic import (
    M20_ANSWER_TERMINATION_CASE_A, M20_ANSWER_TERMINATION_CASE_B,
    M20AnswerTerminationDiagnosticRunner, answer_termination_authorization_payload,
    build_answer_termination_protocol, validate_answer_termination_protocol,
    verify_answer_termination_authorization,
)
from src.evaluation.m20_harness import M20Condition, M20Proposal, M20ProposalKind, m20_answer_ready
from src.evaluation.m20_real_case_source import M20RealEnvironment, real_case_definitions


def response(value):
    return {"model": "deepseek-flash", "choices": [{"message": {"content": json.dumps(value)}}]}


class M20AnswerTerminationDiagnosticTest(unittest.TestCase):
    def test_freeze_selects_exact_public_cases_and_readiness_transitions(self):
        protocol = build_answer_termination_protocol()
        validate_answer_termination_protocol(protocol)
        self.assertEqual([item["case_id"] for item in protocol["cases"]],
                         [M20_ANSWER_TERMINATION_CASE_A, M20_ANSWER_TERMINATION_CASE_B])
        self.assertEqual(len(protocol["work_ids"]), 4)
        values = {item.case_id: item for item in real_case_definitions()}
        environment = M20RealEnvironment()
        a, b = values[M20_ANSWER_TERMINATION_CASE_A].to_case(), values[M20_ANSWER_TERMINATION_CASE_B].to_case()
        self.assertTrue(m20_answer_ready(environment.initial_public_state(a.public), a.public))
        state = environment.initial_public_state(b.public)
        self.assertFalse(m20_answer_ready(state, b.public))
        for step in b.private.reference_witness[:2]:
            state = environment.apply(b.public, state, M20Proposal(M20ProposalKind.ACT, step["action_id"])).state
        self.assertTrue(m20_answer_ready(state, b.public))

    def test_authorization_and_fake_boundary_are_exact(self):
        runner, protocol = M20AnswerTerminationDiagnosticRunner(), build_answer_termination_protocol()
        authorization, calls = answer_termination_authorization_payload(protocol), []
        artifact = Path("docs/evaluation/M20-AnswerTermination-Diagnostic-LiveAuthorization.json")
        self.assertEqual(json.loads(artifact.read_text(encoding="utf-8")), authorization)
        item = runner.work_items()[0]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(PermissionError):
                runner.run_fake(None, item, lambda *_: calls.append(1), root / "missing")
            record = runner.run_fake(authorization, item, lambda request, _: calls.append(request) or response({"kind": "stop"}), root / "records")
            self.assertEqual((len(calls), record.telemetry.stop_proposed, record.telemetry.tool_attempts), (1, True, 0))
        mutations = (
            lambda value: value.__setitem__("protocol", "m20_real_provider_diagnostic_v5"),
            lambda value: value.__setitem__("case_ids", value["case_ids"][:1]),
            lambda value: value.__setitem__("work_ids", value["work_ids"] + ["extra"]),
            lambda value: value.__setitem__("answer_readiness_policy", "stale"),
            lambda value: value.__setitem__("runtime_identity", "stale"),
            lambda value: value.__setitem__("provider_hash", "0" * 64),
            lambda value: value.__setitem__("resource_ceiling_version", "m20_real_ceiling_v1"),
            lambda value: value.__setitem__("resource_ceiling_digest", "0" * 64),
        )
        for mutate in mutations:
            invalid = deepcopy(authorization); mutate(invalid)
            with self.assertRaises(PermissionError): verify_answer_termination_authorization(invalid, protocol)

    def test_case_b_projection_changes_only_at_public_readiness_with_no_canary_leakage(self):
        runner, item = M20AnswerTerminationDiagnosticRunner(), next(
            item for item in M20AnswerTerminationDiagnosticRunner().work_items()
            if item.spec.case_id == M20_ANSWER_TERMINATION_CASE_B and item.spec.condition is M20Condition.MIND_FIXED)
        requests = []
        replies = iter(({"kind": "act", "action_id": "advance"}, {"kind": "act", "action_id": "advance"}, {"kind": "stop"}))
        with TemporaryDirectory() as directory:
            record = runner.run_fake(answer_termination_authorization_payload(), item,
                lambda request, _: requests.append(request) or response(next(replies)), Path(directory) / "records")
        self.assertEqual((record.telemetry.stop_proposed, record.telemetry.tool_attempts), (True, 2))
        public = [json.loads(request["messages"][1]["content"].split("Public input: ", 1)[1]) for request in requests]
        self.assertEqual(public[0]["legal_decision_kinds"], ["act", "answer"])
        self.assertEqual(public[-1]["legal_decision_kinds"], ["answer", "stop"])
        wire = json.dumps(requests, sort_keys=True)
        for forbidden in ("reference_witness", "target", "required_progress", "requires_observation", "requires_recovery", "hidden_reasoning"):
            self.assertNotIn(forbidden, wire)


if __name__ == "__main__":
    unittest.main()
