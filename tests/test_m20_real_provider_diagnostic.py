import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m20_harness import (
    M20Condition, M20IntegrityError, M20LifecycleState, M20Namespace,
    M20ProviderAttemptError,
)
from src.evaluation.m20_real_provider_diagnostic import (
    M20DiagnosticWorkItem, M20FakeDiagnosticTransport,
    M20_DIAGNOSTIC_GENERATION_V2, M20_DIAGNOSTIC_GENERATION_V3, M20_DIAGNOSTIC_GENERATION_V4,
    M20LiveDiagnosticTransport,
    M20_REAL_PROVIDER_DIAGNOSTIC_PROTOCOL, M20_RESPONSE_TELEMETRY_SCHEMA,
    M20RealProviderDiagnosticRunner, build_diagnostic_protocol,
    build_post_envelope_diagnostic_protocol, build_post_envelope_v3_diagnostic_protocol,
    build_post_envelope_v4_diagnostic_protocol,
    expected_live_authorization_artifact,
)


def response(value):
    return {"model": "deepseek-flash", "choices": [{"message": {"content": json.dumps(value)}}]}


class M20RealProviderDiagnosticTest(unittest.TestCase):
    def test_v4_is_a_new_isolated_generation_with_shared_retry_persistence(self):
        v1 = M20RealProviderDiagnosticRunner()
        v2 = M20RealProviderDiagnosticRunner(generation=M20_DIAGNOSTIC_GENERATION_V2)
        v3 = M20RealProviderDiagnosticRunner(generation=M20_DIAGNOSTIC_GENERATION_V3)
        v4 = M20RealProviderDiagnosticRunner(generation=M20_DIAGNOSTIC_GENERATION_V4)
        generations = (v1, v2, v3, v4)
        self.assertEqual(v4.protocol["protocol"], "m20_real_provider_diagnostic_v4")
        self.assertEqual(v4.protocol["namespace"], "m20_real_provider_diagnostic_v4")
        self.assertEqual(v4.protocol["result_path"], "evaluation/results/m20_real_provider_diagnostic_v4")
        self.assertEqual(v4.protocol, build_post_envelope_v4_diagnostic_protocol())
        self.assertEqual(len(v4.work_items()), 2)
        self.assertEqual({item.spec.condition for item in v4.work_items()},
                         {M20Condition.MIND_ADAPTIVE, M20Condition.MIND_FIXED})
        self.assertEqual({item.spec.namespace for item in v4.work_items()}, {M20Namespace.DIAGNOSTIC_V4})
        self.assertEqual({item.spec.repetition for item in v4.work_items()}, {1})
        v4_ids = {item.work_id for item in v4.work_items()}
        self.assertEqual(len(v4_ids), 2)
        for runner in (v1, v2, v3):
            self.assertTrue(v4_ids.isdisjoint(item.work_id for item in runner.work_items()))
            self.assertNotEqual(v4.protocol["digest"], runner.protocol["digest"])

        artifacts = [expected_live_authorization_artifact(runner.generation) for runner in generations]
        with TemporaryDirectory() as directory:
            root, store = Path(directory), v4.store(Path(directory) / "v4")
            fake = M20FakeDiagnosticTransport(lambda *_: response({"kind": "answer", "payload": "wrong"}))
            for runner in (v1, v2, v3):
                with self.assertRaises(ValueError):
                    v4.run_fake(runner.work_items()[0], fake, store)
                with self.assertRaises(ValueError):
                    runner.run_fake(v4.work_items()[0], fake, runner.store(root / runner.generation.protocol))
            artifact = root / "authorization.json"
            live = M20LiveDiagnosticTransport(lambda *_: response({"kind": "answer", "payload": "wrong"}), True)
            for stale in artifacts[:-1]:
                artifact.write_text(json.dumps(stale), encoding="utf-8")
                with self.assertRaises(PermissionError):
                    v4.run_live(v4.work_items()[0], live, store, artifact)

        for field, value in (("digest", "0" * 64),
                             ("result_path", "evaluation/results/m20_real_provider_diagnostic_v3")):
            invalid = build_post_envelope_v4_diagnostic_protocol(); invalid[field] = value
            with self.assertRaises(ValueError):
                M20RealProviderDiagnosticRunner(invalid, M20_DIAGNOSTIC_GENERATION_V4)

        class RetryOnce:
            def __init__(self): self.calls = 0
            def __call__(self, *_):
                self.calls += 1
                if self.calls == 1:
                    raise M20ProviderAttemptError("transport", True)
                return {"id": "metadata-only", **response({"kind": "answer", "payload": "wrong"})}

        with TemporaryDirectory() as directory:
            retry, store = RetryOnce(), v4.store(Path(directory) / "v4-retry")
            record = v4.run_fake(v4.work_items()[1], M20FakeDiagnosticTransport(retry), store)
            persisted = store.records()[0]
            attempts = persisted["telemetry"]["retries"]
            self.assertEqual((record.telemetry.provider_interactions, record.telemetry.provider_transport_attempts), (1, 2))
            self.assertEqual([attempt["retry_index"] for attempt in attempts], [0, 1])
            self.assertEqual(len({attempt["logical_operation_id"] for attempt in attempts}), 1)
            self.assertEqual(len({attempt["physical_attempt_id"] for attempt in attempts}), 2)
            self.assertEqual({attempt["owner"] for attempt in attempts}, {"provider_client"})
            self.assertTrue(persisted["telemetry"]["response_diagnostics"][0]["admitted_proposal"])

    def test_v3_namespace_binding_supersedes_blocked_v2_without_mutation(self):
        v1 = M20RealProviderDiagnosticRunner()
        v2 = M20RealProviderDiagnosticRunner(generation=M20_DIAGNOSTIC_GENERATION_V2)
        v3 = M20RealProviderDiagnosticRunner(generation=M20_DIAGNOSTIC_GENERATION_V3)
        self.assertEqual([item.work_id for item in v2.work_items()], [
            "716f81a7fed568252a48c1dce7ce42a7fd0a33872e6a6b25ba9390881766535c",
            "1524725c41d33657fca0b136a56cd516e1861494c1c01d33438e6b80e8f26e27",
        ])
        self.assertEqual(v3.protocol["protocol"], "m20_real_provider_diagnostic_v3")
        self.assertEqual(v3.protocol["namespace"], "m20_real_provider_diagnostic_v3")
        self.assertEqual(v3.protocol["result_path"], "evaluation/results/m20_real_provider_diagnostic_v3")
        self.assertNotEqual(v3.protocol["digest"], v2.protocol["digest"])
        self.assertTrue({item.work_id for item in v3.work_items()}.isdisjoint(
            item.work_id for item in v2.work_items()))
        self.assertNotEqual(build_post_envelope_v3_diagnostic_protocol()["digest"],
                            build_post_envelope_diagnostic_protocol()["digest"])
        v2_artifact = expected_live_authorization_artifact(M20_DIAGNOSTIC_GENERATION_V2)
        v3_artifact = expected_live_authorization_artifact(M20_DIAGNOSTIC_GENERATION_V3)
        self.assertEqual(v3_artifact["namespace"], "m20_real_provider_diagnostic_v3")
        self.assertNotEqual(v2_artifact, v3_artifact)
        fake = M20FakeDiagnosticTransport(lambda *_: response({"kind": "answer", "payload": "wrong"}))
        with TemporaryDirectory() as directory:
            root, store = Path(directory), v3.store(Path(directory) / "v3")
            with self.assertRaises(ValueError):
                v3.run_fake(v1.work_items()[0], fake, store)
            with self.assertRaises(ValueError):
                v3.run_fake(v2.work_items()[0], fake, store)
            with self.assertRaises(ValueError):
                v1.run_fake(v3.work_items()[0], fake, v1.store(root / "v1"))
            with self.assertRaises(ValueError):
                v2.run_fake(v3.work_items()[0], fake, v2.store(root / "v2"))
            artifact = root / "authorization.json"
            artifact.write_text(json.dumps(v2_artifact), encoding="utf-8")
            live = M20LiveDiagnosticTransport(lambda *_: response({"kind": "answer", "payload": "wrong"}), True)
            with self.assertRaises(PermissionError):
                v3.run_live(v3.work_items()[0], live, store, artifact)
            artifact.write_text(json.dumps(v3_artifact), encoding="utf-8")
            record = v3.run_live(v3.work_items()[0], live, store, artifact)
            self.assertEqual(record.spec.namespace, M20Namespace.DIAGNOSTIC_V3)
            self.assertTrue(record.telemetry.response_diagnostics[0]["admitted_proposal"])

    def test_post_envelope_generation_is_distinct_and_fail_closed(self):
        v1 = M20RealProviderDiagnosticRunner()
        v2 = M20RealProviderDiagnosticRunner(generation=M20_DIAGNOSTIC_GENERATION_V2)
        v1_items, v2_items = v1.work_items(), v2.work_items()
        self.assertEqual(len(v2_items), 2)
        self.assertEqual({item.spec.condition for item in v2_items},
                         {M20Condition.MIND_ADAPTIVE, M20Condition.MIND_FIXED})
        self.assertEqual(v2.protocol["protocol"], "m20_real_provider_diagnostic_v2")
        self.assertEqual(v2.protocol["result_path"], "evaluation/results/m20_real_provider_diagnostic_v2")
        self.assertTrue({item.work_id for item in v1_items}.isdisjoint(item.work_id for item in v2_items))
        self.assertEqual(v2_items[0].spec.case_id, "m20.real.multi_step_stateful.01")
        self.assertEqual(v2_items[0].spec.payload_digest,
                         "b977a2170893e1c1cfc7d7571e275df3f47d95259b29415e2d1bdea1202069be")
        self.assertNotEqual(build_diagnostic_protocol()["digest"],
                            build_post_envelope_diagnostic_protocol()["digest"])
        fake = M20FakeDiagnosticTransport(lambda *_: response({"kind": "answer", "payload": "wrong"}))
        with TemporaryDirectory() as directory:
            root, store = Path(directory), v2.store(Path(directory) / "v2")
            with self.assertRaises(ValueError):
                v2.run_fake(v1_items[0], fake, store)
            with self.assertRaises(ValueError):
                v1.run_fake(v2_items[0], fake, v1.store(root / "v1"))
            record = v2.run_fake(v2_items[0], fake, store)
            self.assertEqual(v2.run_fake(v2_items[0], fake, store).digest, record.digest)
            self.assertEqual(record.provenance["diagnostic_protocol"], "m20_real_provider_diagnostic_v2")
            self.assertTrue(record.telemetry.response_diagnostics[0]["admitted_proposal"])
            self.assertEqual(v2.namespace_accounting(store),
                             {"diagnostic": 1, "pilot": 0, "calibration": 0, "formal": 0})
            artifact = root / "authorization.json"
            artifact.write_text(json.dumps(expected_live_authorization_artifact()), encoding="utf-8")
            live = M20LiveDiagnosticTransport(lambda *_: response({"kind": "answer", "payload": "wrong"}), True)
            with self.assertRaises(PermissionError):
                v2.run_live(v2_items[1], live, store, artifact)
            artifact.write_text(json.dumps(expected_live_authorization_artifact(M20_DIAGNOSTIC_GENERATION_V2)), encoding="utf-8")
            self.assertTrue(v2.run_live(v2_items[1], live, store, artifact).telemetry.response_diagnostics[0]["admitted_proposal"])
        for field, value in (("case_id", "other"), ("payload_digest", "0" * 64),
                             ("conditions", [M20Condition.MIND_ADAPTIVE.value]),
                             ("repetition", 2), ("provider_hash", "0" * 64),
                             ("resource_ceiling_identity", "wrong"),
                             ("telemetry_schema", "wrong"), ("protocol", "wrong")):
            protocol = build_post_envelope_diagnostic_protocol(); protocol[field] = value
            with self.assertRaises(ValueError):
                M20RealProviderDiagnosticRunner(protocol, M20_DIAGNOSTIC_GENERATION_V2)

    def test_exact_two_work_items_and_fail_closed_protocol_identity(self):
        runner = M20RealProviderDiagnosticRunner()
        items = runner.work_items()
        self.assertEqual(len(items), 2)
        self.assertEqual({item.spec.namespace for item in items}, {M20Namespace.DIAGNOSTIC})
        self.assertEqual({item.spec.repetition for item in items}, {1})
        self.assertEqual({item.spec.condition.value for item in items},
                         {"m20_mind_adaptive_v1", "m20_mind_fixed_v1"})
        self.assertEqual(items[0].spec.case_id, "m20.real.multi_step_stateful.01")
        for field, bad in (("case_id", "other"), ("payload_digest", "0" * 64),
                           ("provider_hash", "0" * 64), ("resource_ceiling_identity", "wrong"),
                           ("case_source", "wrong"), ("telemetry_schema", "wrong"),
                           ("protocol", "wrong")):
            protocol = build_diagnostic_protocol(); protocol[field] = bad
            with self.assertRaises(ValueError):
                M20RealProviderDiagnosticRunner(protocol)

    def test_fake_persistence_idempotence_and_partial_safety(self):
        runner, item, calls = M20RealProviderDiagnosticRunner(), M20RealProviderDiagnosticRunner().work_items()[0], []
        fake = M20FakeDiagnosticTransport(lambda body, timeout: calls.append((body, timeout)) or response({"kind": "answer", "payload": "wrong"}))
        with TemporaryDirectory() as directory:
            store = runner.store(Path(directory))
            record = runner.run_fake(item, fake, store)
            again = runner.run_fake(item, fake, store)
            self.assertEqual(record.digest, again.digest)
            self.assertEqual(len(calls), 1)
            self.assertEqual(store.namespace, M20Namespace.DIAGNOSTIC)
            persisted = store.records()[0]
            self.assertEqual(persisted["provenance"]["diagnostic_protocol"], M20_REAL_PROVIDER_DIAGNOSTIC_PROTOCOL)
            self.assertEqual(persisted["provenance"]["response_telemetry_schema"], M20_RESPONSE_TELEMETRY_SCHEMA)
            self.assertEqual(M20RealProviderDiagnosticRunner.namespace_accounting(store),
                             {"diagnostic": 1, "pilot": 0, "calibration": 0, "formal": 0})
        with TemporaryDirectory() as directory:
            store = runner.store(Path(directory))
            with self.assertRaises(InterruptedError):
                runner.run_fake(item, fake, store, interrupt_before_execution=True)
            self.assertEqual(store.lifecycle(item.spec), M20LifecycleState.ZERO_COMMIT_PARTIAL)
            runner.run_fake(item, fake, store)
            self.assertEqual(len(store.records()), 1)

    def test_actual_parser_telemetry_and_private_redaction(self):
        runner = M20RealProviderDiagnosticRunner()
        adaptive, fixed = runner.work_items()
        cases = ((adaptive, {"kind": "act", "action_id": "advance"}, None),
                 (fixed, {"kind": "answer", "payload": "wrong"}, None),
                 (fixed, "not-json", "NON_JSON_RESPONSE"),
                 (fixed, {"kind": "answer"}, "MISSING_REQUIRED_FIELD"),
                 (fixed, {"kind": "act", "action_id": "not-known"}, "UNKNOWN_ACTION_ID"),
                 (fixed, {"kind": "act", "action_id": "advance"}, "ACTION_NOT_LEGAL_IN_PUBLIC_STATE"))
        for item, value, category in cases:
            with TemporaryDirectory() as directory:
                store = runner.store(Path(directory))
                if category == "ACTION_NOT_LEGAL_IN_PUBLIC_STATE":
                    # The real selected case admits advance. A caller-created reduced
                    # public contract is rejected before it can become diagnostic work.
                    altered = replace(item.spec, condition=item.spec.condition, repetition=2)
                    with self.assertRaises(ValueError):
                        runner.run_fake(M20DiagnosticWorkItem(item.protocol_digest, altered),
                                        M20FakeDiagnosticTransport(lambda *_: response(value)), store)
                    continue
                payload = value if isinstance(value, str) else json.dumps(value)
                record = runner.run_fake(item, M20FakeDiagnosticTransport(
                    lambda *_args, content=payload: {"model": "deepseek-flash", "choices": [{"message": {"content": content}}]}), store)
                diagnostics = record.telemetry.response_diagnostics
                self.assertTrue(diagnostics)
                if category is None:
                    self.assertTrue(diagnostics[0]["admitted_proposal"])
                else:
                    self.assertEqual(diagnostics[-1]["rejection_category"], category)
        secret = "DEEPSEEK_API_KEY_CANARY"
        with TemporaryDirectory() as directory:
            store = runner.store(Path(directory))
            record = runner.run_fake(fixed, M20FakeDiagnosticTransport(
                lambda *_: response({"kind": "unknown", "x": secret})), store)
            serialized = json.dumps(record.canonical(), sort_keys=True)
            self.assertNotIn(secret, serialized)
            self.assertNotIn("reference_witness", serialized)

    def test_corruption_and_caller_added_work_fail_closed(self):
        runner, item = M20RealProviderDiagnosticRunner(), M20RealProviderDiagnosticRunner().work_items()[1]
        fake = M20FakeDiagnosticTransport(lambda *_: response({"kind": "answer", "payload": "wrong"}))
        with TemporaryDirectory() as directory:
            store = runner.store(Path(directory))
            runner.run_fake(item, fake, store)
            path = next(Path(directory).glob("*.json"))
            if path.name == "manifest.json": path = next(p for p in Path(directory).glob("*.json") if p.name != "manifest.json")
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(M20IntegrityError): runner.run_fake(item, fake, store)
        altered = M20DiagnosticWorkItem(item.protocol_digest, replace(item.spec, repetition=2))
        with TemporaryDirectory() as directory:
            with self.assertRaises(ValueError): runner.run_fake(altered, fake, runner.store(Path(directory)))
        for field, value in (("case_id", "other"), ("payload_digest", "0" * 64),
                             ("condition", M20Condition.DIRECT), ("provider_hash", "0" * 64),
                             ("resource_ceiling_identity", "wrong")):
            bad_spec = replace(item.spec, **{field: value})
            bad_item = M20DiagnosticWorkItem(item.protocol_digest, bad_spec)
            with TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    runner.run_fake(bad_item, fake, runner.store(Path(directory)))

    def test_live_transport_requires_future_artifact_and_admits_only_typed_boundary(self):
        runner, item, calls = M20RealProviderDiagnosticRunner(), M20RealProviderDiagnosticRunner().work_items()[1], []
        live = M20LiveDiagnosticTransport(
            lambda body, timeout: calls.append((body, timeout)) or response({"kind": "answer", "payload": "wrong"}), True)
        with TemporaryDirectory() as directory:
            root = Path(directory); store = runner.store(root / "diagnostic")
            artifact = root / "authorization.json"
            with self.assertRaises(PermissionError): runner.run_live(item, live, store, artifact)
            artifact.write_text("{}", encoding="utf-8")
            with self.assertRaises(PermissionError): runner.run_live(item, live, store, artifact)
            artifact.write_text(json.dumps(expected_live_authorization_artifact()), encoding="utf-8")
            with self.assertRaises(PermissionError): runner.run_live(item, M20LiveDiagnosticTransport(live.responder, False), store, artifact)
            with self.assertRaises(PermissionError): runner.run_live(item, lambda *_: {}, store, artifact)
            altered = M20DiagnosticWorkItem(item.protocol_digest, replace(item.spec, repetition=2))
            with self.assertRaises(ValueError): runner.run_live(altered, live, store, artifact)
            record = runner.run_live(item, live, store, artifact)
            self.assertEqual(len(calls), 1)
            self.assertTrue(record.telemetry.response_diagnostics[0]["admitted_proposal"])


if __name__ == "__main__":
    unittest.main()
