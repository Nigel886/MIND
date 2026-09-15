from __future__ import annotations

import json
from pathlib import Path
import unittest
from urllib.error import HTTPError

from src.evaluation.m18_shared_provider import (
    M18SharedProviderConfiguration, M18SharedProviderClient, M18ProviderTransportError,
    M18SharedMINDProvider, M18SharedDirectProvider, M18SharedReActProvider, M18SharedPlanProvider,
)


class QueuePost:
    def __init__(self, outcomes): self.outcomes, self.calls = list(outcomes), []
    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, dict(headers), body, timeout)); result = self.outcomes.pop(0)
        if isinstance(result, Exception): raise result
        return result


def response(content='{"action":"answer","answer":"ok"}'):
    return {"model": "deepseek-flash", "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5,
                      "prompt_tokens_details": {"cached_tokens": 1}}}


class M18SharedProviderTests(unittest.TestCase):
    def client(self, outcomes, **kwargs):
        post = QueuePost(outcomes); clocks = iter((0, 1_000_000, 2_000_000, 3_000_000))
        return M18SharedProviderClient(http_post=post, environment={"DEEPSEEK_API_KEY": "not-serialized"},
            sleeper=lambda _: None, clock_ns=lambda: next(clocks), **kwargs), post

    def test_configuration_is_immutable_canonical_and_secret_free(self):
        config = M18SharedProviderConfiguration()
        self.assertEqual(config, M18SharedProviderConfiguration()); self.assertEqual(len(config.config_hash), 64)
        self.assertNotIn("API_KEY", json.dumps(config.to_dict())); self.assertNotIn("not-serialized", json.dumps(config.to_dict()))
        with self.assertRaises(ValueError): M18SharedProviderConfiguration(requested_model="other")
        with self.assertRaises(TypeError): config.thinking["type"] = "enabled"

    def test_same_semantic_configuration_has_stable_hash(self):
        self.assertEqual(M18SharedProviderConfiguration().config_hash, M18SharedProviderConfiguration().config_hash)

    def test_tracked_manifest_matches_canonical_configuration_without_credentials(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "evaluation/m18/manifests/provider_config_v1.json").read_text(encoding="utf-8"))
        config = M18SharedProviderConfiguration()
        self.assertEqual(manifest["canonical_settings"], config.to_dict())
        self.assertEqual(manifest["provider_config_hash"], config.config_hash)
        self.assertEqual(manifest["adapter_contract_status"], {"mind": "PASS", "direct": "PASS", "react": "PASS", "plan_planner": "PASS", "plan_executor": "PASS"})

    def test_success_records_nullable_safe_telemetry_and_request_condition(self):
        client, post = self.client([response()]); result = client.generate("Return JSON.", {"public": True})
        self.assertEqual((client.logical_provider_calls, client.transport_attempts), (1, 1))
        self.assertEqual(result.to_dict()["returned_model"], "deepseek-flash")
        self.assertEqual(result.to_dict()["cached_tokens"], 1)
        body = json.loads(post.calls[0][2]); self.assertEqual(body["thinking"], {"type": "disabled"})
        self.assertEqual((body["temperature"], body["top_p"], body["max_tokens"], body["stream"]), (0, 1, 512, False))
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertNotIn("not-serialized", post.calls[0][2].decode())

    def test_absent_optional_usage_telemetry_remains_null(self):
        client, _ = self.client([{"choices": [{"message": {"content": '{"action":"answer","answer":"ok"}'}}]}])
        record = client.generate("Return JSON.", {})
        self.assertIsNone(record.prompt_tokens); self.assertIsNone(record.completion_tokens)
        self.assertIsNone(record.total_tokens); self.assertIsNone(record.cached_tokens)

    def test_exposed_unexpected_model_identity_is_rejected_without_substitution(self):
        client, post = self.client([{**response(), "model": "unapproved-model"}])
        with self.assertRaises(M18ProviderTransportError) as raised: client.generate("Return JSON.", {})
        self.assertEqual(raised.exception.category, "model_identity_mismatch")
        self.assertEqual((client.logical_provider_calls, client.transport_attempts, len(post.calls)), (1, 1, 1))

    def test_transient_retry_is_one_logical_call_and_two_attempts(self):
        client, post = self.client([HTTPError("x", 503, "bad", {}, None), response()])
        result = client.generate("JSON", {})
        self.assertEqual((client.logical_provider_calls, client.transport_attempts, result.transport_attempts), (1, 2, 2)); self.assertEqual(len(post.calls), 2)

    def test_malformed_completed_output_is_not_transport_retried(self):
        client, post = self.client([{"choices": []}])
        with self.assertRaises(M18ProviderTransportError) as raised: client.generate("JSON", {})
        self.assertEqual(raised.exception.category, "malformed_json"); self.assertEqual(len(post.calls), 1)

    def test_no_fallback_model_or_semantic_cache(self):
        client, post = self.client([response(), response()])
        client.generate("JSON", {}); client.generate("JSON", {})
        self.assertEqual((client.logical_provider_calls, len(post.calls)), (2, 2))
        self.assertTrue(all(json.loads(call[2])["model"] == "deepseek-flash" for call in post.calls))

    def test_one_configuration_binds_all_four_adapter_protocols(self):
        client, _ = self.client([])
        self.assertIs(M18SharedMINDProvider(client).client.configuration, client.configuration)
        self.assertIs(M18SharedDirectProvider(client).client.configuration, client.configuration)
        self.assertIs(M18SharedReActProvider(client).client.configuration, client.configuration)
        self.assertIs(M18SharedPlanProvider(client).client.configuration, client.configuration)

    def test_no_suite_dependency(self):
        import inspect
        import src.evaluation.m18_shared_provider as module
        source = inspect.getsource(module)
        self.assertNotIn("m18/suites", source); self.assertNotIn("held_out", source)


if __name__ == "__main__": unittest.main()
