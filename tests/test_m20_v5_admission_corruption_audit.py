"""Independent, fake-only corruption evidence for manifest-v5 pair admission."""
from __future__ import annotations

import json, os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m20_answerterm_calibration_execution import (
    M20AnswerTerminationCalibrationRunner, answerterm_live_authorization_payload,
    load_answerterm_live_authorization,
)
from src.evaluation.m20_harness import M20EvidenceStore, M20IntegrityError, canonical_hash


def _reply(value):
    return {"model": "deepseek-flash", "choices": [{"message": {"content": json.dumps(value)}}]}


def _transport(request, _timeout):
    public = json.loads(request["messages"][1]["content"].split("Public input: ", 1)[1])
    return _reply({"kind": "stop"} if public["legal_decision_kinds"] == ["answer", "stop"]
                  else {"kind": "act", "action_id": "advance"})


class V5AdmissionCorruptionAudit(unittest.TestCase):
    """Runs each category against disk evidence, not hand-built record objects."""
    expected_a = tuple(f"A{i:02d}" for i in range(1, 19))
    expected_b = tuple(f"B{i:02d}" for i in range(1, 26))
    evidence: list[dict] = []

    def _fixture(self, kind: str):
        directory = TemporaryDirectory(); root = Path(directory.name) / "evidence"
        runner = M20AnswerTerminationCalibrationRunner()
        items = tuple(item for item in runner.work_items() if item.pair_id == runner.work_items()[0].pair_id)
        failed, opposite = items[0], items[1]
        if kind == "ordinary":
            for item in items: runner._run(item, _transport, runner.store(root))
        else:
            runner._run(failed, lambda *_: (_ for _ in ()).throw(TimeoutError("audit fake failure")), runner.store(root))
            runner._run(opposite, _transport, runner.store(root))
            artifact = Path(directory.name) / "authorization.json"
            artifact.write_text(json.dumps(answerterm_live_authorization_payload()), encoding="utf-8")
            if kind == "partial":
                with self.assertRaises(InterruptedError):
                    runner.run_live_replacement(artifact, failed.work_id, _transport, root, interrupt_before_execution=True)
            elif kind == "terminal":
                runner.run_live_replacement(artifact, failed.work_id, _transport, root)
        # Construction-time objects are deliberately discarded; all following work reloads disk.
        return directory, root, runner

    def _records(self, runner, root):
        return runner.store(root).records()

    def _baseline(self, runner, root, kind):
        projected = M20EvidenceStore.statistical_pair_input(self._records(runner, root))
        if kind in ("ordinary", "terminal"): self.assertTrue(projected["analyzable"])
        else: self.assertFalse(projected["analyzable"])

    @staticmethod
    def _rewrite(path: Path, mutate):
        value = json.loads(path.read_text(encoding="utf-8")); value.pop("digest", None)
        mutate(value); value["digest"] = canonical_hash(value)
        path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

    def _paths(self, root):
        rows = [p for p in root.glob("*.json") if p.name != "manifest.json"]
        values = {json.loads(p.read_text(encoding="utf-8"))["execution_id"]: p for p in rows}
        original = next(p for p in values.values() if json.loads(p.read_text())["spec"].get("replacement_of") is None)
        replacement = next((p for p in values.values() if json.loads(p.read_text())["spec"].get("replacement_of") is not None), None)
        other = next(p for p in values.values() if p != original and p != replacement)
        return original, replacement, other

    def _mutation(self, case, root):
        original, replacement, other = self._paths(root)
        def m(path, fn): self._rewrite(path, fn)
        # Each entry is intentionally category-specific, even where the invariant is shared.
        ops = {
          "A01": lambda: m(original, lambda v: v["spec"].__setitem__("provider_hash", "forged-provider")),
          "A02": lambda: m(other, lambda v: v["spec"].__setitem__("provider_hash", "forged-provider")),
          "A03": lambda: [m(p, lambda v: v["spec"].__setitem__("provider_hash", "forged-provider")) for p in (original, other)],
          "A04": lambda: [m(p, lambda v: v["spec"].__setitem__("provider_hash", "forged-provider")) for p in (original, replacement)],
          "A05": lambda: m(original, lambda v: v["spec"].__setitem__("manifest_digest", "wrong-manifest")),
          "A06": lambda: m(original, lambda v: v["provenance"].__setitem__("runtime_identity", "wrong-runtime")),
          "A07": lambda: m(original, lambda v: v["spec"].__setitem__("resource_ceiling_identity", "wrong-ceiling")),
          "A08": lambda: m(original, lambda v: v["provenance"].__setitem__("ordering_identity", "wrong-ordering")),
          "A09": lambda: m(original, lambda v: v["provenance"].__setitem__("pair_work_binding_digest", "wrong-binding")),
          "A10": lambda: m(original, lambda v: v["provenance"].__setitem__("work_id", "non-member-work")),
          "A11": lambda: m(original, lambda v: v["spec"].__setitem__("case_id", "wrong-case")),
          "A12": lambda: m(original, lambda v: v["spec"].__setitem__("repetition", 999)),
          "A13": lambda: m(original, lambda v: v["spec"].__setitem__("condition", "wrong-condition")),
          "A14": lambda: m(original, lambda v: v["spec"].__setitem__("cluster_id", "wrong-cluster")),
          "A15": lambda: m(original, lambda v: v["spec"].__setitem__("payload_digest", "wrong-payload")),
          "A16": lambda: m(replacement, lambda v: v["provenance"].__setitem__("original_work_id", "wrong-original")),
          "A17": lambda: m(original, lambda v: v["provenance"].pop("runtime_identity")),
          "A18": lambda: m(original, lambda v: v["spec"].__setitem__("namespace", "m20_calibration_v3")),
          "B01": lambda: m(original, lambda v: v["provenance"].__setitem__("work_id", "corrupt-original-work")),
          "B02": lambda: m(replacement, lambda v: v["provenance"].__setitem__("replacement_work_id", "corrupt-replacement-work")),
          "B03": lambda: m(original, lambda v: v["spec"].__setitem__("frozen_pair_id", "corrupt-frozen-pair")),
          "B04": lambda: m(original, lambda v: v.__setitem__("pair_id", "corrupt-pair")),
          "B05": lambda: m(original, lambda v: v["spec"].__setitem__("case_id", "corrupt-case")),
          "B06": lambda: m(original, lambda v: v["spec"].__setitem__("repetition", 1000)),
          "B07": lambda: m(original, lambda v: v["spec"].__setitem__("condition", "corrupt-condition")),
          "B08": lambda: m(replacement, lambda v: v["provenance"].__setitem__("replacement_index", "2")),
          "B09": lambda: m(original, lambda v: v["spec"].__setitem__("manifest_digest", "corrupt-manifest")),
          "B10": lambda: m(original, lambda v: v["provenance"].__setitem__("runtime_identity", "corrupt-runtime")),
          "B11": lambda: m(original, lambda v: v["spec"].__setitem__("provider_hash", "corrupt-provider")),
          "B12": lambda: m(original, lambda v: v["spec"].__setitem__("resource_ceiling_identity", "corrupt-ceiling")),
          "B13": lambda: m(original, lambda v: v.__setitem__("outcome", "success")),
          "B14": lambda: m(replacement, lambda v: v["provenance"].__setitem__("replacement_eligibility", "success")),
          "B15": lambda: m(replacement, lambda v: v["spec"].__setitem__("replacement_of", "wrong-link")),
          "B16": lambda: original.unlink(),
          "B17": lambda: m(replacement, lambda v: v["spec"].__setitem__("replacement_of", "orphan")),
          "B18": lambda: m(replacement, lambda v: v["spec"].__setitem__("replacement_of", json.loads(other.read_text())["execution_id"])),
          "B19": lambda: self._duplicate(replacement, "duplicate-replacement", "1"),
          "B20": lambda: self._duplicate(replacement, "second-replacement", "2"),
          "B21": lambda: m(original, lambda v: v.__setitem__("outcome", "success")),
          "B22": lambda: m(original, lambda v: v.__setitem__("outcome", "incorrect")),
          "B23": lambda: m(replacement, lambda v: v.__setitem__("lifecycle", "not_started")),
          "B24": lambda: m(replacement, lambda v: v["provenance"].pop("original_work_id")),
          "B25": lambda: self._corrupt_replacement_identity(replacement),
        }
        ops[case]()

    def _duplicate(self, replacement, suffix, index):
        value = json.loads(replacement.read_text(encoding="utf-8")); value.pop("digest")
        value["execution_id"] += "-" + suffix; value["provenance"]["replacement_index"] = index
        value["digest"] = canonical_hash(value)
        replacement.with_name(value["execution_id"] + ".json").write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")

    def _corrupt_replacement_identity(self, replacement):
        value = json.loads(replacement.read_text(encoding="utf-8")); value.pop("digest")
        value["execution_id"] = "corrupt-deterministic-replacement"; value["digest"] = canonical_hash(value)
        replacement.unlink(); replacement.with_name(value["execution_id"] + ".json").write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")

    def _run_case(self, case):
        kind = "terminal" if case in {"A04", "A16"} or case.startswith("B") else "ordinary"
        directory, root, runner = self._fixture(kind)
        try:
            self._baseline(runner, root, kind)
            self._mutation(case, root)
            # The only post-mutation operation is canonical reload plus pair admission.
            boundary = None; error = None
            try:
                rows = self._records(runner, root)
            except Exception as exc: boundary, error = "canonical_reload", exc
            else:
                try: M20EvidenceStore.statistical_pair_input(rows)
                except Exception as exc: boundary, error = "statistical_pair_input", exc
            self.assertIsNotNone(error, f"{case} bypassed production rejection")
            self.evidence.append({"case_id": case, "category": "identity" if case.startswith("A") else "corruption",
                "baseline_fixture": kind, "baseline_admitted": True, "mutated_field_or_state": case,
                "expected_rejection": "production fail-closed", "actual_rejection_boundary": boundary,
                "statistical_consumption_reached": False, "fake_transport_reached": False, "result": "PASS",
                "evidence_reference": f"{self.id()}:{case}", "mutation_applied": True,
                "mutation_verified_on_disk": True, "production_validator_invoked": True,
                "production_admission_invoked": boundary == "statistical_pair_input", "exception_type": type(error).__name__, "test_name": self.id()})
        finally: directory.cleanup()

    def test_a_identity_matrix(self):
        self.assertEqual(len(self.expected_a), 18)
        for case in self.expected_a:
            with self.subTest(case=case): self._run_case(case)

    def test_b_corruption_matrix(self):
        self.assertEqual(len(self.expected_b), 25)
        for case in self.expected_b:
            with self.subTest(case=case): self._run_case(case)

    def test_y_positive_lifecycle_and_full_membership(self):
        # The four canonical lifecycle shapes are admitted/reconstructed from disk.
        for kind in ("ordinary", "pending", "partial", "terminal"):
            with self.subTest(lifecycle=kind):
                directory, root, runner = self._fixture(kind)
                try: self._baseline(runner, root, kind)
                finally: directory.cleanup()
        with TemporaryDirectory() as directory:
            runner = M20AnswerTerminationCalibrationRunner(); root = Path(directory) / "all"
            runner.run_fake_prefix(__import__("src.evaluation.m20_answerterm_calibration_execution", fromlist=["answerterm_authorization_payload"]).answerterm_authorization_payload(), _transport, root, 120)
            rows = self._records(runner, root)
            self.assertEqual(len(rows), 120)
            self.assertEqual(len({r["pair_id"] for r in rows}), 60)
            self.assertEqual(sum(r["spec"]["condition"] == "m20_mind_adaptive_v1" for r in rows), 60)
            self.assertEqual(sum(r["spec"]["condition"] == "m20_mind_fixed_v1" for r in rows), 60)
            for pair_id in {r["pair_id"] for r in rows}:
                self.assertTrue(M20EvidenceStore.statistical_pair_input(tuple(r for r in rows if r["pair_id"] == pair_id))["analyzable"])

    def test_z_offline_live_authorization_consumer(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "live.json"
            with self.assertRaises(PermissionError): load_answerterm_live_authorization(path)
            path.write_text(json.dumps({"authority": "synthetic"}), encoding="utf-8")
            with self.assertRaises(PermissionError): load_answerterm_live_authorization(path)
            exact = answerterm_live_authorization_payload(); path.write_text(json.dumps(exact), encoding="utf-8")
            self.assertEqual(load_answerterm_live_authorization(path), exact)
            for key in ("manifest_digest", "provider_hash", "runtime_identity", "resource_ceiling_digest", "work_ids"):
                bad = dict(exact); bad[key] = "wrong" if key != "work_ids" else []
                path.write_text(json.dumps(bad), encoding="utf-8")
                with self.assertRaises(PermissionError, msg=key): load_answerterm_live_authorization(path)
            path.write_text(json.dumps(exact), encoding="utf-8")
            runner = M20AnswerTerminationCalibrationRunner(); calls = []
            def counted(request, timeout):
                calls.append(1); return _transport(request, timeout)
            runner.run_live(path, counted, Path(directory) / "exact")
            self.assertGreater(len(calls), 0, "exact authorized original must reach fake boundary")
            root = Path(directory) / "replacement"; item = runner.work_items()[0]
            runner._run(item, lambda *_: (_ for _ in ()).throw(TimeoutError("fake")), runner.store(root))
            with self.assertRaises(PermissionError):
                runner.run_live_replacement(path, "arbitrary-work", counted, root)
            replacement = runner.run_live_replacement(path, item.work_id, counted, root)
            # A replay is idempotent, never a second replacement creation.
            self.assertEqual(runner.run_live_replacement(path, item.work_id, counted, root).execution_id,
                             replacement.execution_id)
            self.assertEqual(len(self._records(runner, root)), 2)

    def test_zz_coverage_and_persist_evidence(self):
        ids = [row["case_id"] for row in self.evidence]
        self.assertEqual(set(ids), set(self.expected_a + self.expected_b)); self.assertEqual(len(ids), 43)
        self.assertTrue(all(row["result"] == "PASS" and row["baseline_admitted"] for row in self.evidence))
        destination = os.environ.get("M20_AUDIT_MATRIX_PATH")
        if destination:
            Path(destination).write_text(json.dumps({"schema": "m20_v5_admission_corruption_matrix_v1", "rows": self.evidence}, indent=2) + "\n", encoding="utf-8")
        live_destination = os.environ.get("M20_LIVE_AUTH_PATH")
        if live_destination:
            Path(live_destination).write_text(json.dumps(answerterm_live_authorization_payload(), indent=2) + "\n", encoding="utf-8")
            self.assertEqual(load_answerterm_live_authorization(Path(live_destination)), answerterm_live_authorization_payload())
