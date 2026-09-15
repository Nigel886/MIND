"""Pre-pilot contract tests.  These never invoke a provider or execute a pilot case."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.evaluation.m18_execution_harness import (
    M18BudgetCounters,
    M18ExecutionMode,
    M18FrozenProviderBinding,
    M18ResultStore,
    M18RunRecord,
    M18_RESULT_SCHEMA_VERSION,
    M18RunSpec,
    M18SharedExecutionHarness,
    M18ExecutionIntegrityError,
    harness_identity,
)
from src.evaluation.m18_pilot_execution import (
    M18_PILOT_EXPERIMENT_NAMESPACE,
    M18_PILOT_EXPECTED_RUN_COUNT,
    M18_PILOT_RUN_MANIFEST_FILENAME,
    M18_PILOT_STOP_EVENT_FILENAME,
    M18FrozenPilotExecution,
    M18FrozenPilotPlan,
    M18OperationalTrancheManifest,
    M18OperationalTranchePlan,
    M18OperationalStopCategory,
    M18OperationalStopCondition,
    operational_tranche_specs,
    operational_tranche_manifest,
)
from src.evaluation.m18_shared_provider import M18SharedProviderClient, M18SharedProviderConfiguration
from src.evaluation.m18_task_generation import M18Cohort, M18Difficulty, M18Namespace, generate_m18_case


ROOT = Path(__file__).resolve().parents[1]
HASH = M18SharedProviderConfiguration().config_hash


def plan() -> M18FrozenPilotPlan:
    return M18FrozenPilotPlan.from_repository(ROOT)


def record(spec: M18RunSpec, tranche_id: str | None = None) -> M18RunRecord:
    return M18RunRecord(
        spec.run_id, spec.suite_version, spec.case_id, "multi_step", "easy", spec.system_condition,
        spec.repetition, spec.provider_config_hash, harness_identity(), "budget_exhausted", None,
        "budget_exhausted", M18BudgetCounters(), True, result_schema_version=M18_RESULT_SCHEMA_VERSION,
        experiment_namespace=M18_PILOT_EXPERIMENT_NAMESPACE,
        system_artifact_identity=plan().manifest.harness_manifest.system_artifact_identities[spec.system_condition],
        tranche_id=tranche_id,
    )


class FrozenPilotPlanTests(unittest.TestCase):
    def test_frozen_pilot_entry_point_and_manifest_are_pilot_only(self):
        value = plan()
        self.assertEqual((len(value.cases), len(value.specs), value.manifest.harness_manifest.expected_run_count), (18, 360, 360))
        self.assertEqual(len(value.manifest.run_ids), M18_PILOT_EXPECTED_RUN_COUNT)
        self.assertEqual(value.manifest.harness_manifest.experiment_namespace, M18_PILOT_EXPERIMENT_NAMESPACE)
        self.assertTrue(all(case.namespace is M18Namespace.PILOT for case in value.cases))
        self.assertTrue(all(spec.case_id.startswith("pilot.") for spec in value.specs))
        self.assertEqual({spec.repetition for spec in value.specs}, {1, 2, 3, 4, 5})
        self.assertEqual({spec.system_condition for spec in value.specs[:4]}, set(value.manifest.harness_manifest.systems))

    def test_dry_run_is_provider_free_and_writes_no_run_records(self):
        with TemporaryDirectory() as directory:
            execution = M18FrozenPilotExecution.from_repository(ROOT, environment={"DEEPSEEK_API_KEY": "test-only"})
            dry_run = execution.dry_run()
            self.assertEqual((dry_run.mode, dry_run.expected_run_count, dry_run.missing_run_count), ("operational_tranche_dry_run", 240, 240))
            self.assertFalse((Path(directory) / M18_PILOT_RUN_MANIFEST_FILENAME).exists())
            self.assertEqual(list(execution.manifest.run_ids), list(dry_run.manifest.run_ids))

    def test_manual_or_formal_plan_substitution_is_rejected(self):
        value = plan()
        formal = generate_m18_case(M18Cohort.A, M18Difficulty.EASY, 123456, M18Namespace.FORMAL)
        with self.assertRaises(ValueError):
            M18FrozenPilotPlan(value.repository_root, (formal,) + value.cases[1:], value.specs, value.manifest)

    def test_formal_case_is_rejected_before_provider_invocation(self):
        calls: list[object] = []
        client = M18SharedProviderClient(http_post=lambda *args: calls.append(args) or {}, environment={"DEEPSEEK_API_KEY": "test-only"})
        harness = M18SharedExecutionHarness(HASH, mode=M18ExecutionMode.FROZEN, frozen_binding=M18FrozenProviderBinding(client))
        formal = generate_m18_case(M18Cohort.A, M18Difficulty.EASY, 123456, M18Namespace.FORMAL)
        spec = M18RunSpec("m18_suite_v1", formal.case_id, "mind_lite_v11", 1, HASH)
        with self.assertRaises(ValueError):
            harness.run_frozen_pilot(spec, formal)
        self.assertEqual(calls, [])
        self.assertFalse(hasattr(M18FrozenPilotExecution, "run_formal"))

    def test_frozen_binding_accepts_no_arbitrary_provider(self):
        with self.assertRaises(TypeError):
            M18FrozenProviderBinding(object())
        with self.assertRaises(ValueError):
            M18SharedExecutionHarness(HASH, mode=M18ExecutionMode.FROZEN)

    def test_structural_tranche_is_deterministic_and_covers_recovery_subtypes(self):
        value = plan(); first, second = operational_tranche_specs(value), operational_tranche_specs(value)
        selected = {case.case_id: case for case in value.cases}
        manifest = operational_tranche_manifest(value); ids = tuple(manifest["case_ids"])
        self.assertEqual(first, second); self.assertEqual((len(ids), len(first), len({item.run_id for item in first})), (12, 240, 240))
        self.assertEqual(tuple(item.run_id for item in first), tuple(manifest["run_ids"]))
        self.assertEqual({selected[item].cohort.value for item in ids}, {"multi_step", "distractor_selection", "recovery_correction"})
        self.assertEqual({selected[item].difficulty.value for item in ids}, {"easy", "medium", "hard"})
        self.assertEqual({selected[item].evaluator.failure_schedule.get("subtype") for item in ids if selected[item].cohort.value == "recovery_correction"}, {"recoverable_failure", "invalid_action"})

    def test_tracked_manifest_is_authoritative_and_full_plan_remains_separate(self):
        value = plan(); tranche = M18OperationalTranchePlan.from_pilot_plan(value)
        self.assertEqual((len(value.specs), len(tranche.specs)), (360, 240))
        self.assertEqual(tranche.manifest.manifest_hash, operational_tranche_manifest(value)["manifest_hash"])
        self.assertEqual(M18FrozenPilotExecution(value).full_pilot_dry_run().expected_run_count, 360)

    def test_manifest_hash_and_identity_tampering_fail_before_schedule(self):
        raw = operational_tranche_manifest(plan())
        for field, changed in (("manifest_hash", "0" * 64), ("provider_config_hash", "0" * 64), ("harness_identity", "wrong")):
            with self.subTest(field=field):
                value = dict(raw); value[field] = changed
                with self.assertRaises(ValueError):
                    M18OperationalTrancheManifest.from_dict(value)

    def test_real_entry_point_admits_only_tranche_schedule_before_provider_creation(self):
        execution = M18FrozenPilotExecution.from_repository(ROOT, environment={"DEEPSEEK_API_KEY": "test-only"})
        captured: dict[str, object] = {}
        class Store:
            def missing(self, specs):
                captured["store_specs"] = specs
                return specs
        def initialize(root, specs, *, tranche_id=None):
            captured["root"], captured["init_specs"], captured["tranche_id"] = root, specs, tranche_id
            return Store()
        def execute_specs(store, specs, cases, *, tranche_id=None):
            captured["execute_specs"], captured["cases"], captured["execute_tranche"] = specs, cases, tranche_id
            return ()
        execution._initialize_store = initialize  # type: ignore[method-assign]
        execution._execute_specs = execute_specs  # type: ignore[method-assign]
        self.assertEqual(execution.execute(), ())
        self.assertEqual(len(captured["init_specs"]), 240)
        self.assertEqual(len(captured["execute_specs"]), 240)
        self.assertEqual(captured["tranche_id"], execution.tranche_manifest.tranche_id)
        self.assertEqual(set(captured["cases"]), set(execution.tranche_manifest.case_ids))


class ProvenanceSafeResumeTests(unittest.TestCase):
    def store(self, directory: str) -> tuple[M18ResultStore, M18RunSpec]:
        value = plan()
        return M18ResultStore(Path(directory), value.manifest.harness_manifest, value.specs), value.specs[0]

    def write_unchecked(self, directory: str, name: str, value: M18RunRecord | dict) -> None:
        raw = value.to_dict() if isinstance(value, M18RunRecord) else value
        (Path(directory) / name).write_text(json.dumps(raw), encoding="utf-8")

    def test_valid_record_counts_and_resume_schedules_only_missing_runs(self):
        with TemporaryDirectory() as directory:
            store, spec = self.store(directory)
            valid = record(spec)
            store.persist(valid)
            self.assertEqual(store.completed_ids(), frozenset({spec.run_id}))
            self.assertEqual(len(store.missing(plan().specs)), 359)

    def test_filename_only_or_filename_record_mismatch_fails_closed(self):
        with TemporaryDirectory() as directory:
            store, _ = self.store(directory)
            self.write_unchecked(directory, "filename-only.json", {})
            with self.assertRaises(ValueError): store.completed_ids()
        with TemporaryDirectory() as directory:
            store, spec = self.store(directory)
            self.write_unchecked(directory, "wrong-name.json", record(spec))
            with self.assertRaises(ValueError): store.completed_ids()

    def test_all_identity_tampering_fails_closed_and_never_counts_completed(self):
        for name, change in (
            ("provider", lambda value: replace(value, provider_config_hash="a" * 64)),
            ("artifact", lambda value: replace(value, system_artifact_identity="wrong")),
            ("repetition", lambda value: replace(value, repetition=2)),
            ("harness", lambda value: replace(value, harness_identity="wrong")),
            ("schema", lambda value: replace(value, result_schema_version="wrong")),
            ("namespace", lambda value: replace(value, experiment_namespace="wrong")),
            ("nonmanifest", lambda value: replace(value, run_id="f" * 64, case_id="pilot.not-in-manifest")),
        ):
            with self.subTest(name=name), TemporaryDirectory() as directory:
                store, spec = self.store(directory)
                self.write_unchecked(directory, spec.run_id + ".json", change(record(spec)))
                with self.assertRaises(ValueError): store.completed_ids()

    def test_duplicate_claimed_run_id_is_detected(self):
        with TemporaryDirectory() as directory:
            store, spec = self.store(directory)
            self.write_unchecked(directory, spec.run_id + ".json", record(spec))
            self.write_unchecked(directory, "duplicate-alias.json", record(spec))
            with self.assertRaisesRegex(ValueError, "duplicate stored record run id"):
                store.completed_ids()

    def test_persisted_manifest_config_drift_stops_resume(self):
        with TemporaryDirectory() as directory:
            store, _ = self.store(directory)
            altered = replace(store.manifest, provider_config_hash="b" * 64)
            with self.assertRaisesRegex(ValueError, "configuration drift"):
                M18ResultStore(Path(directory), altered, plan().specs)

    def test_tranche_resume_accepts_only_manifest_member_records(self):
        value = plan(); tranche = M18OperationalTranchePlan.from_pilot_plan(value)
        with TemporaryDirectory() as directory:
            store = M18ResultStore(Path(directory), value.manifest.harness_manifest, tranche.specs, required_tranche_id=tranche.manifest.tranche_id)
            valid = record(tranche.specs[0], tranche.manifest.tranche_id)
            store.persist(valid)
            self.assertEqual(store.completed_ids(), frozenset({valid.run_id}))
            non_tranche = next(item for item in value.specs if item.case_id not in tranche.manifest.case_ids)
            with self.assertRaises(ValueError):
                store.persist(record(non_tranche, tranche.manifest.tranche_id))
            with self.assertRaises(ValueError):
                store.persist(record(tranche.specs[1], "wrong-tranche"))


class OperationalStopTests(unittest.TestCase):
    def _temporary_repository(self, directory: str) -> Path:
        root = Path(directory)
        shutil.copytree(ROOT / "evaluation" / "m18", root / "evaluation" / "m18")
        return root

    def _assert_construction_stop(self, root: Path) -> None:
        with patch("src.evaluation.m18_pilot_execution.M18SharedProviderClient", side_effect=AssertionError("provider creation is forbidden")):
            with self.assertRaises(M18OperationalStopCondition) as raised:
                M18FrozenPilotExecution.from_repository(root, environment={"DEEPSEEK_API_KEY": "test-only"})
        self.assertEqual(raised.exception.event.category, M18OperationalStopCategory.FROZEN_ARTIFACT_DRIFT)
        self.assertEqual(raised.exception.event.stage, "construction")
        stop = root / "evaluation" / "m18" / "results" / "pilot" / M18_PILOT_EXPERIMENT_NAMESPACE / M18_PILOT_STOP_EVENT_FILENAME
        self.assertTrue(stop.exists())
        self.assertEqual(json.loads(stop.read_text(encoding="utf-8"))["category"], "frozen_artifact_drift")
        self.assertEqual(list(stop.parent.glob("[0-9a-f]*.json")), [])

    def test_real_entry_maps_suite_artifact_drift_to_typed_stop_before_provider_creation(self):
        with TemporaryDirectory() as directory:
            root = self._temporary_repository(directory)
            path = root / "evaluation" / "m18" / "suites" / "manifests" / "m18_suite_v1_manifest.json"
            value = json.loads(path.read_text(encoding="utf-8")); value["manifest_hash"] = "0" * 64
            path.write_text(json.dumps(value), encoding="utf-8")
            self._assert_construction_stop(root)

    def test_real_entry_maps_tranche_artifact_drift_to_typed_stop_before_provider_creation(self):
        with TemporaryDirectory() as directory:
            root = self._temporary_repository(directory)
            path = root / "evaluation" / "m18" / "manifests" / "pilot_tranche_v1.json"
            value = json.loads(path.read_text(encoding="utf-8")); value["manifest_hash"] = "0" * 64
            path.write_text(json.dumps(value), encoding="utf-8")
            self._assert_construction_stop(root)

    def test_artifact_stop_blocks_automatic_resume_and_explicit_restart_resumes_missing_only(self):
        with TemporaryDirectory() as directory:
            root = self._temporary_repository(directory)
            path = root / "evaluation" / "m18" / "suites" / "manifests" / "m18_suite_v1_manifest.json"
            original = path.read_text(encoding="utf-8")
            value = json.loads(original); value["split_hash"] = "0" * 64
            path.write_text(json.dumps(value), encoding="utf-8")
            self._assert_construction_stop(root)
            path.write_text(original, encoding="utf-8")
            execution = M18FrozenPilotExecution.from_repository(root, environment={"DEEPSEEK_API_KEY": "test-only"})
            with self.assertRaises(M18OperationalStopCondition) as raised:
                execution.execute()
            self.assertEqual(raised.exception.event.reason, "prior_integrity_stop_requires_explicit_operator_resolution")
            stop = execution.result_root / M18_PILOT_STOP_EVENT_FILENAME
            stop.unlink()
            captured: dict[str, object] = {}
            execution._execute_specs = lambda store, specs, cases, *, tranche_id=None: captured.update(specs=specs, cases=cases, tranche_id=tranche_id) or ()  # type: ignore[method-assign]
            self.assertEqual(execution.execute(), ())
            self.assertEqual(len(captured["specs"]), 240)
            self.assertEqual(captured["tranche_id"], execution.tranche_manifest.tranche_id)

    def test_unrelated_entry_error_is_not_misclassified_as_artifact_drift(self):
        with TemporaryDirectory() as directory:
            root = self._temporary_repository(directory)
            with patch.object(M18FrozenPilotPlan, "from_repository", side_effect=RuntimeError("programming error")):
                with self.assertRaisesRegex(RuntimeError, "programming error"):
                    M18FrozenPilotExecution.from_repository(root, environment={"DEEPSEEK_API_KEY": "test-only"})
            stop = root / "evaluation" / "m18" / "results" / "pilot" / M18_PILOT_EXPERIMENT_NAMESPACE / M18_PILOT_STOP_EVENT_FILENAME
            self.assertFalse(stop.exists())

    def _stop_without_persistence(self, execution, events):
        def stop(category, stage, reason, detail, *, run_id=None, result_persisted=False, persist=True):
            event = __import__("src.evaluation.m18_pilot_execution", fromlist=["M18OperationalStopEvent"]).M18OperationalStopEvent(category, stage, reason, detail, run_id, result_persisted)
            events.append(event)
            raise M18OperationalStopCondition(event)
        execution._raise_stop = stop  # type: ignore[method-assign]

    def test_integrity_signal_stops_before_later_identity_or_persistence(self):
        execution = M18FrozenPilotExecution.from_repository(ROOT, environment={"DEEPSEEK_API_KEY": "test-only"})
        tranche = M18OperationalTranchePlan.from_pilot_plan(plan())
        events, persisted = [], []
        self._stop_without_persistence(execution, events)
        class Store:
            def persist(self, record): persisted.append(record)
        original = M18SharedExecutionHarness.run_frozen_pilot
        def failing(*args, **kwargs):
            raise M18ExecutionIntegrityError("provider_identity_drift", "provider_decode", "model_identity_mismatch")
        M18SharedExecutionHarness.run_frozen_pilot = failing
        try:
            with self.assertRaises(M18OperationalStopCondition):
                execution._execute_specs(Store(), tranche.specs[:3], tranche.cases_by_id, tranche_id=tranche.manifest.tranche_id)
        finally:
            M18SharedExecutionHarness.run_frozen_pilot = original
        self.assertEqual((len(events), len(persisted)), (1, 0))
        self.assertEqual(events[0].category, M18OperationalStopCategory.PROVIDER_IDENTITY_DRIFT)
        self.assertEqual(events[0].run_id, tranche.specs[0].run_id)

    def test_persistence_failure_stops_and_does_not_mark_complete(self):
        execution = M18FrozenPilotExecution.from_repository(ROOT, environment={"DEEPSEEK_API_KEY": "test-only"})
        events = []
        self._stop_without_persistence(execution, events)
        with TemporaryDirectory() as directory:
            tranche = M18OperationalTranchePlan.from_pilot_plan(plan())
            store = M18ResultStore(Path(directory), plan().manifest.harness_manifest, tranche.specs, required_tranche_id=tranche.manifest.tranche_id)
            store.persist = lambda record: (_ for _ in ()).throw(ValueError("atomic failure"))
            original = M18SharedExecutionHarness.run_frozen_pilot
            M18SharedExecutionHarness.run_frozen_pilot = lambda self, spec, case, **kwargs: record(spec, tranche.manifest.tranche_id)
            try:
                with self.assertRaises(M18OperationalStopCondition):
                    execution._execute_specs(store, tranche.specs[:2], tranche.cases_by_id, tranche_id=tranche.manifest.tranche_id)
            finally:
                M18SharedExecutionHarness.run_frozen_pilot = original
        self.assertEqual(events[0].category, M18OperationalStopCategory.PERSISTENCE_INTEGRITY_FAILURE)


if __name__ == "__main__":
    unittest.main()
