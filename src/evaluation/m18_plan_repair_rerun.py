"""Provider-free provenance admission for the post-hoc M18 Plan repair rerun.

This module deliberately has no provider or execution entry point.  It freezes
the replacement identities and validates result persistence for a later,
separately authorized rerun.  Historical pilot records are never read for
resume and can never share the repair result namespace.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping

from src.evaluation.m18_execution_harness import (
    M18BudgetCounters,
    M18ExecutionIntegrityError,
    M18ExecutionMode,
    M18_FORMAL_REPETITIONS,
    M18FrozenProviderBinding,
    M18_RESULT_SCHEMA_VERSION,
    M18_SYSTEM_ARTIFACTS,
    M18RunRecord,
    M18RunSpec,
    M18SharedExecutionHarness,
    harness_identity,
)
from src.evaluation.m18_pilot_execution import (
    M18OperationalStopCategory,
    M18OperationalStopCondition,
    M18OperationalStopEvent,
    M18OperationalTranchePlan,
    M18FrozenArtifactValidationError,
    M18FrozenPilotPlan,
    M18_PILOT_EXPERIMENT_NAMESPACE,
    M18_PILOT_RESULT_DIRECTORY,
    M18_PILOT_TRANCHE_ID,
    _read_json,
)
from src.evaluation.m18_shared_provider import M18SharedProviderClient, M18SharedProviderConfiguration
from src.evaluation.m18_task_generation import M18Case, M18Namespace, canonical_json


M18_PLAN_REPAIR_RERUN_ID = "m18_plan_repair_rerun_v1"
M18_PLAN_REPAIR_CONDITION_ID = "m18_plan_provider_contract_repair_v1"
M18_PLAN_REPAIR_COMMIT = "1edd890cbc9afe1f75af845be8fd4069ef9f9768"
M18_PLAN_REPAIR_PRE_REPAIR_COMMIT = "fbf98fa54c26c9cd8ab3c9cbfa3d550f92e5abac"
M18_PLAN_REPAIR_NAMESPACE = "m18_plan_provider_contract_repair_v1"
M18_PLAN_REPAIR_RESULT_DIRECTORY = Path("evaluation") / "m18" / "results" / "repair"
M18_PLAN_REPAIR_MANIFEST_PATH = Path("evaluation") / "m18" / "manifests" / "plan_repair_rerun_v1.json"
M18_PLAN_REPAIR_RESULT_SCHEMA_VERSION = "m18_plan_repair_result_v1"
M18_PLAN_REPAIR_STOP_FILENAME = "repair_stop_event.json"
M18_HISTORICAL_PLAN_ARTIFACT = "0c0decad89793d2b8b1b9d943febd23b9b377759"


def _hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class M18PlanRepairRunSpec:
    """One replacement identity linked immutably to a historical Plan run."""

    original_run_id: str
    case_id: str
    repetition: int
    provider_config_hash: str
    repaired_condition_id: str = M18_PLAN_REPAIR_CONDITION_ID
    repair_manifest_id: str = M18_PLAN_REPAIR_RERUN_ID
    repair_commit: str = M18_PLAN_REPAIR_COMMIT
    source_system_condition: str = "plan_and_execute"
    source_experiment_namespace: str = M18_PILOT_EXPERIMENT_NAMESPACE
    source_tranche_id: str = M18_PILOT_TRANCHE_ID

    def __post_init__(self) -> None:
        if (not isinstance(self.original_run_id, str) or len(self.original_run_id) != 64
                or not isinstance(self.case_id, str) or not self.case_id.startswith("pilot.")
                or self.source_system_condition != "plan_and_execute"
                or not 1 <= self.repetition <= M18_FORMAL_REPETITIONS
                or not isinstance(self.provider_config_hash, str) or len(self.provider_config_hash) != 64
                or self.repaired_condition_id != M18_PLAN_REPAIR_CONDITION_ID
                or self.repair_manifest_id != M18_PLAN_REPAIR_RERUN_ID
                or self.repair_commit != M18_PLAN_REPAIR_COMMIT
                or self.source_experiment_namespace != M18_PILOT_EXPERIMENT_NAMESPACE
                or self.source_tranche_id != M18_PILOT_TRANCHE_ID):
            raise ValueError("invalid repaired Plan run provenance")

    @property
    def repaired_run_id(self) -> str:
        return _hash({
            "identity_version": "m18_plan_repaired_run_v1",
            "original_run_id": self.original_run_id,
            "case_id": self.case_id,
            "system_condition": self.source_system_condition,
            "repetition": self.repetition,
            "repaired_condition_id": self.repaired_condition_id,
            "repair_manifest_id": self.repair_manifest_id,
            "repair_commit": self.repair_commit,
            "provider_config_hash": self.provider_config_hash,
        })

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "repaired_run_id": self.repaired_run_id}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "M18PlanRepairRunSpec":
        required = {
            "original_run_id", "repaired_run_id", "case_id", "repetition", "provider_config_hash",
            "repaired_condition_id", "repair_manifest_id", "repair_commit", "source_system_condition",
            "source_experiment_namespace", "source_tranche_id",
        }
        if set(value) != required:
            raise ValueError("repair run schema mismatch")
        item = cls(**{key: value[key] for key in required if key != "repaired_run_id"})
        if value["repaired_run_id"] != item.repaired_run_id:
            raise ValueError("repaired run identity mismatch")
        return item


@dataclass(frozen=True)
class M18PlanRepairManifest:
    manifest_id: str
    repair_commit: str
    pre_repair_execution_baseline: str
    source_experiment_namespace: str
    source_tranche_id: str
    repaired_condition_id: str
    system_condition: str
    case_ids: tuple[str, ...]
    repetitions: tuple[int, ...]
    expected_run_count: int
    provider_config_hash: str
    harness_identity: str
    result_namespace: str
    original_run_linkage_policy: str
    repaired_run_id_derivation: str
    replacement_identity_set_hash: str
    manifest_hash: str

    def core_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id, "repair_commit": self.repair_commit,
            "pre_repair_execution_baseline": self.pre_repair_execution_baseline,
            "source_experiment_namespace": self.source_experiment_namespace,
            "source_tranche_id": self.source_tranche_id,
            "repaired_condition_id": self.repaired_condition_id, "system_condition": self.system_condition,
            "case_ids": list(self.case_ids), "repetitions": list(self.repetitions),
            "expected_run_count": self.expected_run_count, "provider_config_hash": self.provider_config_hash,
            "harness_identity": self.harness_identity, "result_namespace": self.result_namespace,
            "original_run_linkage_policy": self.original_run_linkage_policy,
            "repaired_run_id_derivation": self.repaired_run_id_derivation,
            "replacement_identity_set_hash": self.replacement_identity_set_hash,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.core_dict(), "manifest_hash": self.manifest_hash}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "M18PlanRepairManifest":
        required = {
            "manifest_id", "repair_commit", "pre_repair_execution_baseline", "source_experiment_namespace",
            "source_tranche_id", "repaired_condition_id", "system_condition", "case_ids", "repetitions",
            "expected_run_count", "provider_config_hash", "harness_identity", "result_namespace",
            "original_run_linkage_policy", "repaired_run_id_derivation", "replacement_identity_set_hash", "manifest_hash",
        }
        if set(value) != required:
            raise M18FrozenArtifactValidationError("repair rerun manifest schema mismatch")
        try:
            manifest = cls(
                value["manifest_id"], value["repair_commit"], value["pre_repair_execution_baseline"],
                value["source_experiment_namespace"], value["source_tranche_id"], value["repaired_condition_id"],
                value["system_condition"], tuple(value["case_ids"]), tuple(value["repetitions"]),
                value["expected_run_count"], value["provider_config_hash"], value["harness_identity"],
                value["result_namespace"], value["original_run_linkage_policy"], value["repaired_run_id_derivation"],
                value["replacement_identity_set_hash"], value["manifest_hash"],
            )
        except (TypeError, ValueError) as error:
            raise M18FrozenArtifactValidationError("repair rerun manifest value mismatch") from error
        if manifest.manifest_hash != _hash(manifest.core_dict()):
            raise M18FrozenArtifactValidationError("repair rerun manifest hash mismatch")
        return manifest


def _repair_spec(source: M18RunSpec) -> M18PlanRepairRunSpec:
    return M18PlanRepairRunSpec(source.run_id, source.case_id, source.repetition, source.provider_config_hash)


@dataclass(frozen=True)
class M18PlanRepairPlan:
    repository_root: Path
    manifest: M18PlanRepairManifest
    specs: tuple[M18PlanRepairRunSpec, ...]
    cases: tuple[M18Case, ...]

    @classmethod
    def from_repository(cls, repository_root: Path) -> "M18PlanRepairPlan":
        root = repository_root.resolve()
        pilot = M18FrozenPilotPlan.from_repository(root)
        tranche = M18OperationalTranchePlan.from_pilot_plan(pilot)
        raw = _read_json(root / M18_PLAN_REPAIR_MANIFEST_PATH)
        if not isinstance(raw, Mapping):
            raise M18FrozenArtifactValidationError("repair rerun manifest must be an object")
        manifest = M18PlanRepairManifest.from_dict(raw)
        expected = tuple(_repair_spec(spec) for spec in tranche.specs if spec.system_condition == "plan_and_execute")
        selected = tuple(case for case in pilot.cases if case.case_id in manifest.case_ids)
        plan = cls(root, manifest, expected, selected)
        plan.validate_admission()
        return plan

    @property
    def result_root(self) -> Path:
        return self.repository_root / M18_PLAN_REPAIR_RESULT_DIRECTORY / M18_PLAN_REPAIR_NAMESPACE

    @property
    def historical_root(self) -> Path:
        return self.repository_root / M18_PILOT_RESULT_DIRECTORY / M18_PILOT_EXPERIMENT_NAMESPACE

    def validate_admission(self) -> None:
        m = self.manifest
        if (
            m.manifest_id != M18_PLAN_REPAIR_RERUN_ID
            or m.repair_commit != M18_PLAN_REPAIR_COMMIT
            or m.pre_repair_execution_baseline != M18_PLAN_REPAIR_PRE_REPAIR_COMMIT
            or m.source_experiment_namespace != M18_PILOT_EXPERIMENT_NAMESPACE
            or m.source_tranche_id != M18_PILOT_TRANCHE_ID
            or m.repaired_condition_id != M18_PLAN_REPAIR_CONDITION_ID
            or m.system_condition != "plan_and_execute"
            or m.repetitions != tuple(range(1, M18_FORMAL_REPETITIONS + 1))
            or m.expected_run_count != 60
            or m.provider_config_hash != M18SharedProviderConfiguration().config_hash
            or m.harness_identity != harness_identity()
            or m.result_namespace != M18_PLAN_REPAIR_NAMESPACE
            or m.result_namespace == M18_PILOT_EXPERIMENT_NAMESPACE
            or len(m.case_ids) != 12 or len(set(m.case_ids)) != 12
            or len(self.specs) != 60
            or len(self.cases) != 12
            or len({item.repaired_run_id for item in self.specs}) != 60
            or len({item.original_run_id for item in self.specs}) != 60
            or {item.case_id for item in self.specs} != set(m.case_ids)
            or {item.case_id for item in self.cases} != set(m.case_ids)
            or any(item.namespace is not M18Namespace.PILOT for item in self.cases)
            or {item.repetition for item in self.specs} != set(m.repetitions)
            or any(item.repaired_run_id == item.original_run_id for item in self.specs)
            or m.replacement_identity_set_hash != _hash([item.to_dict() for item in self.specs])
            or m.manifest_hash != _hash(m.core_dict())
        ):
            raise M18FrozenArtifactValidationError("repair rerun manifest admission mismatch")

    @property
    def cases_by_id(self) -> Mapping[str, M18Case]:
        return {item.case_id: item for item in self.cases}

    def dry_run(self) -> dict[str, int | bool]:
        self.validate_admission()
        return {
            "repair_identities": len(self.specs), "original_historical_identities": len(self.specs),
            "collisions": len({item.repaired_run_id for item in self.specs} & {item.original_run_id for item in self.specs}),
            "one_to_one_linkage": len({item.original_run_id for item in self.specs}) == len(self.specs),
        }


@dataclass(frozen=True)
class M18PlanRepairRunRecord:
    """Schema for future repaired evidence, with all pairing provenance explicit."""

    repaired_run_id: str
    original_run_id: str
    case_id: str
    system_condition: str
    repetition: int
    source_experiment_namespace: str
    source_tranche_id: str
    repaired_condition_id: str
    repair_manifest_id: str
    repair_manifest_hash: str
    repair_commit: str
    provider_config_hash: str
    harness_identity: str
    execution_baseline: str
    result_namespace: str
    runtime_terminal_outcome: str
    evaluator_outcome: str | None
    neutral_failure_category: str
    budget: M18BudgetCounters
    infrastructure_valid: bool
    provider_model: str | None = None
    token_telemetry: Mapping[str, int | None] | None = None
    latency_ms: int | None = None
    raw_artifact_references: tuple[str, ...] = ()
    result_schema_version: str = M18_PLAN_REPAIR_RESULT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["budget"] = self.budget.to_dict()
        value["token_telemetry"] = dict(self.token_telemetry) if self.token_telemetry is not None else None
        value["raw_artifact_references"] = list(self.raw_artifact_references)
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "M18PlanRepairRunRecord":
        expected = set(cls.__dataclass_fields__)
        if set(value) != expected or not isinstance(value.get("budget"), Mapping):
            raise ValueError("repair result schema mismatch")
        telemetry, refs = value["token_telemetry"], value["raw_artifact_references"]
        if telemetry is not None and not isinstance(telemetry, Mapping):
            raise ValueError("repair token telemetry mismatch")
        if not isinstance(refs, list) or any(not isinstance(item, str) for item in refs):
            raise ValueError("repair references mismatch")
        return cls(**{**dict(value), "budget": M18BudgetCounters(**dict(value["budget"])),
                      "token_telemetry": dict(telemetry) if telemetry is not None else None,
                      "raw_artifact_references": tuple(refs)})

    @classmethod
    def from_harness_record(cls, spec: M18PlanRepairRunSpec, manifest: M18PlanRepairManifest,
                            execution_baseline: str, record: M18RunRecord) -> "M18PlanRepairRunRecord":
        return cls(spec.repaired_run_id, spec.original_run_id, spec.case_id, "plan_and_execute", spec.repetition,
                   spec.source_experiment_namespace, spec.source_tranche_id, spec.repaired_condition_id,
                   spec.repair_manifest_id, manifest.manifest_hash, spec.repair_commit,
                   spec.provider_config_hash, manifest.harness_identity, execution_baseline,
                   manifest.result_namespace, record.runtime_terminal_outcome, record.evaluator_outcome,
                   record.neutral_failure_category, record.budget, record.infrastructure_valid,
                   record.provider_model, record.token_telemetry, record.latency_ms,
                   record.raw_artifact_references)


class M18PlanRepairResultStore:
    """Fail-closed dedicated repair storage; historical pilot storage is forbidden."""

    def __init__(self, root: Path, plan: M18PlanRepairPlan) -> None:
        plan.validate_admission()
        if root.resolve() != plan.result_root.resolve() or root.resolve() == plan.historical_root.resolve():
            raise ValueError("repair result namespace mismatch")
        self.root, self.plan = root, plan
        self.root.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self.root / "repair_run_manifest.json"
        value = plan.manifest.to_dict()
        if self._manifest_path.exists():
            if _read_json(self._manifest_path) != value:
                raise ValueError("repair manifest drift")
        else:
            self._atomic(self._manifest_path, value)

    def _atomic(self, path: Path, value: Mapping[str, Any]) -> None:
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=self.root, suffix=".tmp") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            handle.write("\n")
            temporary = Path(handle.name)
        temporary.replace(path)

    def _validate(self, record: M18PlanRepairRunRecord) -> None:
        m = self.plan.manifest
        spec = {item.repaired_run_id: item for item in self.plan.specs}.get(record.repaired_run_id)
        if spec is None or record.repaired_run_id == record.original_run_id:
            raise ValueError("repair run identity is not admitted")
        if (
            record.original_run_id != spec.original_run_id or record.case_id != spec.case_id
            or record.system_condition != "plan_and_execute" or record.repetition != spec.repetition
            or record.source_experiment_namespace != m.source_experiment_namespace
            or record.source_tranche_id != m.source_tranche_id
            or record.repaired_condition_id != m.repaired_condition_id
            or record.repair_manifest_id != m.manifest_id or record.repair_manifest_hash != m.manifest_hash
            or record.repair_commit != m.repair_commit or record.provider_config_hash != m.provider_config_hash
            or record.harness_identity != m.harness_identity or record.result_namespace != m.result_namespace
            or record.result_schema_version != M18_PLAN_REPAIR_RESULT_SCHEMA_VERSION
            or not isinstance(record.execution_baseline, str) or len(record.execution_baseline) != 40
        ):
            raise ValueError("repair record provenance mismatch")

    def persist(self, record: M18PlanRepairRunRecord) -> None:
        self._validate(record)
        path = self.root / (record.repaired_run_id + ".json")
        if path.exists():
            raise FileExistsError("duplicate repaired run id")
        self._atomic(path, record.to_dict())

    def completed_ids(self) -> frozenset[str]:
        found: set[str] = set()
        for path in sorted(self.root.glob("*.json")):
            if path.name in {"repair_run_manifest.json", M18_PLAN_REPAIR_STOP_FILENAME}:
                continue
            try:
                record = M18PlanRepairRunRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise ValueError("repair stored record corruption") from error
            if path.stem != record.repaired_run_id or record.repaired_run_id in found:
                raise ValueError("duplicate or mismatched repaired record")
            self._validate(record)
            found.add(record.repaired_run_id)
        return frozenset(found)

    def missing(self) -> tuple[M18PlanRepairRunSpec, ...]:
        completed = self.completed_ids()
        return tuple(item for item in self.plan.specs if item.repaired_run_id not in completed)


class M18PlanRepairRerun:
    """The only repaired-Plan execution surface; never writes pilot identities."""

    def __init__(self, plan: M18PlanRepairPlan) -> None:
        self.plan = plan

    @classmethod
    def from_repository(cls, repository_root: Path) -> "M18PlanRepairRerun":
        return cls(M18PlanRepairPlan.from_repository(repository_root))

    @property
    def result_root(self) -> Path:
        return self.plan.result_root

    def dry_run(self) -> dict[str, int | bool]:
        return self.plan.dry_run()

    def result_store(self, root: Path | None = None) -> M18PlanRepairResultStore:
        return M18PlanRepairResultStore(root or self.result_root, self.plan)

    def _raise_stop(self, category: M18OperationalStopCategory, stage: str, detail: str,
                    *, repaired_run_id: str | None = None, persist: bool = True) -> None:
        event = M18OperationalStopEvent(category, stage, category.value, detail, repaired_run_id)
        if persist:
            root = self.result_root
            root.mkdir(parents=True, exist_ok=True)
            path = root / M18_PLAN_REPAIR_STOP_FILENAME
            if not path.exists():
                self._atomic_stop(path, event)
        raise M18OperationalStopCondition(event)

    @staticmethod
    def _atomic_stop(path: Path, event: M18OperationalStopEvent) -> None:
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
            json.dump(event.to_dict(), handle, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            handle.write("\n")
            temporary = Path(handle.name)
        temporary.replace(path)

    def _assert_no_prior_stop(self) -> None:
        path = self.result_root / M18_PLAN_REPAIR_STOP_FILENAME
        if path.exists():
            self._raise_stop(M18OperationalStopCategory.PERSISTENCE_INTEGRITY_FAILURE, "resume",
                             "prior_integrity_stop_requires_explicit_operator_resolution", persist=False)

    def _frozen_binding(self, environment: Mapping[str, str] | None) -> M18FrozenProviderBinding:
        return M18FrozenProviderBinding(M18SharedProviderClient(environment=environment))

    @staticmethod
    def _original_spec(spec: M18PlanRepairRunSpec) -> M18RunSpec:
        return M18RunSpec("m18_suite_v1", spec.case_id, "plan_and_execute", spec.repetition,
                          spec.provider_config_hash)

    def _execute_specs(self, store: M18PlanRepairResultStore,
                       specs: tuple[M18PlanRepairRunSpec, ...], execution_baseline: str,
                       binding_factory) -> tuple[M18PlanRepairRunRecord, ...]:
        """Execute admitted repair identities; persistence keys are repaired IDs only."""
        records: list[M18PlanRepairRunRecord] = []
        for spec in specs:
            case = self.plan.cases_by_id.get(spec.case_id)
            if case is None or case.namespace is not M18Namespace.PILOT:
                self._raise_stop(M18OperationalStopCategory.PROVENANCE_INTEGRITY_FAILURE, "case_admission",
                                 "repair_case_not_admitted", repaired_run_id=spec.repaired_run_id)
            try:
                binding = binding_factory()
                if not isinstance(binding, M18FrozenProviderBinding):
                    raise TypeError("repair execution requires frozen provider binding")
                harness = M18SharedExecutionHarness(
                    spec.provider_config_hash, max_steps=3, max_tool_calls=1,
                    mode=M18ExecutionMode.FROZEN, frozen_binding=binding,
                )
            except M18OperationalStopCondition:
                raise
            except Exception as error:
                self._raise_stop(M18OperationalStopCategory.PROVIDER_CONFIG_DRIFT, "provider_preflight",
                                 type(error).__name__, repaired_run_id=spec.repaired_run_id)
            try:
                # The original spec is internal-only. It is never persisted or used as completion identity.
                internal = harness.run_frozen_pilot(self._original_spec(spec), case,
                                                     tranche_id=spec.source_tranche_id)
            except M18ExecutionIntegrityError as error:
                try:
                    category = M18OperationalStopCategory(error.category)
                except ValueError:
                    category = M18OperationalStopCategory.PROVENANCE_INTEGRITY_FAILURE
                self._raise_stop(category, error.stage, error.detail, repaired_run_id=spec.repaired_run_id)
            references = set(internal.raw_artifact_references)
            if "m18_plan_provider:model_identity_mismatch" in references:
                self._raise_stop(M18OperationalStopCategory.PROVIDER_IDENTITY_DRIFT, "provider_decode",
                                 "model_identity_mismatch", repaired_run_id=spec.repaired_run_id)
            if "m18_plan_provider:malformed_json" in references:
                self._raise_stop(M18OperationalStopCategory.PROVIDER_DECODER_INCOMPATIBILITY, "provider_decode",
                                 "malformed_json", repaired_run_id=spec.repaired_run_id)
            repaired = M18PlanRepairRunRecord.from_harness_record(spec, self.plan.manifest,
                                                                    execution_baseline, internal)
            try:
                store.persist(repaired)
            except Exception as error:
                self._raise_stop(M18OperationalStopCategory.PERSISTENCE_INTEGRITY_FAILURE, "persistence",
                                 type(error).__name__, repaired_run_id=spec.repaired_run_id)
            records.append(repaired)
        return tuple(records)

    def execute(self, execution_baseline: str, *, environment: Mapping[str, str] | None = None) -> tuple[M18PlanRepairRunRecord, ...]:
        """Execute missing repaired identities only, using the unchanged frozen provider contract."""
        if not isinstance(execution_baseline, str) or len(execution_baseline) != 40:
            raise ValueError("execution baseline must be a commit hash")
        self.plan.validate_admission()
        self._assert_no_prior_stop()
        try:
            store = self.result_store()
            missing = store.missing()
        except M18OperationalStopCondition:
            raise
        except Exception as error:
            self._raise_stop(M18OperationalStopCategory.PROVENANCE_INTEGRITY_FAILURE, "resume",
                             type(error).__name__)
        return self._execute_specs(store, missing, execution_baseline,
                                   lambda: self._frozen_binding(environment))

    def stop_for_integrity_failure(self, category: M18OperationalStopCategory, stage: str, detail: str) -> None:
        if category not in {
            M18OperationalStopCategory.PROVIDER_IDENTITY_DRIFT,
            M18OperationalStopCategory.PROVIDER_CONFIG_DRIFT,
            M18OperationalStopCategory.FROZEN_ARTIFACT_DRIFT,
            M18OperationalStopCategory.NAMESPACE_INTEGRITY_FAILURE,
            M18OperationalStopCategory.PROVENANCE_INTEGRITY_FAILURE,
            M18OperationalStopCategory.PERSISTENCE_INTEGRITY_FAILURE,
            M18OperationalStopCategory.EVALUATOR_INVARIANT_FAILURE,
            M18OperationalStopCategory.ENVIRONMENT_INVARIANT_FAILURE,
            M18OperationalStopCategory.PROVIDER_DECODER_INCOMPATIBILITY,
        }:
            raise ValueError("unsupported repair stop category")
        self._raise_stop(category, stage, detail, persist=False)


def historical_plan_record_digest(root: Path) -> tuple[int, str]:
    """Read-only digest for the historical Plan subset; never writes records."""
    values: list[tuple[str, str]] = []
    for path in sorted(root.glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if value.get("system_condition") == "plan_and_execute":
            values.append((path.name, sha256(path.read_bytes()).hexdigest()))
    return len(values), _hash(values)
