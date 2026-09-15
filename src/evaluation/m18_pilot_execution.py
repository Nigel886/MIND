"""Frozen, pilot-only M18 execution admission.

This module is intentionally the only real-provider-capable M18 execution
surface.  Importing it, building a plan, and running a dry-run never call the
provider or execute a case.  Formal execution is deliberately not implemented.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping

from src.evaluation.m18_execution_harness import (
    M18_FORMAL_REPETITIONS,
    M18_HARNESS_VERSION,
    M18_RESULT_SCHEMA_VERSION,
    M18_SCHEDULE_POLICY,
    M18_SCHEDULE_SEED,
    M18_SYSTEMS,
    M18_SYSTEM_ARTIFACTS,
    M18ExecutionMode,
    M18FrozenProviderBinding,
    M18HarnessManifest,
    M18ResultStore,
    M18RunRecord,
    M18RunSpec,
    M18SharedExecutionHarness,
    balanced_schedule,
    harness_identity,
)
from src.evaluation.m18_shared_provider import M18SharedProviderClient, M18SharedProviderConfiguration
from src.evaluation.m18_suite_freeze import M18_SUITE_VERSION, audit_suite
from src.evaluation.m18_task_generation import (
    M18Case,
    M18Cohort,
    M18Difficulty,
    M18EvaluatorFixture,
    M18Namespace,
    M18PublicCase,
    canonical_json,
)


M18_PILOT_EXPERIMENT_NAMESPACE = "m18_pilot_v1"
M18_PILOT_RESULT_DIRECTORY = Path("evaluation") / "m18" / "results" / "pilot"
M18_PILOT_RUN_MANIFEST_FILENAME = "pilot_run_manifest.json"
M18_PILOT_MAX_STEPS = 3
M18_PILOT_MAX_TOOL_CALLS = 1
M18_PILOT_CASE_COUNT = 18
M18_PILOT_EXPECTED_RUN_COUNT = 360
M18_FROZEN_SUITE_MANIFEST_HASH = "4eb3c8a1a4da0a17297bf26937db28b7d9fb33b9174e2f2128d14fd6fc6aec04"
M18_FROZEN_SPLIT_HASH = "88c0a88063f0e50f1f396f4e01fc2ce6bd53bb4858ac895b8e1fae5e1c911e67"
M18_FROZEN_PILOT_PRIVATE_HASH = "811d3bd92d016d36efcd147770d8f97b0211fb7c652093c4b00d13a81fb8da1d"
M18_FROZEN_PILOT_PUBLIC_HASH = "2515eb193492d0423dfd1b32b5207106ddb4c53088c4572158db94a6119b081d"
M18_PILOT_TRANCHE_ID = "m18_pilot_operational_tranche_v1"
M18_PILOT_TRANCHE_CASE_IDS = (
    "pilot.multi_step.easy.21000.0", "pilot.multi_step.medium.21002.0", "pilot.multi_step.hard.21004.0",
    "pilot.distractor_selection.easy.21006.0", "pilot.distractor_selection.medium.21008.0", "pilot.distractor_selection.hard.21010.0",
    "pilot.recovery_correction.easy.21012.0", "pilot.recovery_correction.easy.21013.1",
    "pilot.recovery_correction.medium.21014.0", "pilot.recovery_correction.medium.21015.1",
    "pilot.recovery_correction.hard.21016.0", "pilot.recovery_correction.hard.21017.1",
)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid frozen M18 artifact: {path}") from error


def _case_from_record(value: Mapping[str, Any]) -> M18Case:
    """Parse an immutable frozen fixture without ever exposing it to a provider."""
    try:
        public = value["public"]
        evaluator = value["evaluator"]
        case = M18Case(
            value["case_id"], M18Namespace(value["namespace"]), M18Cohort(value["cohort"]),
            M18Difficulty(value["difficulty"]),
            M18PublicCase(public["case_id"], public["task_text"], tuple(public["tools"]), public["environment_config"]),
            M18EvaluatorFixture(evaluator["target_answer"], evaluator["target_state"], evaluator["evaluator_rule"], evaluator["failure_schedule"]),
            value["generation_seed"], value["generation_protocol_version"], value["environment_version"], value["evaluator_version"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("invalid frozen pilot case record") from error
    if canonical_json(case.to_dict()) != canonical_json(dict(value)):
        raise ValueError("frozen pilot case canonical representation mismatch")
    return case


@dataclass(frozen=True)
class M18PilotRunManifest:
    """Dedicated pilot identity, distinct from both suite and formal manifests."""

    harness_manifest: M18HarnessManifest
    pilot_case_ids: tuple[str, ...]
    run_ids: tuple[str, ...]
    max_steps: int = M18_PILOT_MAX_STEPS
    max_tool_calls: int = M18_PILOT_MAX_TOOL_CALLS

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.harness_manifest.to_dict(),
            "pilot_case_ids": list(self.pilot_case_ids),
            "run_ids": list(self.run_ids),
            "max_steps": self.max_steps,
            "max_tool_calls": self.max_tool_calls,
            "execution_mode": M18ExecutionMode.FROZEN.value,
            "entry_point": "m18_frozen_pilot_execution_v1",
        }


@dataclass(frozen=True)
class M18FrozenPilotPlan:
    """Validated frozen pilot namespace and its deterministic run schedule."""

    repository_root: Path
    cases: tuple[M18Case, ...]
    specs: tuple[M18RunSpec, ...]
    manifest: M18PilotRunManifest

    def __post_init__(self) -> None:
        harness = self.manifest.harness_manifest
        if (
            len(self.cases) != M18_PILOT_CASE_COUNT or len(self.specs) != M18_PILOT_EXPECTED_RUN_COUNT
            or harness.suite_version != M18_SUITE_VERSION
            or harness.suite_manifest_hash != M18_FROZEN_SUITE_MANIFEST_HASH
            or harness.split_hash != M18_FROZEN_SPLIT_HASH
            or harness.provider_config_hash != M18SharedProviderConfiguration().config_hash
            or harness.experiment_namespace != M18_PILOT_EXPERIMENT_NAMESPACE
            or harness.harness_identity != harness_identity()
            or harness.system_artifact_identities != M18_SYSTEM_ARTIFACTS
        ):
            raise ValueError("frozen pilot plan identity mismatch")
        if any(case.namespace is not M18Namespace.PILOT for case in self.cases):
            raise ValueError("frozen pilot plan contains a non-pilot case")
        audit = audit_suite(self.cases)
        if audit["private_hash"] != M18_FROZEN_PILOT_PRIVATE_HASH or audit["public_hash"] != M18_FROZEN_PILOT_PUBLIC_HASH:
            raise ValueError("frozen pilot plan case hash mismatch")
        if tuple(case.case_id for case in self.cases) != self.manifest.pilot_case_ids:
            raise ValueError("frozen pilot plan case identity mismatch")
        if tuple(spec.run_id for spec in self.specs) != self.manifest.run_ids:
            raise ValueError("frozen pilot plan schedule identity mismatch")

    @classmethod
    def from_repository(cls, repository_root: Path) -> "M18FrozenPilotPlan":
        root = repository_root.resolve()
        suite_root = root / "evaluation" / "m18" / "suites"
        suite_manifest = _read_json(suite_root / "manifests" / "m18_suite_v1_manifest.json")
        split = _read_json(suite_root / "manifests" / "m18_suite_v1_split.json")
        records = _read_json(suite_root / "pilot" / "private_cases.json")
        if not isinstance(records, list) or not isinstance(split, Mapping) or not isinstance(suite_manifest, Mapping):
            raise ValueError("frozen pilot artifacts have invalid top-level schemas")
        if suite_manifest.get("suite_version") != M18_SUITE_VERSION or suite_manifest.get("pilot_case_count") != M18_PILOT_CASE_COUNT or suite_manifest.get("manifest_hash") != M18_FROZEN_SUITE_MANIFEST_HASH or suite_manifest.get("split_hash") != M18_FROZEN_SPLIT_HASH:
            raise ValueError("frozen pilot suite identity mismatch")
        pilot_ids, formal_ids = split.get("pilot_ids"), split.get("formal_ids")
        if not isinstance(pilot_ids, list) or not isinstance(formal_ids, list) or len(pilot_ids) != M18_PILOT_CASE_COUNT:
            raise ValueError("frozen pilot split mismatch")
        if set(pilot_ids) & set(formal_ids) or any(not isinstance(item, str) or not item.startswith("pilot.") for item in pilot_ids):
            raise ValueError("pilot/formal namespace overlap or invalid pilot id")
        cases = tuple(_case_from_record(item) for item in records if isinstance(item, Mapping))
        if len(cases) != len(records) or any(case.namespace is not M18Namespace.PILOT for case in cases):
            raise ValueError("pilot loader admitted a non-pilot case")
        if tuple(case.case_id for case in cases) != tuple(pilot_ids) or len(set(pilot_ids)) != M18_PILOT_CASE_COUNT:
            raise ValueError("pilot fixture membership/order mismatch")
        audit = audit_suite(cases)
        expected_audit = suite_manifest.get("pilot")
        if not isinstance(expected_audit, Mapping) or any(audit.get(key) != expected_audit.get(key) for key in ("case_count", "cohort_counts", "difficulty_counts", "subtype_counts", "private_hash", "public_hash")):
            raise ValueError("pilot fixture hash or distribution mismatch")
        provider = M18SharedProviderConfiguration()
        specs = balanced_schedule(tuple(pilot_ids), provider.config_hash)
        if len(specs) != M18_PILOT_EXPECTED_RUN_COUNT or any(not spec.case_id.startswith("pilot.") for spec in specs):
            raise ValueError("frozen pilot schedule mismatch")
        harness = M18HarnessManifest(
            M18_SUITE_VERSION, suite_manifest["manifest_hash"], suite_manifest["split_hash"], provider.config_hash,
            M18_FORMAL_REPETITIONS, M18_SCHEDULE_SEED, len(specs), M18_SYSTEMS, harness_identity(),
            result_schema_version=M18_RESULT_SCHEMA_VERSION, experiment_namespace=M18_PILOT_EXPERIMENT_NAMESPACE,
            system_artifact_identities=M18_SYSTEM_ARTIFACTS,
        )
        manifest = M18PilotRunManifest(harness, tuple(pilot_ids), tuple(spec.run_id for spec in specs))
        return cls(root, cases, specs, manifest)

    @property
    def cases_by_id(self) -> Mapping[str, M18Case]:
        return {case.case_id: case for case in self.cases}


@dataclass(frozen=True)
class M18PilotDryRun:
    mode: str
    expected_run_count: int
    missing_run_count: int
    manifest: M18PilotRunManifest


def operational_tranche_specs(plan: M18FrozenPilotPlan) -> tuple[M18RunSpec, ...]:
    """Frozen structural subset: A/B first canonical case per difficulty; both C subtypes."""
    if tuple(sorted(M18_PILOT_TRANCHE_CASE_IDS)) != tuple(sorted(set(M18_PILOT_TRANCHE_CASE_IDS))):
        raise ValueError("tranche case ids must be unique")
    available = {case.case_id for case in plan.cases}
    if not set(M18_PILOT_TRANCHE_CASE_IDS) <= available:
        raise ValueError("tranche includes a non-pilot case")
    specs = tuple(spec for spec in plan.specs if spec.case_id in M18_PILOT_TRANCHE_CASE_IDS)
    if len(specs) != 240:
        raise ValueError("frozen tranche must contain 240 identities")
    return specs


def operational_tranche_manifest(plan: M18FrozenPilotPlan) -> dict[str, Any]:
    specs = operational_tranche_specs(plan)
    core = {"tranche_id": M18_PILOT_TRANCHE_ID, "source_experiment_namespace": M18_PILOT_EXPERIMENT_NAMESPACE,
            "source_suite_version": M18_SUITE_VERSION, "source_suite_manifest_hash": plan.manifest.harness_manifest.suite_manifest_hash,
            "selection_rule": "first_canonical_multi_step_and_distractor_per_difficulty_plus_both_recovery_subtypes_per_difficulty_v1",
            "case_ids": list(M18_PILOT_TRANCHE_CASE_IDS), "systems": list(M18_SYSTEMS), "repetitions": 5,
            "expected_run_count": len(specs), "provider_config_hash": plan.manifest.harness_manifest.provider_config_hash,
            "harness_identity": plan.manifest.harness_manifest.harness_identity,
            "run_ids": [spec.run_id for spec in specs],
            "stop_conditions": ["provider_model_or_config_drift", "truth_leakage", "evaluator_or_environment_invariant_failure", "result_provenance_or_persistence_failure", "frozen_artifact_drift", "systematic_provider_or_decoder_contract_incompatibility"],
            "interpretation": "operational_diagnostic_not_powered_comparative_result"}
    return {**core, "manifest_hash": sha256(canonical_json(core).encode("utf-8")).hexdigest()}


class M18FrozenPilotExecution:
    """The only M18 real-provider-capable entry point; formal execution is absent."""

    def __init__(self, plan: M18FrozenPilotPlan, *, environment: Mapping[str, str] | None = None) -> None:
        if not isinstance(plan, M18FrozenPilotPlan):
            raise TypeError("frozen pilot execution requires an M18FrozenPilotPlan")
        if plan.manifest.harness_manifest.experiment_namespace != M18_PILOT_EXPERIMENT_NAMESPACE:
            raise ValueError("execution plan is not in the pilot namespace")
        self._plan, self._environment = plan, environment

    @classmethod
    def from_repository(cls, repository_root: Path, *, environment: Mapping[str, str] | None = None) -> "M18FrozenPilotExecution":
        return cls(M18FrozenPilotPlan.from_repository(repository_root), environment=environment)

    @property
    def manifest(self) -> M18PilotRunManifest:
        return self._plan.manifest

    @property
    def result_root(self) -> Path:
        return self._plan.repository_root / M18_PILOT_RESULT_DIRECTORY / M18_PILOT_EXPERIMENT_NAMESPACE

    def _initialize_store(self, result_root: Path) -> M18ResultStore:
        result_root.mkdir(parents=True, exist_ok=True)
        pilot_manifest_path = result_root / M18_PILOT_RUN_MANIFEST_FILENAME
        value = self._plan.manifest.to_dict()
        if pilot_manifest_path.exists():
            if _read_json(pilot_manifest_path) != value:
                raise ValueError("pilot run-manifest configuration drift")
        else:
            with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=result_root, suffix=".tmp") as handle:
                json.dump(value, handle, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                handle.write("\n")
                temporary = Path(handle.name)
            temporary.replace(pilot_manifest_path)
        return M18ResultStore(result_root, self._plan.manifest.harness_manifest, self._plan.specs, metadata_filenames=(M18_PILOT_RUN_MANIFEST_FILENAME,))

    def dry_run(self) -> M18PilotDryRun:
        """PILOT DRY-RUN: validates identities and optional resume storage only."""
        return M18PilotDryRun("pilot_dry_run", len(self._plan.specs), len(self._plan.specs), self._plan.manifest)

    def execute(self) -> tuple[M18RunRecord, ...]:
        """REAL PILOT EXECUTION.  It has no formal-suite input or formal mode."""
        store = self._initialize_store(self.result_root)
        missing = store.missing(self._plan.specs)
        records: list[M18RunRecord] = []
        cases = self._plan.cases_by_id
        for spec in missing:
            # New client/binding/session adapters per run prevent cross-run state.
            client = M18SharedProviderClient(environment=self._environment)
            binding = M18FrozenProviderBinding(client)
            harness = M18SharedExecutionHarness(
                self._plan.manifest.harness_manifest.provider_config_hash,
                max_steps=M18_PILOT_MAX_STEPS,
                max_tool_calls=M18_PILOT_MAX_TOOL_CALLS,
                mode=M18ExecutionMode.FROZEN,
                frozen_binding=binding,
            )
            case = cases.get(spec.case_id)
            if case is None or case.namespace is not M18Namespace.PILOT:
                raise ValueError("pilot plan contains a non-pilot case")
            record = harness.run_frozen_pilot(spec, case)
            store.persist(record)
            records.append(record)
        return tuple(records)
