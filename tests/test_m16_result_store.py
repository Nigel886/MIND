import tempfile, unittest
from src.evaluation.m16_benchmark_contracts import *
from src.evaluation.m16_result_store import M16ResultStore
class ResultStoreTests(unittest.TestCase):
 def test_append_and_resume(self):
  m=M16FormalExecutionManifest("1.1.0","1.0.0","suite","split","1","config")
  with tempfile.TemporaryDirectory() as p:
   s=M16ResultStore(p,m); s.initialize(); d=M16FormalRunDefinition(m.manifest_hash,"dev",M16BaselineID.MIND_LITE_V1,1,0)
   r=M16RunAttemptRecord(RESULT_SCHEMA_VERSION,d.run_id,d.attempt_id(1),1,"dev",M16BaselineID.MIND_LITE_V1,1,"direct","easy","development","agent_final_answer",True,M16FailureCategory.SUCCESS,1,0,manifest_hash=m.manifest_hash)
   s.append(r); self.assertIn(d.run_id,s.completed_run_ids())
   with self.assertRaises(ValueError): s.append(r)
