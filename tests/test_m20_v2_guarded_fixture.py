import json
import re
import unittest
from pathlib import Path
from tests.m20_memory_native_ops import MemoryNativeOps
from tests.m20_test_scratch import TemporaryDirectory
from src.evaluation.m20_harness import M20GuardedEvidenceStoreAccessProvider, M20IntegrityError
from src.evaluation.m20_prospective_feasibility import M20ProspectiveFeasibilityRunner, M20_FEASIBILITY_GENERATION_V2

class GuardedV2Fixture:
    def __init__(self, directory):
        self.repository=Path(directory)/"repository"; self.destination=self.repository/"evaluation"/"results"/"m20_task_evaluator_feasibility_v2"
        self.destination.mkdir(parents=True); (self.destination/"private_evaluator_diagnostics").mkdir(); (self.destination/".m20_execution_control").mkdir(); self.ops=MemoryNativeOps()
        evaluation=self.ops.provision(self.ops.root,"evaluation"); results=self.ops.provision(evaluation,"results"); self.node=self.ops.provision(results,"m20_task_evaluator_feasibility_v2"); self.diagnostics_node=self.ops.provision(self.node,"private_evaluator_diagnostics"); self.control_node=self.ops.provision(self.node,".m20_execution_control")
        self.factory=self.ops.store_access_provider(self.repository,self.destination,("evaluation","results","m20_task_evaluator_feasibility_v2"))
        self.runner=M20ProspectiveFeasibilityRunner(generation=M20_FEASIBILITY_GENERATION_V2,evidence_writer_factory=self.factory)

