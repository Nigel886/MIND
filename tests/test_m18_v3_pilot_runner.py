"""Provider-free integrity tests for the v3 pilot-only execution entry point."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.evaluation.m18_v2_provider_diagnostics import M18V2SystematicProviderStop
from src.evaluation.m18_v3_pilot_runner import (
    M18V3PilotPlan, M18V3PilotRecord,
    M18V3PilotRunner, M18V3PilotResultStore, M18V3PilotProvenance,
    M18_V3_EXPECTED_MANIFEST_HASH, M18_V3_PILOT_RESULT_NAMESPACE, main,
)
from src.evaluation.m18_v2_pilot_runner import M18V2PilotIntegrityError
from src.evaluation.m18_v3_runtime import M18_V3_SYSTEMS


class _Provider:
    transport_attempts_per_logical_call = 1
    def __init__(self, failure: str | None = None): self.failure = failure; self.calls = 0
    @staticmethod
    def _context(request):
        value=request.to_dict()
        return (value["public_context"]["task"]["public_input"] if "public_context" in value else value["public_task"]["public_input"])["m18_v3_public_action_context"]
    def generate(self, request):
        self.calls += 1
        if self.failure: raise RuntimeError(self.failure)
        context=self._context(request); action=context["current_action"]
        return json.dumps({"action":"answer","answer":context["state"]["current_value"]} if action is None else {"action":"tool_call","tool_name":action["tool_id"],"parameters":action["parameters"]})
    def plan(self, request):
        self.calls += 1
        if self.failure: raise RuntimeError(self.failure)
        self._context(request)
        return json.dumps({"steps":[{"step_id":str(i),"subgoal":"public current action","capability_id":None} for i in range(6)]})
    def execute(self, request): return self.generate(request)


class M18V3PilotRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.plan=M18V3PilotPlan.from_repository(Path("."))
    def runner(self, root: Path): return M18V3PilotRunner(self.plan,result_root=root)

    def test_plan_is_exact_pilot_only_frozen_universe(self):
        self.assertEqual((len(self.plan.cases),len(self.plan.expected)),(18,360))
        self.assertEqual(len({x.run_id for x in self.plan.expected}),360)
        self.assertTrue(all(x.identity.schema=="m18_v3_logical_run_id_v1" for x in self.plan.expected))
        self.assertEqual(self.plan.manifest["manifest_hash"],M18_V3_EXPECTED_MANIFEST_HASH)
        self.assertIn("v3/pilot",str(self.plan.result_root).replace("\\","/"))
        self.assertNotEqual(M18_V3_PILOT_RESULT_NAMESPACE,Path("evaluation/m18/results/v2/pilot/m18_suite_v2"))

    def test_preflight_and_no_execute_do_not_call_provider_or_create_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"records"; runner=self.runner(root)
            state=runner.preflight()
            self.assertEqual(tuple(state.__dict__.values()),(360,0,360,0,0,0))
            self.assertFalse(root.exists())
            self.assertEqual(main(["--suite","m18_suite_v3","--split","pilot","--result-root",str(root)]),0)
            self.assertFalse(root.exists())

    def test_cli_rejects_wrong_suite_and_nonpilot_splits(self):
        with self.assertRaises(SystemExit): main(["--suite","m18_suite_v2"])
        for split in ("formal","diagnostic","historical","unknown"):
            with self.assertRaises(SystemExit): main(["--split",split])

    def test_all_four_real_v3_adapter_dispatches_use_public_context(self):
        with tempfile.TemporaryDirectory() as directory:
            runner=self.runner(Path(directory)); seen=[]
            def factory(system): return _Provider()
            results=runner.execute(provider_factory=factory,limit=20)
            self.assertEqual({x.provenance.identity.comparator_id for x in results},set(M18_V3_SYSTEMS))
            self.assertTrue(all(x.evaluator_outcome=="success" for x in results))

    def test_atomic_admission_reread_duplicate_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            store=M18V3PilotResultStore(Path(directory),self.plan.expected,self.plan.manifest); store.initialize()
            expected=self.plan.expected[0]
            record=M18V3PilotRecord(expected,"success","answer_submitted",None,{"logical_provider_calls":1,"transport_attempts":1})
            self.assertEqual(store.persist(record),record)
            with self.assertRaises(M18V2PilotIntegrityError): store.persist(record)
            path=Path(directory)/(record.run_id+".json"); value=json.loads(path.read_text()); value["terminal"]="tampered"; path.write_text(json.dumps(value))
            with self.assertRaises(M18V2PilotIntegrityError): store.records()

    def test_missing_only_resume_and_crash_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); runner=self.runner(root)
            first=runner.execute(provider_factory=lambda _: _Provider(),limit=3)
            self.assertEqual(len(first),3)
            resumed=runner.execute(provider_factory=lambda _: _Provider(),limit=2)
            self.assertEqual(len(resumed),2); self.assertEqual(len(runner.store.records()),5)
            with self.assertRaises(RuntimeError): runner.execute(provider_factory=lambda _: _Provider(),limit=1,after_persist=lambda _: (_ for _ in ()).throw(RuntimeError("crash after commit")))
            self.assertEqual(len(runner.store.records()),6)
            self.assertEqual(runner.preflight().missing,354)

    def test_structural_stop_persists_but_transients_do_not(self):
        with tempfile.TemporaryDirectory() as directory:
            runner=self.runner(Path(directory)/"structural")
            with self.assertRaises(M18V2SystematicProviderStop): runner.execute(provider_factory=lambda system: _Provider("schema_incompatible") if system == "direct_tool_calling" else _Provider(),limit=7)
            self.assertIsNotNone(runner.store.systematic_stop())
            with self.assertRaises(M18V2SystematicProviderStop): runner.execute(provider_factory=lambda _: _Provider(),limit=1)
            transient=self.runner(Path(directory)/"transient")
            transient.execute(provider_factory=lambda system: _Provider("http_503") if system == "direct_tool_calling" else _Provider(),limit=7)
            self.assertIsNone(transient.store.systematic_stop())

    def test_manifest_binding_and_secret_bearing_diagnostics_fail_closed_or_redact(self):
        with self.assertRaises(ValueError):
            M18V3PilotProvenance(self.plan.expected[0].identity, "0" * 64)
        with tempfile.TemporaryDirectory() as directory:
            runner=self.runner(Path(directory))
            records=runner.execute(provider_factory=lambda system: _Provider("api_key=sk-test-123 BearerSecretXYZ") if system == "direct_tool_calling" else _Provider(),limit=6)
            payload=json.dumps(records[-1].to_dict())
            self.assertNotIn("sk-test-123",payload); self.assertNotIn("BearerSecretXYZ",payload)

    def test_fake_full_lifecycle_pairing_and_distribution(self):
        with tempfile.TemporaryDirectory() as directory:
            runner=self.runner(Path(directory)); records=runner.execute(provider_factory=lambda _: _Provider())
            self.assertEqual(len(records),360); self.assertEqual(len(runner.store.records()),360)
            self.assertEqual({x.provenance.identity.comparator_id:sum(y.provenance.identity.comparator_id==x.provenance.identity.comparator_id for y in records) for x in records},{name:90 for name in M18_V3_SYSTEMS})
            self.assertEqual({r:sum(x.provenance.identity.repetition==r for x in records) for r in range(1,6)},{r:72 for r in range(1,6)})
            self.assertTrue(all(sum(x.provenance.identity.case_id==case.case_id for x in records)==20 for case in self.plan.cases))
            cells={(x.provenance.identity.case_id,x.provenance.identity.repetition) for x in records}
            self.assertEqual(len(cells),90)
            self.assertTrue(all(sum(x.provenance.identity.case_id==case and x.provenance.identity.repetition==rep for x in records)==4 for case,rep in cells))
