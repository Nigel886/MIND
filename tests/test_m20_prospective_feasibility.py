from __future__ import annotations
import json
import re
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from src.evaluation.m20_prospective_feasibility import (M20ProspectiveFeasibilityRunner, build_feasibility_manifest, feasibility_authorization_payload, feasibility_live_authorization_payload, verify_feasibility_authorization, descriptive_projection)
from src.evaluation.m20_evaluator_failure_diagnostics import diagnose_after_evaluator_handoff
from src.evaluation.m20_real_case_source import M20RealEnvironment, real_cases
from src.evaluation.m20_harness import M20Outcome, M20Proposal, M20ProposalKind

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
        with self.assertRaises(PermissionError): runner.run_live(Path("missing.json"), lambda *_: self.fail("transport"), Path("records"))
    def test_live_authorization_admits_only_exact_temporary_artifact_before_fake_transport(self):
        runner = M20ProspectiveFeasibilityRunner()
        with TemporaryDirectory() as directory:
            root, artifact = Path(directory) / "records", Path(directory) / "authorization.json"
            artifact.write_text(json.dumps(feasibility_authorization_payload()), encoding="utf-8")
            with self.assertRaises(PermissionError): runner.run_live(artifact, lambda *_: self.fail("synthetic reached transport"), root)
            artifact.write_text(json.dumps(feasibility_live_authorization_payload()), encoding="utf-8")
            records = runner.run_live(artifact, responder, root)
        self.assertEqual(len(records), 24)
    def test_live_replacement_is_canonical_and_performance_rerun_rejects(self):
        runner = M20ProspectiveFeasibilityRunner()
        with TemporaryDirectory() as directory:
            root, artifact = Path(directory) / "records", Path(directory) / "authorization.json"
            artifact.write_text(json.dumps(feasibility_live_authorization_payload()), encoding="utf-8")
            item = runner.work_items()[0]
            failed = runner._run(item, lambda *_: (_ for _ in ()).throw(TimeoutError("fake")), runner.store(root))
            replacement = runner.run_live_replacement(artifact, item.work_id, responder, root)
            again = runner.run_live_replacement(artifact, item.work_id, lambda *_: self.fail("completed replacement transport"), root)
            self.assertEqual((replacement.spec.replacement_of, again.digest), (failed.execution_id, replacement.digest))
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

if __name__ == "__main__": unittest.main()
