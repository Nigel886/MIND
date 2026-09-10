from __future__ import annotations
import json, unittest
from hashlib import sha256
from pathlib import Path
from src.evaluation.deepseek_transport import DEEPSEEK_ENDPOINT,DeepSeekGenerationConfig,DeepSeekRestTransport,DeepSeekTransportSuccess
from src.evaluation.m16_benchmark_contracts import load_frozen_m16_deepseek_manifest,load_frozen_m16_flash_lite_manifest
from src.evaluation.m16_deepseek_v4_flash_formal_execution import DEFAULT_RESULT_DIRECTORY,EXPECTED_MANIFEST_HASH,execute_deepseek_formal_benchmark,validate_deepseek_formal_preflight

ROOT=Path(__file__).resolve().parents[1]
class _Post:
 def __init__(self,response): self.response=response;self.calls=[]
 def __call__(self,url,headers,body,timeout): self.calls.append((url,json.loads(body)));return self.response
class DeepSeekMigrationTests(unittest.TestCase):
 def test_frozen_transport_request_and_usage_mapping(self):
  post=_Post({"model":"deepseek-flash","choices":[{"message":{"content":"{\"status\":\"ok\"}"}}],"usage":{"prompt_tokens":3,"completion_tokens":2,"total_tokens":5,"prompt_cache_hit_tokens":1}})
  r=DeepSeekRestTransport(http_post=post,environment={"DEEPSEEK_API_KEY":"development"},sleeper=lambda _:None).generate("Return JSON.")
  self.assertIsInstance(r,DeepSeekTransportSuccess); self.assertEqual(r.observation.to_dict()["cached_tokens"],1)
  url,body=post.calls[0]; self.assertEqual(url,DEEPSEEK_ENDPOINT); self.assertEqual(body["model"],"deepseek-v4-flash"); self.assertEqual(body["thinking"],{"type":"disabled"}); self.assertEqual(body["response_format"],{"type":"json_object"}); self.assertEqual((body["temperature"],body["top_p"],body["n"],body["max_tokens"]),(0,1,1,512))
 def test_config_manifest_and_result_state_are_isolated(self):
  raw=(ROOT/"evaluation/config/m16_deepseek_v4_flash_v1.json").read_bytes(); m=load_frozen_m16_deepseek_manifest()
  self.assertEqual(sha256(raw).hexdigest(),"2a19406120cdb5627ee8520c5a32fe01d7226500ac0c1727b4f4794971a8d97e");self.assertEqual(m.manifest_hash,EXPECTED_MANIFEST_HASH);self.assertNotEqual(m.manifest_hash,load_frozen_m16_flash_lite_manifest().manifest_hash)
  self.assertEqual((m.provider_request_model_id,m.official_documented_model_version),("deepseek-v4-flash","DeepSeek-V4-Flash-0731"));self.assertEqual(DEFAULT_RESULT_DIRECTORY,"evaluation/results/m16_deepseek_v4_flash")
  _,cases,definitions=validate_deepseek_formal_preflight();self.assertEqual((len(cases),len(definitions),len({x.run_id for x in definitions})),(96,960,960))
  with self.assertRaises(ValueError): execute_deepseek_formal_benchmark("evaluation/results/m16_flash_lite")
 def test_unexpected_returned_model_stops(self):
  post=_Post({"model":"unexpected","choices":[{"message":{"content":"{}"}}]})
  with self.assertRaises(RuntimeError): DeepSeekRestTransport(http_post=post,environment={"DEEPSEEK_API_KEY":"development"}).generate("Return JSON.")
