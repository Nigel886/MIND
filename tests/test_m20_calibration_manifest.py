import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from src.evaluation.m20_calibration_manifest import build_manifest, load_manifest, persist_manifest, require_manifest, validate_manifest

class M20CalibrationManifestTest(unittest.TestCase):
 def test_deterministic_complete_reloadable_manifest(self):
  a,b=build_manifest(),build_manifest(); self.assertEqual(a,b); self.assertEqual((len(a["pairs"]),a["repetitions"]),(60,5)); self.assertEqual(len({x["pair_id"] for x in a["pairs"]}),60)
  with TemporaryDirectory() as d: self.assertEqual(persist_manifest(Path(d)/"m.json"),load_manifest(Path(d)/"m.json"))
 def test_mutations_fail_closed_and_execution_blocked(self):
  value=build_manifest()
  for key in ("provider_hash","resource_ceiling_identity","environment_id","metric_version","statistical_protocol"):
   changed=json.loads(json.dumps(value)); changed[key]="wrong"
   with self.assertRaises(ValueError): validate_manifest(changed)
  changed=json.loads(json.dumps(value)); changed["pairs"].pop()
  with self.assertRaises(ValueError): validate_manifest(changed)
  with self.assertRaises(PermissionError): require_manifest(value)
  with self.assertRaises(ValueError): require_manifest(None)
if __name__ == "__main__": unittest.main()
