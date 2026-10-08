"""Fake-only admission and lifecycle tests for the frozen manifest-v5 bridge."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m20_answerterm_calibration_execution import (
    M20AnswerTerminationCalibrationRunner, answerterm_authorization_payload,
    answerterm_live_authorization_payload,
)
from src.evaluation.m20_harness import M20Condition, M20EvidenceStore, M20IntegrityError, M20Outcome


def reply(value):
    return {"model": "deepseek-flash", "choices": [{"message": {"content": json.dumps(value)}}]}


def public_responder(request, _timeout):
    public = json.loads(request["messages"][1]["content"].split("Public input: ", 1)[1])
    return reply({"kind": "stop"} if public["legal_decision_kinds"] == ["answer", "stop"]
                 else {"kind": "act", "action_id": "advance"})


def distract_responder(_request, _timeout):
    return reply({"kind": "act", "action_id": "distract"})


class M20AnswerTermCalibrationExecutionTest(unittest.TestCase):
    def test_pair_level_statistical_admission_rejects_raw_v5_and_preserves_ordinary_pair(self):
        runner = M20AnswerTerminationCalibrationRunner()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            pair_id = runner.work_items()[0].pair_id
            items = tuple(item for item in runner.work_items() if item.pair_id == pair_id)
            for item in items:
                runner._run(item, public_responder, runner.store(root))
            records = runner.store(root).records()
            with self.assertRaises(M20IntegrityError):
                M20EvidenceStore.statistical_input(records[0])
            projected = M20EvidenceStore.statistical_pair_input(records)
        self.assertTrue(projected["analyzable"])
        self.assertIsNone(projected["missingness"])
        self.assertEqual({projected["adaptive"]["spec"]["condition"], projected["fixed"]["spec"]["condition"]},
                         {M20Condition.MIND_ADAPTIVE.value, M20Condition.MIND_FIXED.value})

    def test_pair_level_statistical_admission_marks_pending_and_partial_replacements_missing(self):
        runner = M20AnswerTerminationCalibrationRunner()
        for condition in (M20Condition.MIND_ADAPTIVE, M20Condition.MIND_FIXED):
            with self.subTest(condition=condition.value), TemporaryDirectory() as directory:
                root = Path(directory) / "records"
                pair_id = runner.work_items()[0].pair_id
                items = tuple(item for item in runner.work_items() if item.pair_id == pair_id)
                failed = next(item for item in items if item.spec.condition is condition)
                opposite = next(item for item in items if item.spec.condition is not condition)
                runner._run(failed, lambda *_: (_ for _ in ()).throw(TimeoutError("fake")), runner.store(root))
                runner._run(opposite, public_responder, runner.store(root))
                pending = runner.store(root).records()
                with self.assertRaises(M20IntegrityError): M20EvidenceStore.statistical_input(pending[0])
                projected = M20EvidenceStore.statistical_pair_input(pending)
                self.assertFalse(projected["analyzable"])
                self.assertEqual(projected["missingness"], "replacement_unavailable")
                self.assertIsNone(projected["adaptive"] if condition is M20Condition.MIND_ADAPTIVE else projected["fixed"])
                artifact = Path(directory) / "authorization.json"
                artifact.write_text(json.dumps(answerterm_live_authorization_payload()), encoding="utf-8")
                with self.assertRaises(InterruptedError):
                    runner.run_live_replacement(artifact, failed.work_id, public_responder, root,
                                                interrupt_before_execution=True)
                partial = runner.store(root).records()
                projected = M20EvidenceStore.statistical_pair_input(partial)
                self.assertFalse(projected["analyzable"])
                self.assertEqual(projected["missingness"], "replacement_unavailable")

    def test_pair_level_statistical_admission_selects_terminal_replacement_with_retries(self):
        runner = M20AnswerTerminationCalibrationRunner()
        with TemporaryDirectory() as directory:
            root = Path(directory) / "records"; pair_id = runner.work_items()[0].pair_id
            items = tuple(item for item in runner.work_items() if item.pair_id == pair_id)
            failed = items[0]; opposite = items[1]
            runner._run(failed, lambda *_: (_ for _ in ()).throw(TimeoutError("fake")), runner.store(root))
            runner._run(opposite, public_responder, runner.store(root))
            artifact = Path(directory) / "authorization.json"
            artifact.write_text(json.dumps(answerterm_live_authorization_payload()), encoding="utf-8")
            attempts = []
            def retry_once(request, timeout):
                attempts.append(1)
                if len(attempts) == 1: raise TimeoutError("fake")
                return public_responder(request, timeout)
            replacement = runner.run_live_replacement(artifact, failed.work_id, retry_once, root)
            projected = M20EvidenceStore.statistical_pair_input(runner.store(root).records())
        selected = projected["adaptive"] if failed.spec.condition is M20Condition.MIND_ADAPTIVE else projected["fixed"]
        self.assertTrue(projected["analyzable"])
        self.assertEqual(selected["spec"]["replacement_of"], failed.spec.execution_id)
        self.assertGreater(selected["telemetry"]["provider_interactions"], 0)
        self.assertEqual(selected["telemetry"]["provider_transport_attempts"],
                         selected["telemetry"]["provider_interactions"] + 1)

    def test_pair_level_statistical_admission_rejects_linkage_corruption(self):
        runner = M20AnswerTerminationCalibrationRunner()
        with TemporaryDirectory() as directory:
            root = Path(directory); pair_id = runner.work_items()[0].pair_id
            for item in (item for item in runner.work_items() if item.pair_id == pair_id):
                runner._run(item, public_responder, runner.store(root))
            records = runner.store(root).records()
        for mutate in (
            lambda values: values[0]["spec"].__setitem__("condition", "invalid"),
            lambda values: values[0].__setitem__("pair_id", "wrong"),
            lambda values: values[0]["provenance"].pop("metrics"),
            lambda values: values[0]["provenance"].pop("answerterm_protocol"),
            lambda values: values[0]["spec"].__setitem__("frozen_pair_id", "wrong"),
            lambda values: values[0]["telemetry"].__setitem__("provider_interactions", 99),
        ):
            corrupt = deepcopy(records); mutate(corrupt)
            with self.assertRaises(M20IntegrityError):
                M20EvidenceStore.statistical_pair_input(corrupt)

    def test_full_fake_manifest_projects_exactly_one_effective_pair_per_frozen_pair(self):
        runner, authorization = M20AnswerTerminationCalibrationRunner(), answerterm_authorization_payload()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            runner.run_fake_prefix(authorization, public_responder, root, 120)
            records = runner.store(root).records()
            pairs = {}
            for record in records:
                pairs.setdefault(record["pair_id"], []).append(record)
            projections = tuple(M20EvidenceStore.statistical_pair_input(tuple(value)) for value in pairs.values())
        self.assertEqual((len(records), len(pairs), len(projections)), (120, 60, 60))
        self.assertTrue(all(projection["analyzable"] for projection in projections))
        self.assertEqual(sum(projection["adaptive"] is not None for projection in projections), 60)
        self.assertEqual(sum(projection["fixed"] is not None for projection in projections), 60)
    def test_live_artifact_gate_is_distinct_from_synthetic_authority(self):
        runner = M20AnswerTerminationCalibrationRunner()
        with TemporaryDirectory() as directory:
            root, artifact = Path(directory) / "records", Path(directory) / "authorization.json"
            artifact.write_text(json.dumps(answerterm_authorization_payload()), encoding="utf-8")
            with self.assertRaises(PermissionError):
                runner.run_live(artifact, lambda *_: self.fail("synthetic reached live transport"), root / "records")
            artifact.write_text(json.dumps(answerterm_live_authorization_payload()), encoding="utf-8")
            records = runner.run_live(artifact, public_responder, root / "records")
            self.assertEqual(len(records), 120)

    def test_live_replacement_is_derived_and_idempotent(self):
        runner = M20AnswerTerminationCalibrationRunner()
        with TemporaryDirectory() as directory:
            root, artifact = Path(directory) / "records", Path(directory) / "authorization.json"
            artifact.write_text(json.dumps(answerterm_live_authorization_payload()), encoding="utf-8")
            original = runner.work_items()[0]
            failed = runner._run(original, lambda *_: (_ for _ in ()).throw(TimeoutError("fake")), runner.store(root))
            self.assertEqual(failed.outcome, M20Outcome.PROVIDER_FAILURE)
            calls = []
            replacement = runner.run_live_replacement(artifact, original.work_id,
                                                       lambda request, timeout: calls.append(1) or public_responder(request, timeout), root)
            self.assertEqual(replacement.spec.replacement_of, original.spec.execution_id)
            before = len(calls)
            again = runner.run_live_replacement(artifact, original.work_id,
                                                lambda *_: self.fail("completed replacement reached transport"), root)
            self.assertEqual((again.digest, len(calls)), (replacement.digest, before))
            with self.assertRaises(PermissionError): runner.run_live_replacement(artifact, replacement.execution_id, public_responder, root)
    def test_exact_authorization_rejects_mutations_before_transport(self):
        runner, authorization = M20AnswerTerminationCalibrationRunner(), answerterm_authorization_payload()
        calls = []
        with TemporaryDirectory() as directory:
            with self.assertRaises(PermissionError): runner.run_fake_prefix(None, lambda *_: calls.append(1), Path(directory), 1)
            for key, value in (("protocol", "m20_calibration_ceilingv2_v1"), ("manifest_digest", "0" * 64),
                               ("pair_work_binding_digest", "0" * 64), ("runtime_identity", "old"),
                               ("answer_readiness_identity", "old"), ("ordering_identity", "old"),
                               ("provider_hash", "0" * 64), ("resource_ceiling_version", "m20_real_ceiling_v1"),
                               ("resource_ceiling_digest", "0" * 64), ("namespace", "wrong")):
                invalid = deepcopy(authorization); invalid[key] = value
                with self.assertRaises(PermissionError): runner.run_fake_prefix(invalid, lambda *_: calls.append(1), Path(directory), 1)
        self.assertEqual(calls, [])

    def test_answer_phase_paths_shared_by_adaptive_and_fixed(self):
        runner, authorization = M20AnswerTerminationCalibrationRunner(), answerterm_authorization_payload()
        ready = [item for item in runner.work_items() if item.spec.case_id == "m20.real.answer_ready_early_stop.01"]
        progress = [item for item in runner.work_items() if item.spec.case_id == "m20.real.multi_step_stateful.01"]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            records = tuple(runner._run(item, public_responder, runner.store(root)) for item in ready + progress)
        for record in (record for record in records if record.spec.case_id == "m20.real.answer_ready_early_stop.01"):
            self.assertEqual((record.telemetry.answer_ready_first_cycle, record.telemetry.tool_attempts,
                              record.telemetry.stop_proposed), (1, 0, True))
        for record in (record for record in records if record.spec.case_id == "m20.real.multi_step_stateful.01"):
            self.assertEqual((record.telemetry.answer_ready_first_cycle, record.telemetry.tool_attempts,
                              record.telemetry.stop_proposed), (3, 2, True))
            self.assertFalse(record.telemetry.illegal_act_in_answer_phase)

    def test_answer_handoff_illegal_act_and_public_projection(self):
        runner = M20AnswerTerminationCalibrationRunner()
        case_id = "m20.real.multi_step_stateful.01"
        items = [item for item in runner.work_items() if item.spec.case_id == case_id]
        seen = []
        def answer(request, _timeout):
            seen.append(request)
            public = json.loads(request["messages"][1]["content"].split("Public input: ", 1)[1])
            return reply({"kind": "answer", "payload": "answer:" + case_id}
                         if public["legal_decision_kinds"] == ["answer", "stop"]
                         else {"kind": "act", "action_id": "advance"})
        def illegal_after_ready(request, _timeout):
            public = json.loads(request["messages"][1]["content"].split("Public input: ", 1)[1])
            return reply({"kind": "act", "action_id": "advance"})
        with TemporaryDirectory() as directory:
            root = Path(directory)
            records = tuple(runner._run(item, answer, runner.store(root)) for item in items)
            illegal = runner._run(next(item for item in runner.work_items()
                                       if item.spec.case_id == "m20.real.answer_ready_early_stop.01"),
                                  illegal_after_ready, runner.store(root))
        self.assertTrue(all(record.telemetry.answer_proposed and record.telemetry.evaluator_handoff
                            for record in records))
        self.assertTrue(all(record.outcome is M20Outcome.SUCCESS for record in records))
        self.assertEqual((illegal.outcome, illegal.telemetry.tool_attempts,
                          illegal.telemetry.illegal_act_in_answer_phase),
                         (M20Outcome.PROVIDER_FAILURE, 0, True))
        serialized = json.dumps(seen)
        self.assertNotIn("answer:" + case_id, serialized)
        self.assertNotIn("reference_witness", serialized)

    def test_retry_chains_resource_reload_and_completed_idempotence(self):
        runner, authorization = M20AnswerTerminationCalibrationRunner(), answerterm_authorization_payload()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first_item = next(item for item in runner.work_items() if item.spec.case_id == "m20.real.answer_ready_early_stop.01")
            for retries in range(3):
                calls = 0
                def retrying(request, timeout):
                    nonlocal calls
                    calls += 1
                    if calls <= retries: raise TimeoutError("fake")
                    return public_responder(request, timeout)
                item = runner.work_items()[runner.work_items().index(first_item) + retries * 2]
                first = runner._run(item, retrying, runner.store(root))
                self.assertEqual((first.telemetry.provider_interactions, first.telemetry.provider_transport_attempts), (1, retries + 1))
                self.assertEqual([value.retry_index for value in first.telemetry.retries], list(range(retries + 1)))
            before = calls
            again = runner._run(item, lambda *_: self.fail("completed work reached transport"), runner.store(root))
            self.assertEqual(again.digest, first.digest)
            self.assertEqual(calls, before)
            all_records = runner.run_fake_prefix(authorization, public_responder, root, 120)
            self.assertEqual(len(runner.store(root).records()), 120)
            runner.run_fake_prefix(authorization, lambda *_: self.fail("completed work reached transport"), root, 120)
            self.assertTrue(all(item.telemetry.provider_interactions <= 8 and item.telemetry.tool_attempts <= 8 for item in all_records))

    def test_capacity_partial_resume_and_corruption_fail_closed(self):
        runner, authorization = M20AnswerTerminationCalibrationRunner(), answerterm_authorization_payload()
        constrained = next(item for item in runner.work_items() if item.spec.case_id == "m20.real.resource_constrained.01")
        with TemporaryDirectory() as directory:
            root, calls = Path(directory), []
            def counted_distract(request, timeout):
                calls.append((request, timeout)); return distract_responder(request, timeout)
            record = runner._run(constrained, counted_distract, runner.store(root))
            self.assertEqual((record.outcome, len(calls), record.telemetry.provider_interactions,
                              record.telemetry.tool_attempts), (M20Outcome.INCOMPLETE, 8, 8, 8))

            with self.assertRaises(InterruptedError):
                runner.run_fake_prefix(authorization, public_responder, root, 1, interrupt_before_execution=True)
            # A zero-commit partial is retained then canonically resolved on resume.
            runner._run(runner.work_items()[0], public_responder, runner.store(root))
            self.assertTrue(list(root.glob("*.partial.resolved.json")))

            path = root / (constrained.spec.execution_id + ".json")
            damaged = json.loads(path.read_text(encoding="utf-8")); damaged["outcome"] = "success"
            path.write_text(json.dumps(damaged), encoding="utf-8")
            with self.assertRaises(M20IntegrityError): runner.store(root).records()


if __name__ == "__main__":
    unittest.main()
