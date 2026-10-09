from __future__ import annotations
import json
import re
import base64
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from src.evaluation.m20_prospective_feasibility import (M20ProspectiveFeasibilityRunner, build_feasibility_manifest, feasibility_authorization_payload, feasibility_live_authorization_payload, verify_feasibility_authorization, descriptive_projection)
from src.evaluation.m20_evaluator_failure_diagnostics import diagnose_after_evaluator_handoff
from src.evaluation.m20_real_case_source import M20RealEnvironment, real_cases
from src.evaluation.m20_harness import M20Outcome, M20Proposal, M20ProposalKind
from src.evaluation.m20_prospective_feasibility import (M20_FEASIBILITY_TRUST_ANCHOR_SCHEMA,
    M20FeasibilityLiveBudget, M20FeasibilityExecutionBlocked, M20_FEASIBILITY_OWNER_AUTHORITY)
from src.evaluation.m20_financial_control import (M20FeasibilityFinancialLedger, M20FeasibilityFinancialPolicy,
    M20FinancialControlBlocked)
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

def policy(limit=10_000): return M20FeasibilityFinancialPolicy("test_exact_deepseek_tokenizer_v1", limit)
def exact_test_counter(_request): return 10

def signed_authority(directory, financial_policy=None):
    private = Ed25519PrivateKey.generate(); payload = feasibility_live_authorization_payload(financial_policy=financial_policy or policy())
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(); issuer = "ephemeral-test-issuer"
    artifact, anchor = Path(directory) / "authorization.json", Path(directory) / "trust.json"
    artifact.write_text(json.dumps({"payload":payload,"issuer":issuer,"algorithm":"Ed25519","signature":base64.b64encode(private.sign(encoded)).decode()}), encoding="utf-8")
    anchor.write_text(json.dumps({"schema":M20_FEASIBILITY_TRUST_ANCHOR_SCHEMA,"issuers":{issuer:{"algorithm":"Ed25519","public_key_b64":base64.b64encode(private.public_key().public_bytes_raw()).decode()}}}), encoding="utf-8")
    return artifact, anchor

def reply(value): return {"model": "deepseek-flash", "choices": [{"message": {"content": json.dumps(value)}}]}
def responder(request, _timeout):
    public = json.loads(request["messages"][1]["content"].split("Public input: ", 1)[1])
    match = re.fullmatch(r"Complete the public ([a-z_]+) task (\d+)\.", public["task"])
    if public["legal_decision_kinds"] == ["answer", "stop"]:
        return reply({"kind": "answer", "payload": "answer:m20.real." + match.group(1) + "." + int(match.group(2)).__format__("02d")})
    if public["state"].get("requires_observation") and not public["state"].get("observed"):
        return reply({"kind": "act", "action_id": "observe"})
    if public["state"].get("requires_recovery") and not public["state"].get("recovered"):
        return reply({"kind": "act", "action_id": "recover"})
    return reply({"kind": "act", "action_id": "advance"})