class GuardedV2FixtureTests(unittest.TestCase):
    @staticmethod
    def _answer_transport(runner, item, calls):
        def transport(*_args):
            calls.append(1)
            request=_args[0]; public=json.loads(request["messages"][1]["content"].split("Public input: ",1)[1])
            match=re.fullmatch(r"Complete the public ([a-z_]+) task (\d+)\.",public["task"])
            if public["legal_decision_kinds"]==["answer","stop"]:
                value={"kind":"answer","payload":"answer:m20.real."+match.group(1)+"."+int(match.group(2)).__format__("02d")}
            elif public["state"].get("requires_observation") and not public["state"].get("observed"):
                value={"kind":"act","action_id":"observe"}
            elif public["state"].get("requires_recovery") and not public["state"].get("recovered"):
                value={"kind":"act","action_id":"recover"}
            else: value={"kind":"act","action_id":"advance"}
            return {"model":"deepseek-flash","choices":[{"message":{"content":json.dumps(value)}}]}
        return transport
    def test_real_factory_admits_and_store_writes_manifest_in_memory(self):
        with TemporaryDirectory() as directory:
            fixture=GuardedV2Fixture(directory); self.assertIsInstance(fixture.factory,M20GuardedEvidenceStoreAccessProvider)
            store=fixture.runner.store(fixture.destination)
            self.assertIn("manifest.json",fixture.ops.nodes[fixture.node].children); self.assertFalse((fixture.destination/"manifest.json").exists()); store.close()
    def test_omitted_factory_fails_closed(self):
        with TemporaryDirectory() as directory:
            fixture=GuardedV2Fixture(directory); runner=M20ProspectiveFeasibilityRunner(generation=M20_FEASIBILITY_GENERATION_V2)
            with self.assertRaises(PermissionError): runner.store(fixture.destination)
    def test_historical_v1_is_not_admitted_by_v2_factory(self):
        with TemporaryDirectory() as directory:
            fixture=GuardedV2Fixture(directory); v1=fixture.repository/"evaluation"/"results"/"m20_task_evaluator_feasibility_v1"; v1.mkdir()
            with self.assertRaises(Exception): fixture.factory(v1)
    def test_guarded_completed_ids_drive_diagnostic_sidecar_validation(self):
        with TemporaryDirectory() as directory:
            fixture=GuardedV2Fixture(directory); item=fixture.runner.work_items()[0]
            store=fixture.runner.store(fixture.destination)
            record=fixture.runner._run(item, lambda *_: (_ for _ in ()).throw(TimeoutError("offline")), store); store.close()
            fixture.ops.provision(fixture.diagnostics_node, record.execution_id+".json", directory=False, data=b"{}")
            reopened=fixture.runner.store(fixture.destination)
            with self.assertRaises(M20IntegrityError): fixture.runner.diagnostic_store(fixture.destination,reopened)
            fixture.ops.provision(fixture.diagnostics_node, ("0"*64)+".json", directory=False, data=b"{}")
            with self.assertRaises(PermissionError): fixture.runner._open_diagnostics(fixture.destination,reopened)
            reopened.close()

    def test_v2_guarded_diagnostic_write_failure_aborts_real_runner_before_evidence(self):
        with TemporaryDirectory() as directory:
            fixture=GuardedV2Fixture(directory); item=fixture.runner.work_items()[0]; store=fixture.runner.store(fixture.destination)
            fixture.runner._diagnostic_store=fixture.runner._open_diagnostics(fixture.destination,store)
            calls=[]; fixture.ops.fail["write"]=OSError("diagnostic write failed")
            with self.assertRaises(RuntimeError) as rejected:
                fixture.runner._run(item,self._answer_transport(fixture.runner,item,calls),store)
            self.assertIn("guarded",str(rejected.exception).lower())
            self.assertGreaterEqual(len(calls),1)
            self.assertNotIn(item.spec.execution_id+".json",fixture.ops.nodes[fixture.node].children)
            fixture.ops.fail.pop("write"); fixture.runner._close_diagnostics_preserving_primary(); store.close()

    def test_diagnostic_close_preserves_primary_failure(self):
        with TemporaryDirectory() as directory:
            fixture=GuardedV2Fixture(directory); store=fixture.runner.store(fixture.destination)
            fixture.runner._diagnostic_store=fixture.runner._open_diagnostics(fixture.destination,store)
            fixture.ops.fail["close"]=OSError("diagnostic close failed")
            try:
                try:
                    raise ValueError("primary execution failure")
                except ValueError:
                    fixture.runner._close_diagnostics_preserving_primary()
                    raise
            except ValueError as error:
                self.assertIn("diagnostic-store cleanup failed",getattr(error,"__notes__",[""])[0])
            else: self.fail("diagnostic cleanup replaced the primary failure")
            fixture.ops.fail.pop("close"); store.close()

    def test_evidence_failure_after_diagnostic_write_leaves_rejected_orphan(self):
        with TemporaryDirectory() as directory:
            fixture=GuardedV2Fixture(directory); item=fixture.runner.work_items()[0]; store=fixture.runner.store(fixture.destination)
            diagnostics=fixture.runner._open_diagnostics(fixture.destination,store); fixture.runner._diagnostic_store=diagnostics
            original=diagnostics.persist
            def persist_then_fail(value):
                original(value)
            diagnostics.persist=persist_then_fail
            original_write=store._writer.write_new_atomic
            store._writer.write_new_atomic=lambda *_args: (_ for _ in ()).throw(OSError("evidence write failed"))
            calls=[]
            with self.assertRaises(OSError): fixture.runner._run(item,self._answer_transport(fixture.runner,item,calls),store)
            self.assertIn(item.spec.execution_id+".json",fixture.ops.nodes[fixture.diagnostics_node].children)
            self.assertNotIn(item.spec.execution_id+".json",fixture.ops.nodes[fixture.node].children)
            store._writer.write_new_atomic=original_write; fixture.runner._close_diagnostics_preserving_primary(); store.close()
            reopened=fixture.runner.store(fixture.destination)
            with self.assertRaises(PermissionError): fixture.runner._open_diagnostics(fixture.destination,reopened)
            reopened.close()


if __name__=='__main__': unittest.main()
