import unittest
from src.evaluation.m16_benchmark_contracts import *
class M16ContractsTests(unittest.TestCase):
 def test_manifest_and_schedule_are_stable(self):
  m=M16FormalExecutionManifest("1.1.0","1.0.0","suite","split","1","config")
  self.assertEqual(m.manifest_hash,M16FormalExecutionManifest.from_dict(m.to_dict()).manifest_hash)
  s=counterbalanced_schedule(m,("b","a")); self.assertEqual(s[0].baseline_id,M16BaselineID.DIRECT_TOOL_CALLING); self.assertEqual(s[0].attempt_id(1),s[0].run_id+":a1")
 def test_frozen_budget(self): self.assertEqual(M16FormalBudget().max_agent_steps,2)
 def test_tracked_manifest_values(self):
  m=load_frozen_m16_manifest()
  self.assertEqual(m.protocol_version,"1.2.0"); self.assertEqual(m.suite_generation_protocol_version,"1.1.0"); self.assertEqual(m.completion_semantics_version,"m16_completion_v2"); self.assertEqual(m.suite_version,"1.0.0")
  self.assertEqual(m.suite_hash,"a450c6fa2955136da5d4db08b892af442ab7be66034412739d91e7cbf076445c")
  self.assertEqual(m.model,"gemini-2.5-flash"); self.assertNotIn("GEMINI_API_KEY",str(m.to_dict()))
