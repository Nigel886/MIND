"""Independent offline authorization checks for the frozen M20 diagnostic v4."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m20_harness import M20EvidenceStore, M20ProviderAttemptError
from src.evaluation.m20_real_provider_diagnostic import (
    M20_DIAGNOSTIC_GENERATION_V4,
    M20FakeDiagnosticTransport,
    M20LiveDiagnosticTransport,
    M20RealProviderDiagnosticRunner,
    expected_live_authorization_artifact,
    load_live_authorization_artifact,
)


def response() -> dict[str, object]:
    return {"model": "deepseek-flash", "choices": [{"message": {"content": '{"kind":"answer","payload":"wrong"}'}}]}


class M20DiagnosticV4AuthorizationTest(unittest.TestCase):
    def test_tracked_artifact_and_live_gate_are_exact_and_fail_closed(self):
        runner = M20RealProviderDiagnosticRunner(generation=M20_DIAGNOSTIC_GENERATION_V4)
        artifact = Path("docs/evaluation/M20-DiagnosticV4-Authorization-Artifact.json")
        self.assertEqual(json.loads(artifact.read_text(encoding="utf-8")),
                         expected_live_authorization_artifact(M20_DIAGNOSTIC_GENERATION_V4))
        self.assertEqual(load_live_authorization_artifact(artifact, M20_DIAGNOSTIC_GENERATION_V4)["namespace"],
                         "m20_real_provider_diagnostic_v4")

        calls: list[object] = []
        live = M20LiveDiagnosticTransport(lambda *args: calls.append(args) or response(), True)
        with TemporaryDirectory() as directory:
            root = Path(directory); store = runner.store(root / "records")
            with self.assertRaises(PermissionError):
                runner.run_live(runner.work_items()[0], live, store, root / "missing.json")
            self.assertEqual(calls, [])
            temporary = root / "authorization.json"
            temporary.write_text(json.dumps(expected_live_authorization_artifact(M20_DIAGNOSTIC_GENERATION_V4)), encoding="utf-8")
            record = runner.run_live(runner.work_items()[0], live, store, temporary)
            self.assertEqual((len(calls), record.spec.execution_id), (1, runner.work_items()[0].work_id))

    def test_fake_live_retry_chains_and_integrity_matrix(self):
        runner = M20RealProviderDiagnosticRunner(generation=M20_DIAGNOSTIC_GENERATION_V4)

        def exercise(retries: int):
            calls = 0
            def transport(*_):
                nonlocal calls
                calls += 1
                if calls <= retries:
                    raise M20ProviderAttemptError("transport", True)
                return response()
            with TemporaryDirectory() as directory:
                root = Path(directory); artifact = root / "authorization.json"
                artifact.write_text(json.dumps(expected_live_authorization_artifact(M20_DIAGNOSTIC_GENERATION_V4)), encoding="utf-8")
                record = runner.run_live(runner.work_items()[1], M20LiveDiagnosticTransport(transport, True),
                                         runner.store(root / "records"), artifact)
                persisted = runner.store(root / "records").records()[0]
                return record, persisted

        for retries, expected in ((1, [0, 1]), (2, [0, 1, 2])):
            record, persisted = exercise(retries)
            attempts = persisted["telemetry"]["retries"]
            self.assertEqual((record.telemetry.provider_interactions, len(attempts)), (1, retries + 1))
            self.assertEqual([item["retry_index"] for item in attempts], expected)
            self.assertEqual(len({item["logical_operation_id"] for item in attempts}), 1)
            self.assertEqual(len({item["physical_attempt_id"] for item in attempts}), retries + 1)
            self.assertEqual({item["owner"] for item in attempts}, {"provider_client"})

        _, baseline = exercise(1)
        mutations = (
            lambda value: value["telemetry"]["retries"][1].__setitem__("logical_operation_id", "wrong"),
            lambda value: value["telemetry"]["retries"][1].__setitem__("retry_index", 0),
            lambda value: value["telemetry"].__setitem__("retries", list(reversed(value["telemetry"]["retries"]))),
            lambda value: value["telemetry"]["retries"][1].__setitem__("physical_attempt_id", value["telemetry"]["retries"][0]["physical_attempt_id"]),
            lambda value: value["telemetry"].__setitem__("provider_interactions", 2),
            lambda value: value["telemetry"].__setitem__("provider_interactions", 0),
            lambda value: value["telemetry"]["retries"][1].__setitem__("owner", "caller"),
            lambda value: value["telemetry"].__setitem__("provider_transport_attempts", 1),
        )
        for mutate in mutations:
            invalid = deepcopy(baseline); mutate(invalid)
            with self.assertRaises(Exception):
                M20EvidenceStore.validate_persisted(invalid)


if __name__ == "__main__":
    unittest.main()
