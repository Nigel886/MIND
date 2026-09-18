"""Provider-free tests for M18 post-hoc Plan repair provenance admission."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m18_execution_harness import M18BudgetCounters, M18RunRecord, harness_identity
from src.evaluation.m18_pilot_execution import M18OperationalStopCategory, M18OperationalStopCondition
from src.evaluation.m18_plan_repair_rerun import (
    M18PlanRepairPlan, M18PlanRepairResultStore, M18PlanRepairRerun,
    M18PlanRepairRunRecord, M18_PLAN_REPAIR_COMMIT, M18_PLAN_REPAIR_CONDITION_ID,
    M18_PLAN_REPAIR_NAMESPACE, historical_plan_record_digest,
)
from src.evaluation.m18_execution_harness import M18FrozenProviderBinding
from src.evaluation.m18_shared_provider import M18SharedProviderClient


ROOT = Path(__file__).resolve().parents[1]


def temporary_repository(directory: str) -> Path:
    root = Path(directory)
    shutil.copytree(ROOT / "evaluation" / "m18", root / "evaluation" / "m18", ignore=shutil.ignore_patterns("results"))
    return root


def harness_record(spec) -> M18RunRecord:
    return M18RunRecord(
        spec.original_run_id, "m18_suite_v1", spec.case_id, "multi_step", "easy", "plan_and_execute",
        spec.repetition, spec.provider_config_hash, harness_identity(), "budget_exhausted", None,
        "budget_exhausted", M18BudgetCounters(), True,
        system_artifact_identity="423ffc5dfd11be4a96d0a016019b22f420355c7cde9df2b5d232474101e2183d",
    )


class M18PlanRepairRerunTests(unittest.TestCase):
    def plan(self, root: Path = ROOT) -> M18PlanRepairPlan:
        return M18PlanRepairPlan.from_repository(root)

    def test_manifest_freezes_exactly_sixty_unique_plan_replacements(self):
        value = self.plan()
        self.assertEqual((value.manifest.manifest_id, value.manifest.repaired_condition_id),
                         ("m18_plan_repair_rerun_v1", M18_PLAN_REPAIR_CONDITION_ID))
        self.assertEqual((len(value.manifest.case_ids), value.manifest.repetitions, len(value.specs)), (12, (1, 2, 3, 4, 5), 60))
        self.assertEqual(len({item.repaired_run_id for item in value.specs}), 60)
        self.assertEqual(len({item.original_run_id for item in value.specs}), 60)
        self.assertFalse({item.repaired_run_id for item in value.specs} & {item.original_run_id for item in value.specs})
        self.assertTrue(all(item.source_system_condition == "plan_and_execute" for item in value.specs))

    def test_deterministic_dry_run_is_provider_free_and_has_one_to_one_linkage(self):
        first, second = M18PlanRepairRerun.from_repository(ROOT).dry_run(), M18PlanRepairRerun.from_repository(ROOT).dry_run()
        self.assertEqual(first, second)
        self.assertEqual(first, {"repair_identities": 60, "original_historical_identities": 60, "collisions": 0, "one_to_one_linkage": True})

    def test_result_namespace_is_dedicated_and_historical_namespace_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = temporary_repository(directory); plan = self.plan(root)
            self.assertEqual(plan.result_root.parent.name, "repair")
            with self.assertRaisesRegex(ValueError, "namespace"):
                M18PlanRepairResultStore(plan.historical_root, plan)
            store = M18PlanRepairResultStore(plan.result_root, plan)
            self.assertEqual(store.missing(), plan.specs)

    def valid_repair_record(self, plan: M18PlanRepairPlan, index: int = 0) -> M18PlanRepairRunRecord:
        spec = plan.specs[index]
        return M18PlanRepairRunRecord.from_harness_record(spec, plan.manifest, M18_PLAN_REPAIR_COMMIT, harness_record(spec))

    def test_valid_record_resumes_missing_only_and_duplicate_is_rejected(self):
        with TemporaryDirectory() as directory:
            plan = self.plan(temporary_repository(directory)); store = M18PlanRepairResultStore(plan.result_root, plan)
            record = self.valid_repair_record(plan); store.persist(record)
            self.assertEqual(store.completed_ids(), frozenset({record.repaired_run_id}))
            self.assertEqual(len(store.missing()), 59)
            with self.assertRaises(FileExistsError): store.persist(record)

    def test_all_required_provenance_tampering_fails_closed(self):
        with TemporaryDirectory() as directory:
            plan = self.plan(temporary_repository(directory)); store = M18PlanRepairResultStore(plan.result_root, plan)
            valid = self.valid_repair_record(plan)
            changes = {
                "repaired": replace(valid, repaired_run_id="f" * 64),
                "original": replace(valid, original_run_id="e" * 64),
                "case": replace(valid, case_id="pilot.not-admitted"),
                "repetition": replace(valid, repetition=2),
                "condition": replace(valid, repaired_condition_id="wrong"),
                "commit": replace(valid, repair_commit="0" * 40),
                "manifest": replace(valid, repair_manifest_id="wrong"),
                "provider": replace(valid, provider_config_hash="a" * 64),
                "harness": replace(valid, harness_identity="wrong"),
                "namespace": replace(valid, result_namespace="m18_pilot_v1"),
                "execution_baseline": replace(valid, execution_baseline="short"),
            }
            for name, record in changes.items():
                with self.subTest(name=name), self.assertRaises(ValueError): store.persist(record)

    def test_only_manifest_identity_set_is_admitted(self):
        with TemporaryDirectory() as directory:
            plan = self.plan(temporary_repository(directory)); store = M18PlanRepairResultStore(plan.result_root, plan)
            valid = self.valid_repair_record(plan)
            for field, value in (("case_id", "pilot.remaining.case"), ("system_condition", "mind_lite_v11"),
                                 ("system_condition", "direct_tool_calling"), ("system_condition", "react")):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    store.persist(replace(valid, **{field: value}))

    def test_serialized_tamper_or_original_record_never_counts_complete(self):
        with TemporaryDirectory() as directory:
            plan = self.plan(temporary_repository(directory)); store = M18PlanRepairResultStore(plan.result_root, plan)
            valid = self.valid_repair_record(plan)
            raw = valid.to_dict(); raw["original_run_id"] = "0" * 64
            (plan.result_root / (valid.repaired_run_id + ".json")).write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(ValueError): store.completed_ids()
        with TemporaryDirectory() as directory:
            plan = self.plan(temporary_repository(directory)); store = M18PlanRepairResultStore(plan.result_root, plan)
            original = harness_record(plan.specs[0]).to_dict()
            (plan.result_root / (plan.specs[0].original_run_id + ".json")).write_text(json.dumps(original), encoding="utf-8")
            with self.assertRaises(ValueError): store.completed_ids()

    def test_historical_records_are_unchanged_by_provider_free_plan_and_dry_run(self):
        with TemporaryDirectory() as directory:
            root = temporary_repository(directory)
            historical = root / "evaluation" / "m18" / "results" / "pilot" / "m18_pilot_v1"
            historical.mkdir(parents=True)
            historical_record = harness_record(self.plan(root).specs[0]).to_dict()
            (historical / "historical.json").write_text(json.dumps(historical_record, sort_keys=True), encoding="utf-8")
            before = historical_plan_record_digest(historical)
            M18PlanRepairRerun.from_repository(root).dry_run()
            self.assertEqual(historical_plan_record_digest(historical), before)

    def test_stop_framework_remains_available_without_execution(self):
        rerun = M18PlanRepairRerun.from_repository(ROOT)
        with self.assertRaises(M18OperationalStopCondition) as raised:
            rerun.stop_for_integrity_failure(M18OperationalStopCategory.PROVENANCE_INTEGRITY_FAILURE, "preflight", "synthetic")
        self.assertEqual(raised.exception.event.category, M18OperationalStopCategory.PROVENANCE_INTEGRITY_FAILURE)

    def test_tracked_manifest_tampering_fails_before_any_execution_surface(self):
        with TemporaryDirectory() as directory:
            root = temporary_repository(directory)
            path = root / "evaluation" / "m18" / "manifests" / "plan_repair_rerun_v1.json"
            value = json.loads(path.read_text(encoding="utf-8")); value["repair_commit"] = "0" * 40
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ValueError): M18PlanRepairPlan.from_repository(root)

    def _fake_binding(self, answer: int, *, model: str = "deepseek-flash", calls: list[dict] | None = None):
        responses = [
            '{"steps":[{"step_id":"finish","subgoal":"return public answer","capability_id":null}]}',
            json.dumps({"action": "answer", "answer": answer}),
        ]
        def post(url, headers, body, timeout):
            value = json.loads(body)
            if calls is not None: calls.append(value)
            return {"model": model, "choices": [{"message": {"content": responses.pop(0)}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
        return M18FrozenProviderBinding(M18SharedProviderClient(http_post=post, environment={"DEEPSEEK_API_KEY": "test-only"}))

    def test_real_execute_bridge_exists_and_fake_success_persists_repaired_identity(self):
        with TemporaryDirectory() as directory:
            root = temporary_repository(directory); rerun = M18PlanRepairRerun.from_repository(root)
            store = rerun.result_store(); spec = rerun.plan.specs[0]; case = rerun.plan.cases_by_id[spec.case_id]
            requests: list[dict] = []
            rerun.result_store = lambda: store  # type: ignore[method-assign]
            rerun._frozen_binding = lambda environment: self._fake_binding(case.evaluator.target_answer, calls=requests)  # type: ignore[method-assign]
            store.missing = lambda: (spec,)  # type: ignore[method-assign]
            records = rerun.execute("f" * 40, environment={"DEEPSEEK_API_KEY": "test-only"})
            self.assertTrue(hasattr(rerun, "execute"))
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].repaired_run_id, spec.repaired_run_id)
            self.assertEqual(records[0].original_run_id, spec.original_run_id)
            self.assertTrue((rerun.result_root / (spec.repaired_run_id + ".json")).exists())
            self.assertFalse((rerun.result_root / (spec.original_run_id + ".json")).exists())
            self.assertEqual(store.completed_ids(), frozenset({spec.repaired_run_id}))
            self.assertIn("Public request", json.dumps(requests))

    def test_fake_normal_failure_persists_and_remains_benchmark_data(self):
        with TemporaryDirectory() as directory:
            rerun = M18PlanRepairRerun.from_repository(temporary_repository(directory)); store = rerun.result_store()
            spec = rerun.plan.specs[0]
            record = rerun._execute_specs(store, (spec,), "f" * 40, lambda: self._fake_binding(-1))[0]
            self.assertEqual(record.runtime_terminal_outcome, "answer_submitted")
            self.assertEqual(record.neutral_failure_category, "wrong_answer")
            self.assertEqual(store.completed_ids(), frozenset({spec.repaired_run_id}))

    def test_integrity_drift_and_persistence_failure_stop_before_later_identity(self):
        with TemporaryDirectory() as directory:
            rerun = M18PlanRepairRerun.from_repository(temporary_repository(directory)); store = rerun.result_store()
            calls: list[dict] = []
            with self.assertRaises(M18OperationalStopCondition) as raised:
                rerun._execute_specs(store, rerun.plan.specs[:2], "f" * 40,
                                      lambda: self._fake_binding(-1, model="wrong-model", calls=calls))
            self.assertEqual(raised.exception.event.category, M18OperationalStopCategory.PROVIDER_IDENTITY_DRIFT)
            self.assertEqual(len(calls), 1)
            self.assertEqual(store.completed_ids(), frozenset())
        with TemporaryDirectory() as directory:
            rerun = M18PlanRepairRerun.from_repository(temporary_repository(directory)); store = rerun.result_store()
            spec = rerun.plan.specs[0]; store.persist = lambda record: (_ for _ in ()).throw(OSError("synthetic"))  # type: ignore[method-assign]
            case = rerun.plan.cases_by_id[spec.case_id]
            with self.assertRaises(M18OperationalStopCondition) as raised:
                rerun._execute_specs(store, (spec,), "f" * 40,
                                      lambda: self._fake_binding(case.evaluator.target_answer))
            self.assertEqual(raised.exception.event.category, M18OperationalStopCategory.PERSISTENCE_INTEGRITY_FAILURE)


if __name__ == "__main__":
    unittest.main()
