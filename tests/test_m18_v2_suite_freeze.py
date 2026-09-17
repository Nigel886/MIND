"""Frozen-file validation for M18 v2; no provider or benchmark execution."""
from __future__ import annotations
import json
from tempfile import TemporaryDirectory
import unittest
from pathlib import Path
from src.evaluation.m18_shared_provider import M18SharedProviderConfiguration
from src.evaluation.m18_v2_suite_freeze import ROOT,build,load_and_validate,write
from src.evaluation.m18_v2_pilot_runner import M18V2PilotPlan, M18V2PilotResultStore
from src.evaluation.m18_v2_provenance import M18_V2_COMPARATOR_CONDITIONS, M18_V2_RUNTIME_ID
from src.evaluation.m18_v2_semantics import M18_V2_BUDGET_ID, M18_V2_ENVIRONMENT_ID, M18_V2_EVALUATOR_ID, M18_V2_SUITE_VERSION

class M18V2SuiteFreezeTests(unittest.TestCase):
 def test_written_freeze_reloads_and_reconciles(self):
  m=load_and_validate(); self.assertEqual((m["suite_identity"],m["pilot"]["case_count"],m["formal"]["case_count"]),(M18_V2_SUITE_VERSION,18,162)); self.assertEqual((m["pilot_run_count"],m["formal_run_count"]),(360,3240))
 def test_public_artifacts_exclude_private_truth(self):
  for path,count in ((ROOT/"pilot/public_cases.json",18),(ROOT/"formal/public_cases.json",162)):
   value=json.loads(path.read_text()); self.assertEqual(len(value),count); self.assertNotIn("expected_final_result",str(value)); self.assertNotIn("generation_seed",str(value))
 def test_private_public_ids_and_regeneration_match(self):
  _,_,pp,pv,fp,fv,split,manifest=build()
  self.assertEqual([x["case_id"] for x in pp],[x["case_id"] for x in pv]); self.assertEqual([x["case_id"] for x in fp],[x["case_id"] for x in fv]); self.assertFalse(set(split["pilot_ids"])&set(split["formal_ids"])); self.assertEqual(manifest,load_and_validate())
 def test_distribution_and_hash_binding(self):
  m=load_and_validate(); self.assertEqual(m["pilot"]["cohort_counts"],{"distractor_selection":6,"multi_step":6,"recovery_correction":6}); self.assertEqual(m["formal"]["cohort_counts"],{"distractor_selection":54,"multi_step":54,"recovery_correction":54}); self.assertEqual(m["pilot"]["difficulty_counts"],{"easy":6,"hard":6,"medium":6}); self.assertEqual(m["formal"]["difficulty_counts"],{"easy":54,"hard":54,"medium":54})
 def test_manifest_binds_freeze_identities_and_admission(self):
  m=load_and_validate()
  self.assertEqual((m["environment_id"],m["evaluator_id"],m["budget_id"],m["runtime_id"]),(M18_V2_ENVIRONMENT_ID,M18_V2_EVALUATOR_ID,M18_V2_BUDGET_ID,M18_V2_RUNTIME_ID))
  self.assertEqual(m["comparator_conditions"],M18_V2_COMPARATOR_CONDITIONS); self.assertEqual(m["repetitions"],[1,2,3,4,5])
  self.assertEqual(m["provider_config_hash"],M18SharedProviderConfiguration().config_hash)
  self.assertEqual(set(m["result_admission_requirements"]),{"run_id","repetition","case_id","suite_identity","environment_id","evaluator_id","budget_id","runtime_id","comparator_condition_id","provider_config_hash","execution_baseline"})
  self.assertEqual(m["pilot"]["reachability_passed"],18); self.assertEqual(m["formal"]["reachability_passed"],162)
  self.assertEqual((m["pilot"]["target_public_result_mismatches"],m["formal"]["target_public_result_mismatches"]),(0,0))
 def test_freeze_write_refuses_nonidentical_overwrite(self):
  with TemporaryDirectory() as directory:
   root=Path(directory)/"suites_v2"; first=write(root); self.assertEqual(first,write(root))
   target=root/"pilot"/"public_cases.json"; target.write_text("[]\n",encoding="utf-8")
   with self.assertRaisesRegex(ValueError,"refusing overwrite"): write(root)
 def test_v2_result_namespaces_are_lifecycle_aware_and_admission_bound(self):
  """Protect a clean checkout while admitting only frozen evidence after execution.

  Before any authorized execution both reserved namespaces are absent.  Once
  the canonical pilot namespace exists, this test stays read-only and accepts
  it only when its manifest and every record pass the frozen admission contract.
  """
  m=load_and_validate(); pilot=Path(m["result_namespace_spec"]["pilot"]); formal=Path(m["result_namespace_spec"]["formal"])
  self.assertFalse(any(formal.glob("*.json")) if formal.exists() else False)
  if not pilot.exists(): return
  plan=M18V2PilotPlan.from_repository(Path(".")); self.assertEqual(pilot.resolve(),plan.result_root.resolve())
  store=M18V2PilotResultStore(pilot,plan.expected,plan.suite_manifest)
  self.assertTrue(store.manifest_path.exists()); self.assertEqual(json.loads(store.manifest_path.read_text()),store._store_manifest())
  records=store.records(); self.assertEqual(len(records),len({record.run_id for record in records}))
  self.assertTrue(all(record.run_id in {item.run_id for item in plan.expected} for record in records))
if __name__=="__main__": unittest.main()
