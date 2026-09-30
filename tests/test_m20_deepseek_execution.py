import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m20_deepseek_execution import (M20DeepSeekCalibrationRunner,
    M20DeepSeekProposalAdapter, M20ResponseRejection)
from src.evaluation.m20_harness import M20EvidenceStore, M20Namespace, M20ProviderAttemptError


def response(value):
    return {"model": "deepseek-flash", "choices": [{"message": {"content": json.dumps(value)}}]}


def raw_response(content):
    return {"model": "deepseek-flash", "choices": [{"message": {"content": content}}]}


class M20DeepSeekExecutionTest(unittest.TestCase):
    def test_public_request_and_structured_parser_fail_closed(self):
        seen = []
        adapter = M20DeepSeekProposalAdapter(lambda body, timeout: seen.append((body, timeout)) or response({"kind": "act", "action_id": "advance"}))
        case = M20DeepSeekCalibrationRunner().manifest.cases[0]
        proposal = adapter.propose(case.public, {"progress": 0, "required_progress": "CANARY_SUCCESS",
                                                  "requires_observation": "CANARY_TARGET",
                                                  "private_witness": "CANARY_WITNESS", "future_state": "CANARY_FUTURE"})
        self.assertEqual(proposal.action_id, "advance")
        wire = json.dumps(seen[0][0], sort_keys=True)
        self.assertNotIn(case.private.target, wire); self.assertNotIn("reference_witness", wire)
        for forbidden in ("required_progress", "requires_observation", "requires_recovery", "private_witness",
                          "future_state", "CANARY_SUCCESS", "CANARY_TARGET", "CANARY_WITNESS", "CANARY_FUTURE"):
            self.assertNotIn(forbidden, wire)
        self.assertEqual(json.loads(seen[0][0]["messages"][1]["content"].split("Public input: ", 1)[1])["state"], {"progress": 0})
        self.assertEqual(seen[0][1], 60)
        for invalid in ({"kind": "act", "action_id": "not_legal"}, {"kind": "answer", "extra": 1}, {"kind": "unknown", "x": 1}):
            with self.assertRaises(M20ProviderAttemptError):
                M20DeepSeekProposalAdapter(lambda *_: response(invalid)).propose(case.public, {})

    def test_manifest_bound_dry_run_and_rejections(self):
        runner = M20DeepSeekCalibrationRunner()
        self.assertEqual(runner.dry_run(), {"pairs": 60, "executions": 120, "duplicates": 0, "missing": 0})
        wrong = dict(runner.frozen); wrong["provider_hash"] = "0" * 64
        with self.assertRaises(ValueError): M20DeepSeekCalibrationRunner(wrong)

    def test_response_shape_taxonomy_is_structural_and_fail_closed(self):
        case = M20DeepSeekCalibrationRunner().manifest.cases[0]
        matrix = (
            ("", M20ResponseRejection.EMPTY_RESPONSE),
            ("not-json", M20ResponseRejection.NON_JSON_RESPONSE),
            ("[]", M20ResponseRejection.JSON_TOP_LEVEL_TYPE_INVALID),
            ("{}", M20ResponseRejection.MISSING_REQUIRED_FIELD),
            ('{"kind":"unknown"}', M20ResponseRejection.UNKNOWN_RESPONSE_KIND),
            ('{"kind":"act","action_id":"not-legal"}', M20ResponseRejection.ACTION_NOT_LEGAL_IN_PUBLIC_STATE),
            ('{"kind":"act","action_id":1}', M20ResponseRejection.ACTION_PAYLOAD_INVALID),
            ('{"kind":"answer","payload":"x","extra":1}', M20ResponseRejection.ANSWER_PAYLOAD_INVALID),
        )
        for content, category in matrix:
            adapter = M20DeepSeekProposalAdapter(lambda *_args, value=content: raw_response(value))
            with self.assertRaises(M20ProviderAttemptError) as raised:
                adapter.propose(case.public, {})
            self.assertEqual(raised.exception.reason, category.value)
            self.assertEqual(adapter.last_diagnostic["rejection_category"], category.value)
        secret = "CANARY_RESPONSE_SECRET"
        adapter = M20DeepSeekProposalAdapter(
            lambda *_args: response({"kind": "unknown", "x": secret}))
        with self.assertRaises(M20ProviderAttemptError):
            adapter.propose(case.public, {})
        self.assertNotIn(secret, json.dumps(adapter.last_diagnostic, sort_keys=True))
        for value in ({"kind": "act", "action_id": "advance"}, {"kind": "answer", "payload": "wrong"}):
            adapter = M20DeepSeekProposalAdapter(lambda *_args, result=value: response(result))
            self.assertTrue(adapter.propose(case.public, {}).kind)
            self.assertTrue(adapter.last_diagnostic["admitted_proposal"])

    def test_fake_e2e_retry_persistence_and_reinvocation(self):
        runner, item = M20DeepSeekCalibrationRunner(), M20DeepSeekCalibrationRunner().work_items()[0]
        calls = []
        def fake(body, _timeout):
            calls.append(body)
            if len(calls) == 1: raise TimeoutError("fake")
            return response({"kind": "answer", "payload": "wrong"})
        with TemporaryDirectory() as directory:
            store = M20EvidenceStore(Path(directory), runner.manifest, M20Namespace.CALIBRATION)
            adaptive, fixed = runner.run_work_item(item, fake, store)
            self.assertEqual((adaptive.spec.pair_id, fixed.spec.pair_id), (item.pair_id, item.pair_id))
            self.assertEqual((adaptive.telemetry.provider_interactions, adaptive.telemetry.provider_transport_attempts), (1, 2))
            self.assertEqual(len(adaptive.telemetry.response_diagnostics), 2)
            self.assertEqual(adaptive.telemetry.response_diagnostics[0]["rejection_category"], "PROVIDER_TRANSPORT_FAILURE")
            self.assertTrue(adaptive.telemetry.response_diagnostics[1]["admitted_proposal"])
            self.assertEqual(len(store.records()), 2)
            again = runner.run_work_item(item, fake, store)
            self.assertEqual((again[0].digest, again[1].digest), (adaptive.digest, fixed.digest))
            reconstructed = M20EvidenceStore.reconstruct_pair(store.records())
            self.assertEqual(reconstructed["pair_id"], item.pair_id)
            self.assertIn("protocol", M20EvidenceStore.statistical_input(store.records()[0])["provenance"])

    def test_adaptive_and_fixed_share_isolated_schema(self):
        runner, item, requests = M20DeepSeekCalibrationRunner(), M20DeepSeekCalibrationRunner().work_items()[0], []
        def fake(body, _timeout):
            requests.append(body)
            return response({"kind": "answer", "payload": "wrong"})
        with TemporaryDirectory() as directory:
            runner.run_work_item(item, fake, M20EvidenceStore(Path(directory), runner.manifest, M20Namespace.CALIBRATION))
        self.assertEqual(len(requests), 2)
        public_inputs = [json.loads(body["messages"][1]["content"].split("Public input: ", 1)[1]) for body in requests]
        self.assertEqual(public_inputs[0], public_inputs[1])
        for value in public_inputs:
            self.assertEqual(set(value), {"task", "actions", "state"})
            self.assertTrue(set(value["state"]).issubset({"progress", "observed", "recovered", "resource_note"}))


if __name__ == "__main__":
    unittest.main()