class ProspectiveFeasibilityTests(unittest.TestCase):
    def test_manifest_fixed_only_and_deterministic(self):
        manifest = build_feasibility_manifest(); self.assertEqual((len(manifest["case_membership"]), len(manifest["work_items"])), (12, 24))
        self.assertEqual({item["condition"] for item in manifest["work_items"]}, {"m20_mind_fixed_v1"}); self.assertEqual(manifest, build_feasibility_manifest())
    def test_authorization_is_exact_and_live_default_denies(self):
        runner = M20ProspectiveFeasibilityRunner(); value = feasibility_authorization_payload(); bad = deepcopy(value); bad["namespace"] = "historical"
        with self.assertRaises(PermissionError): verify_feasibility_authorization(bad)
        with self.assertRaises(PermissionError): runner.run_live(Path("missing.json"), Path("missing-trust.json"), lambda *_: self.fail("transport"), Path("records"))
    def test_live_authorization_admits_only_exact_temporary_artifact_before_fake_transport(self):
        runner = M20ProspectiveFeasibilityRunner()
        with TemporaryDirectory() as directory:
            root, artifact = Path(directory) / "records", Path(directory) / "authorization.json"
            artifact, anchor = signed_authority(directory)
            artifact.write_text(json.dumps(feasibility_authorization_payload()), encoding="utf-8")
            with self.assertRaises(PermissionError): runner.run_live(artifact, anchor, lambda *_: self.fail("synthetic reached transport"), root)
            artifact, anchor = signed_authority(directory)
            with self.assertRaises(PermissionError):
                runner.run_live(artifact, anchor, responder, root, operator_stop_path=Path(directory) / "operator-stop",
                                financial_policy=policy(), token_counter=exact_test_counter)
    def test_live_replacement_is_canonical_and_performance_rerun_rejects(self):
        runner = M20ProspectiveFeasibilityRunner()
        with TemporaryDirectory() as directory:
            root = Path(directory) / "records"; artifact, anchor = signed_authority(directory)
            item = runner.work_items()[0]
            failed = runner._run(item, lambda *_: (_ for _ in ()).throw(TimeoutError("fake")), runner.store(root))
            stop = Path(directory) / "operator-stop"
            with self.assertRaises(PermissionError):
                runner.run_live_replacement(artifact, anchor, item.work_id, responder, root, operator_stop_path=stop,
                                            financial_policy=policy(), token_counter=exact_test_counter)
            replacement = runner.replacement_item(failed)
            self.assertEqual(replacement.spec.replacement_of, failed.execution_id)
            successful = runner._run(runner.work_items()[1], responder, runner.store(root))
            with self.assertRaises(PermissionError): runner.replacement_item(successful)
    def test_complete_fake_study_persists_private_diagnostics_and_resumes(self):
        runner = M20ProspectiveFeasibilityRunner()
        with TemporaryDirectory() as directory:
            root = Path(directory); records = runner.run_fake(feasibility_authorization_payload(), responder, root)
            persisted = runner.store(root).records()
            handoffs = tuple(item for item in persisted if item["telemetry"].get("evaluator_handoff"))
            diagnostics = tuple(runner.diagnostic_store(root).load(item["execution_id"]) for item in handoffs)
            projection = descriptive_projection(tuple(persisted), diagnostics)
            runner.run_fake(feasibility_authorization_payload(), lambda *_: self.fail("completed work reached transport"), root)
        self.assertEqual((len(records), len(persisted), len(diagnostics), projection["original_works"]), (24, 24, len(handoffs), 24))
        self.assertEqual(len(diagnostics), len(handoffs))
    def test_incomplete_has_no_diagnostic_sidecar(self):
        runner = M20ProspectiveFeasibilityRunner()
        with TemporaryDirectory() as directory:
            root = Path(directory); runner.run_fake(feasibility_authorization_payload(), lambda *_: reply({"kind": "stop"}), root)
            self.assertEqual(list((root / "private_evaluator_diagnostics").glob("*.json")), [])
    def test_private_diagnostic_classifies_h1_through_h4_without_public_interference(self):
        case = real_cases()[0]; state = M20RealEnvironment().initial_public_state(case.public)
        state = M20RealEnvironment().apply(case.public, state, M20Proposal(M20ProposalKind.ACT, "advance")).state
        state = M20RealEnvironment().apply(case.public, state, M20Proposal(M20ProposalKind.ACT, "advance")).state
        h1 = diagnose_after_evaluator_handoff("a", case, state, "wrong", "m20_evaluator_v1", M20Outcome.FAILURE_OR_INCORRECT)
        h2 = diagnose_after_evaluator_handoff("b", case, {**state, "progress": 0}, case.private.target, "m20_evaluator_v1", M20Outcome.FAILURE_OR_INCORRECT)
        h3 = diagnose_after_evaluator_handoff("c", case, {**state, "progress": 0}, "wrong", "m20_evaluator_v1", M20Outcome.FAILURE_OR_INCORRECT)
        h4 = diagnose_after_evaluator_handoff("d", case, state, None, "m20_evaluator_v1", M20Outcome.FAILURE_OR_INCORRECT)
        self.assertEqual([x.classification for x in (h1, h2, h3, h4)], ["answer_payload_failure", "prerequisite_failure", "combined_failure", "unknown_other"])

    def test_owner_authority_and_live_budget_are_exact_and_persistent(self):
        payload = feasibility_live_authorization_payload()
        self.assertEqual(payload["authority"], M20_FEASIBILITY_OWNER_AUTHORITY)
        self.assertEqual((payload["original_logical_provider_interaction_limit"],
                          payload["replacement_logical_provider_interaction_limit"],
                          payload["maximum_logical_provider_interactions"]), (192, 192, 384))
        with TemporaryDirectory() as directory:
            root, stop = Path(directory) / "records", Path(directory) / "operator-stop"
            budget = M20FeasibilityLiveBudget(root, payload, stop)
            budget.admit(); budget = M20FeasibilityLiveBudget(root, payload, stop)
            self.assertEqual(json.loads((root / ".m20_execution_control" / "live_budget.json").read_text())["consumed"],
                             {"original": 1, "replacement": 0, "total": 1})
            stop.touch()
            with self.assertRaises(M20FeasibilityExecutionBlocked): budget.admit()

    def test_live_stop_and_exhausted_budget_deny_before_fake_transport(self):
        runner = M20ProspectiveFeasibilityRunner()
        with TemporaryDirectory() as directory:
            root, stop = Path(directory) / "records", Path(directory) / "operator-stop"
            artifact, anchor = signed_authority(directory); stop.touch()
            with self.assertRaises(PermissionError):
                runner.run_live(artifact, anchor, lambda *_: self.fail("stopped work reached transport"), root, operator_stop_path=stop,
                                financial_policy=policy(), token_counter=exact_test_counter)
            stop.unlink(); budget = M20FeasibilityLiveBudget(root, feasibility_live_authorization_payload(financial_policy=policy()), stop)
            budget._persist({**budget._expected(), "consumed": {"original": 192, "replacement": 192, "total": 384}})
            with self.assertRaises(PermissionError):
                runner.run_live(artifact, anchor, lambda *_: self.fail("exhausted work reached transport"), root, operator_stop_path=stop,
                                financial_policy=policy(), token_counter=exact_test_counter)

    def test_financial_ledger_persists_observed_and_unknown_charges(self):
        with TemporaryDirectory() as directory:
            root, stop, payload = Path(directory) / "records", Path(directory) / "stop", feasibility_live_authorization_payload(financial_policy=policy())
            ledger = M20FeasibilityFinancialLedger(root, payload, policy(), exact_test_counter, stop)
            first = ledger.reserve("work", "logical-1", 0, {"request": True})
            ledger.settle(first, {"usage": {"prompt_cache_hit_tokens": 1, "prompt_cache_miss_tokens": 2, "completion_tokens": 3}}, "response_received")
            second = ledger.reserve("work", "logical-2", 0, {"request": True}); ledger.settle(second, None, "TimeoutError")
            summary = M20FeasibilityFinancialLedger(root, payload, policy(), exact_test_counter, stop).summary()
        self.assertEqual((summary["physical_attempts"], summary["logical_operations"]), (2, 2))
        self.assertGreater(summary["observed_cny_nano"], 0); self.assertGreater(summary["unresolved_cny_nano"], 0)

    def test_financial_token_limit_and_crashed_reservation_fail_closed(self):
        with TemporaryDirectory() as directory:
            root, stop, payload = Path(directory) / "records", Path(directory) / "stop", feasibility_live_authorization_payload(financial_policy=policy(10))
            ledger = M20FeasibilityFinancialLedger(root, payload, policy(10), lambda _request: 11, stop)
            with self.assertRaises(M20FinancialControlBlocked): ledger.reserve("work", "logical", 0, {})
            ledger = M20FeasibilityFinancialLedger(root, payload, policy(10), exact_test_counter, stop)
            ledger.reserve("work", "logical", 0, {})
            with self.assertRaises(M20FinancialControlBlocked): ledger.reserve("work", "logical", 0, {})

    def test_financial_internal_stop_and_operator_stop_block_new_attempts(self):
        tight = M20FeasibilityFinancialPolicy("test_exact_deepseek_tokenizer_v1", 1,
            planned_total_cny_nano=8_000_000, warning_cny_nano=3_000_000, internal_stop_cny_nano=5_000_000)
        with TemporaryDirectory() as directory:
            root, stop = Path(directory) / "records", Path(directory) / "stop"
            payload = feasibility_live_authorization_payload(financial_policy=tight)
            ledger = M20FeasibilityFinancialLedger(root, payload, tight, lambda _request: 1, stop)
            ledger.reserve("work", "logical-1", 0, {})
            with self.assertRaises(M20FinancialControlBlocked): ledger.reserve("work", "logical-2", 0, {})
            stop.touch()
            with self.assertRaises(M20FinancialControlBlocked): ledger.reserve("work", "logical-3", 0, {})

    def test_retry_attempts_are_separately_reserved_and_unresolved(self):
        runner = M20ProspectiveFeasibilityRunner()
        with TemporaryDirectory() as directory:
            root, stop, payload = Path(directory) / "records", Path(directory) / "stop", feasibility_live_authorization_payload(financial_policy=policy())
            ledger = M20FeasibilityFinancialLedger(root, payload, policy(), exact_test_counter, stop)
            record = runner._run(runner.work_items()[0], lambda *_: (_ for _ in ()).throw(TimeoutError("fake")), runner.store(root), financial=ledger)
            summary = ledger.summary()
        self.assertEqual(record.outcome, M20Outcome.PROVIDER_FAILURE)
        self.assertEqual((summary["physical_attempts"], summary["logical_operations"]), (3, 1))
        self.assertGreater(summary["unresolved_cny_nano"], 0)

if __name__ == "__main__": unittest.main()
