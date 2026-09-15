"""Deterministic freeze checks; these tests do not execute agents/providers."""
from __future__ import annotations
import unittest
from src.evaluation.m18_suite_freeze import *
class M18SuiteFreezeTests(unittest.TestCase):
 def test_deterministic_pilot_and_formal_counts(self):
  self.assertEqual(pilot_suite(),pilot_suite());self.assertEqual(formal_suite(),formal_suite());self.assertEqual(len(pilot_suite()),18);self.assertEqual(len(formal_suite()),162)
 def test_allocation_balance_and_order(self):
  a=audit_suite(formal_suite());self.assertEqual(a["cohort_counts"],{"distractor_selection":54,"multi_step":54,"recovery_correction":54});self.assertEqual(a["difficulty_counts"],{"easy":54,"hard":54,"medium":54});self.assertEqual(a["subtype_counts"],{"invalid_action":27,"recoverable_failure":27})
  self.assertEqual(tuple(sorted(c.case_id for c in formal_suite())),tuple(c.case_id for c in sorted(formal_suite(),key=lambda c:c.case_id)))
 def test_public_leakage_hash_and_separation(self):
  pilot,formal=pilot_suite(),formal_suite();m,split=manifest(pilot,formal,"a8cef9b6e3c1a746a4062aa0e126308d8842d5b0")
  self.assertFalse(set(split["pilot_ids"])&set(split["formal_ids"]));self.assertEqual(m["formal"]["private_hash"],audit_suite(formal)["private_hash"]);self.assertNotEqual(m["formal"]["private_hash"],m["formal"]["public_hash"]);self.assertEqual(m["manifest_hash"],manifest(pilot,formal,"a8cef9b6e3c1a746a4062aa0e126308d8842d5b0")[0]["manifest_hash"])
 def test_case_change_changes_hash_and_audits_environment_evaluator(self):
  f=list(formal_suite());base=audit_suite(tuple(f))["private_hash"];f[0]=generate_m18_case(f[0].cohort,f[0].difficulty,999999,f[0].namespace,0);self.assertNotEqual(base,audit_suite(tuple(f))["private_hash"])
if __name__=="__main__":unittest.main()
