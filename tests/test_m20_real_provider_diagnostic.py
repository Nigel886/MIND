import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m20_harness import M20Condition, M20IntegrityError, M20LifecycleState, M20Namespace
from src.evaluation.m20_real_provider_diagnostic import (
    M20DiagnosticWorkItem, M20FakeDiagnosticTransport,
    M20_REAL_PROVIDER_DIAGNOSTIC_PROTOCOL, M20_RESPONSE_TELEMETRY_SCHEMA,
    M20RealProviderDiagnosticRunner, build_diagnostic_protocol,
)


def response(value):
    return {"model": "deepseek-flash", "choices": [{"message": {"content": json.dumps(value)}}]}


class M20RealProviderDiagnosticTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
