"""Pre-pilot contract tests.  These never invoke a provider or execute a pilot case."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m18_execution_harness import (
    M18BudgetCounters,
    M18ExecutionMode,
    M18FrozenProviderBinding,
    M18ResultStore,
    M18RunRecord,
    M18RunSpec,
    M18SharedExecutionHarness,
    harness_identity,
)
from src.evaluation.m18_pilot_execution import (
    M18_PILOT_EXPERIMENT_NAMESPACE,
    M18_PILOT_EXPECTED_RUN_COUNT,
    M18_PILOT_RUN_MANIFEST_FILENAME,
    M18FrozenPilotExecution,
    M18FrozenPilotPlan,
)
from src.evaluation.m18_shared_provider import M18SharedProviderClient, M18SharedProviderConfiguration
from src.evaluation.m18_task_generation import M18Cohort, M18Difficulty, M18Namespace, generate_m18_case


ROOT = Path(__file__).resolve().parents[1]
HASH = M18SharedProviderConfiguration().config_hash


def plan() -> M18FrozenPilotPlan:
    return M18FrozenPilotPlan.from_repository(ROOT)


def record(spec: M18RunSpec) -> M18RunRecord:
    return M18RunRecord(
        spec.run_id, spec.suite_version, spec.case_id, "multi_step", "easy", spec.system_condition,
        spec.repetition, spec.provider_config_hash, harness_identity(), "budget_exhausted", None,
        "budget_exhausted", M18BudgetCounters(), True, result_schema_version="m18_result_record_v1",
        experiment_namespace=M18_PILOT_EXPERIMENT_NAMESPACE,
        system_artifact_identity=plan().manifest.harness_manifest.system_artifact_identities[spec.system_condition],
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
            dry_run = execution.dry_run(Path(directory))
            self.assertEqual((dry_run.mode, dry_run.expected_run_count, dry_run.missing_run_count), ("pilot_dry_run", 360, 360))
            files = {item.name for item in Path(directory).glob("*.json")}
            self.assertEqual(files, {"manifest.json", M18_PILOT_RUN_MANIFEST_FILENAME})
            self.assertEqual(json.loads((Path(directory) / M18_PILOT_RUN_MANIFEST_FILENAME).read_text())["run_ids"], list(execution.manifest.run_ids))

    def test_manual_or_formal_plan_substitution_is_rejected(self):
        value = plan()
        formal = generate_m18_case(M18Cohort.A, M18Difficulty.EASY, 123456, M18Namespace.FORMAL)
        with self.assertRaises(ValueError):
            M18FrozenPilotPlan((formal,) + value.cases[1:], value.specs, value.manifest)

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


if __name__ == "__main__":
    unittest.main()
