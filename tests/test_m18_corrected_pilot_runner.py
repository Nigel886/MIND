"""Provider-free tests for the corrected-condition M18 pilot runner."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.evaluation.m18_corrected_comparator_contract import (
    M18_CORRECTED_COMPARATOR_CONTRACT_ID, M18CorrectedRecord,
    M18CorrectedResultStore,
)
from src.evaluation.m18_corrected_pilot_runner import (
    M18CorrectedPilotPlan, M18CorrectedPilotRunner, main,
)
from src.evaluation.m18_v2_pilot_runner import M18V2PilotIntegrityError
from src.evaluation.m18_v2_provider_diagnostics import M18V2SystematicProviderStop
from src.evaluation.m18_v3_runtime import M18_V3_SYSTEMS


class _StructuralProviderError(RuntimeError):
    category = "provider_contract_error"


class _Provider:
    transport_attempts_per_logical_call = 1
    def __init__(self, failure=None): self.failure = failure
    @staticmethod
    def _context(request):
        value = request.to_dict()
        return (value["public_context"]["task"]["public_input"] if "public_context" in value else value["public_task"]["public_input"])["m18_v3_public_action_context"]
    def generate(self, request):
        if self.failure: raise _StructuralProviderError(self.failure)
        context = self._context(request); action = context["current_action"]
        return json.dumps({"action":"answer","answer":context["state"]["current_value"]} if action is None else {"action":"tool_call","tool_name":action["tool_id"],"parameters":action["parameters"]})
    def plan(self, request):
        if self.failure: raise _StructuralProviderError(self.failure)
        self._context(request)
        return json.dumps({"steps":[{"step_id":str(i),"subgoal":"public","capability_id":None} for i in range(6)]})
    def execute(self, request): return self.generate(request)


class CorrectedPilotRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.plan = M18CorrectedPilotPlan.from_repository(Path("."))

    def runner(self, root): return M18CorrectedPilotRunner(self.plan, result_root=root)

    def test_identity_universe_preflight_and_guard(self):
        self.assertEqual(len(self.plan.expected), 360)
        self.assertEqual(len({item.run_id for item in self.plan.expected}), 360)
        self.assertTrue(all(item.run_id.startswith("m18ccv2-") for item in self.plan.expected))
        self.assertTrue(all(item.identity.comparator_contract_id == M18_CORRECTED_COMPARATOR_CONTRACT_ID for item in self.plan.expected))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "records"; runner = self.runner(root)
            self.assertEqual((runner.preflight().expected, runner.preflight().valid, runner.preflight().missing), (360, 0, 360))
            self.assertFalse(root.exists())

    def test_cli_rejects_other_condition_and_formal(self):
        with self.assertRaises(ValueError): main(["--condition", "m18_v3"])
        with self.assertRaises(SystemExit): main(["--split", "formal"])

    def test_fake_full_lifecycle_and_pairing(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = self.runner(Path(directory))
            records = runner.execute(provider_factory=lambda _: _Provider())
            self.assertEqual((len(records), len(runner.store.records())), (360, 360))
            self.assertEqual({name: sum(r.provenance.identity.comparator_id == name for r in records) for name in M18_V3_SYSTEMS}, {name:90 for name in M18_V3_SYSTEMS})
            self.assertEqual({rep: sum(r.provenance.identity.repetition == rep for r in records) for rep in range(1,6)}, {rep:72 for rep in range(1,6)})
            cells = {(r.provenance.identity.case_id, r.provenance.identity.repetition) for r in records}
            self.assertEqual(len(cells), 90)
            self.assertTrue(all(sum(r.provenance.identity.case_id == case and r.provenance.identity.repetition == rep for r in records) == 4 for case, rep in cells))

    def test_admission_resume_and_crash_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = self.runner(Path(directory))
            self.assertEqual(len(runner.execute(provider_factory=lambda _: _Provider(), limit=3)), 3)
            self.assertEqual(len(runner.execute(provider_factory=lambda _: _Provider(), limit=2)), 2)
            with self.assertRaises(RuntimeError):
                runner.execute(provider_factory=lambda _: _Provider(), limit=1, after_persist=lambda _: (_ for _ in ()).throw(RuntimeError("after commit")))
            self.assertEqual((len(runner.store.records()), runner.preflight().missing), (6, 354))
            with self.assertRaises(Exception): runner.store.persist(runner.store.records()[0])

    def test_tamper_v3_rejection_and_systematic_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = self.runner(Path(directory) / "tamper")
            record = M18CorrectedRecord(runner.plan.expected[0], "answer_submitted", "success")
            runner.store.persist(record)
            path = runner.store.root / (record.run_id + ".json")
            payload = json.loads(path.read_text()); payload["provenance"]["comparator_contract_id"] = "m18_v3"
            path.write_text(json.dumps(payload))
            with self.assertRaises(M18V2PilotIntegrityError): runner.store.records()
        with tempfile.TemporaryDirectory() as directory:
            runner = self.runner(Path(directory))
            with self.assertRaises(M18V2SystematicProviderStop):
                runner.execute(provider_factory=lambda system: _Provider("schema_incompatible api_key=sk-test-1") if system == "direct_tool_calling" else _Provider(), limit=7)
            self.assertIsNotNone(runner.systematic_stop())
            self.assertNotIn("sk-test-1", runner.stop_path.read_text())
            with self.assertRaises(M18V2SystematicProviderStop): runner.execute(provider_factory=lambda _: _Provider(), limit=1)
