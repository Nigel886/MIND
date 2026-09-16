"""Explicit, provenance-safe execution surface for the frozen M18 v2 pilot.

Imports and dry-run inspection are provider-free.  Real execution is reachable
only through ``M18V2PilotRunner.execute`` or the CLI ``--execute`` flag.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Mapping

from src.evaluation.m18_shared_provider import (
    M18SharedDirectProvider, M18SharedMINDProvider, M18SharedPlanProvider,
    M18SharedProviderClient, M18SharedProviderConfiguration,
    M18SharedReActProvider,
)
from src.evaluation.m18_task_generation import (
    M18Cohort, M18Difficulty, M18FailureSubtype, M18Namespace, canonical_hash,
    canonical_json,
)
from src.evaluation.m18_v2_provenance import (
    M18V2ResultAdmission, M18V2ResultRecord, M18V2RunProvenance,
    M18_V2_COMPARATOR_CONDITIONS, M18_V2_RUNTIME_ID,
    project_m18_v2_run_provenances,
)
from src.evaluation.m18_v2_runtime import (
    M18BenchmarkRuntimeCondition, M18V2ResultProvenance,
    M18V2RuntimeTerminal, M18V2SharedExecutionHarness,
    m18_v2_concrete_adapters,
)
from src.evaluation.m18_v2_semantics import (
    M18V2Case, M18V2EvaluatorFixture, M18V2EvaluationCategory,
    M18V2PublicCase, M18_V2_BUDGET_ID, M18_V2_ENVIRONMENT_ID,
    M18_V2_EVALUATOR_ID, M18_V2_SUITE_VERSION,
)


M18_V2_PILOT_RESULT_NAMESPACE = Path("evaluation/m18/results/v2/pilot/m18_suite_v2")
M18_V2_FORMAL_RESULT_NAMESPACE = Path("evaluation/m18/results/v2/formal/m18_suite_v2")
M18_V2_PILOT_STORE_MANIFEST = "m18_v2_pilot_store_manifest.json"
M18_V2_FREEZE_BASELINE = "59506751b66f22bed5106db68a51b1089975c419"


class M18V2PilotIntegrityError(RuntimeError):
    """Typed fail-closed error; it is never converted into agent performance."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise M18V2PilotIntegrityError(f"invalid frozen artifact: {path.name}") from error


def _case_from_private(value: Mapping[str, Any]) -> M18V2Case:
    try:
        public = value["public"]
        evaluator = value["evaluator"]
        result = M18V2Case(
            value["case_id"], M18Namespace(value["namespace"]),
            M18Cohort(value["cohort"]), M18Difficulty(value["difficulty"]),
            value["generation_seed"],
            M18V2PublicCase(public["case_id"], public["task_text"],
                            tuple(public["capabilities"]), public["task_config"]),
            M18V2EvaluatorFixture(evaluator["expected_final_result"], evaluator["evaluator_id"]),
            M18FailureSubtype(value["failure_subtype"]) if value["failure_subtype"] else None,
            value["suite_version"], value["environment_id"], value["evaluator_id"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise M18V2PilotIntegrityError("invalid frozen v2 private case") from error
    if canonical_json(result.to_dict()) != canonical_json(dict(value)):
        raise M18V2PilotIntegrityError("frozen v2 case canonical representation mismatch")
    return result


@dataclass(frozen=True)
class M18V2PilotPlan:
    """A frozen-file-only pilot plan; it has no formal or dynamic-discovery path."""

    repository_root: Path
    cases: tuple[M18V2Case, ...]
    expected: tuple[M18V2RunProvenance, ...]
    suite_manifest: Mapping[str, Any]
    split_manifest: Mapping[str, Any]

    @classmethod
    def from_repository(cls, repository_root: Path) -> "M18V2PilotPlan":
        root = repository_root.resolve()
        suite_root = root / "evaluation/m18/suites_v2"
        manifest = _read_json(suite_root / "manifests/m18_suite_v2_manifest.json")
        split = _read_json(suite_root / "manifests/m18_suite_v2_split.json")
        public = _read_json(suite_root / "pilot/public_cases.json")
        private = _read_json(suite_root / "pilot/private_cases.json")
        formal = _read_json(suite_root / "formal/private_cases.json")
        if not all(isinstance(value, list) for value in (public, private, formal)) or not isinstance(manifest, Mapping) or not isinstance(split, Mapping):
            raise M18V2PilotIntegrityError("frozen v2 artifact top-level schema mismatch")
        if (manifest.get("suite_identity"), manifest.get("environment_id"),
                manifest.get("evaluator_id"), manifest.get("budget_id"),
                manifest.get("runtime_id")) != (
                    M18_V2_SUITE_VERSION, M18_V2_ENVIRONMENT_ID,
                    M18_V2_EVALUATOR_ID, M18_V2_BUDGET_ID, M18_V2_RUNTIME_ID):
            raise M18V2PilotIntegrityError("frozen v2 identity mismatch")
        if canonical_hash({key: value for key, value in manifest.items() if key != "manifest_hash"}) != manifest.get("manifest_hash"):
            raise M18V2PilotIntegrityError("frozen v2 suite manifest hash mismatch")
        if canonical_hash({key: value for key, value in split.items() if key != "split_hash"}) != split.get("split_hash") or split.get("split_hash") != manifest.get("split_manifest_hash"):
            raise M18V2PilotIntegrityError("frozen v2 split manifest hash mismatch")
        if manifest.get("comparator_conditions") != M18_V2_COMPARATOR_CONDITIONS or manifest.get("repetitions") != [1, 2, 3, 4, 5]:
            raise M18V2PilotIntegrityError("frozen v2 comparator or repetition mismatch")
        if manifest.get("provider_config_hash") != M18SharedProviderConfiguration().config_hash:
            raise M18V2PilotIntegrityError("frozen v2 provider configuration mismatch")
        if len(public) != 18 or len(private) != 18 or len(formal) != 162:
            raise M18V2PilotIntegrityError("frozen v2 split case count mismatch")
        if canonical_hash(public) != manifest["pilot"]["public_hash"] or canonical_hash(private) != manifest["pilot"]["private_hash"]:
            raise M18V2PilotIntegrityError("frozen v2 pilot fixture hash mismatch")
        cases = tuple(_case_from_private(item) for item in private if isinstance(item, Mapping))
        if len(cases) != 18 or [item.case_id for item in cases] != split.get("pilot_ids"):
            raise M18V2PilotIntegrityError("frozen v2 pilot membership/order mismatch")
        if set(split.get("pilot_ids", ())) & set(split.get("formal_ids", ())):
            raise M18V2PilotIntegrityError("frozen v2 split overlaps")
        if [item["case_id"] for item in public] != [item.case_id for item in cases] or any(item["public"] != public[index] for index, item in enumerate(private)):
            raise M18V2PilotIntegrityError("frozen v2 public/private projection mismatch")
        expected = project_m18_v2_run_provenances(
            split["pilot_ids"], tuple(manifest["comparator_conditions"].values()),
            manifest["provider_config_hash"], M18_V2_FREEZE_BASELINE,
            manifest["repetitions"],
        )
        if len(expected) != 360 or len({item.run_id for item in expected}) != 360 or manifest.get("pilot_run_count") != 360:
            raise M18V2PilotIntegrityError("frozen v2 pilot run-universe mismatch")
        return cls(root, cases, expected, dict(manifest), dict(split))

    @property
    def cases_by_id(self) -> Mapping[str, M18V2Case]:
        return {case.case_id: case for case in self.cases}

    @property
    def result_root(self) -> Path:
        return self.repository_root / M18_V2_PILOT_RESULT_NAMESPACE


class M18V2PilotResultStore:
    """Atomic, fail-closed store for exactly one frozen v2 pilot universe."""

    def __init__(self, root: Path, expected: tuple[M18V2RunProvenance, ...], manifest: Mapping[str, Any]) -> None:
        self.root, self.expected, self.manifest = root, expected, dict(manifest)
        self._expected_by_id = {item.run_id: item for item in expected}
        if len(self._expected_by_id) != len(expected):
            raise M18V2PilotIntegrityError("duplicate expected v2 pilot run ID")

    @property
    def manifest_path(self) -> Path:
        return self.root / M18_V2_PILOT_STORE_MANIFEST

    def _store_manifest(self) -> dict[str, Any]:
        return {"store_schema": "m18_v2_pilot_store_v1", "suite_manifest_hash": self.manifest["manifest_hash"],
                "split_manifest_hash": self.manifest["split_manifest_hash"],
                "execution_baseline": M18_V2_FREEZE_BASELINE,
                "expected_run_ids": [item.run_id for item in self.expected]}

    @staticmethod
    def _atomic(path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
            handle.write(canonical_json(dict(value)) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        try:
            if path.exists():
                raise FileExistsError("no-overwrite result persistence violation")
            os.replace(temporary, path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def initialize(self) -> None:
        value = self._store_manifest()
        if self.manifest_path.exists():
            if _read_json(self.manifest_path) != value:
                raise M18V2PilotIntegrityError("v2 pilot store manifest drift")
        else:
            self._atomic(self.manifest_path, value)

    def _parse_records(self) -> tuple[M18V2ResultRecord, ...]:
        if not self.root.exists():
            return ()
        records: list[M18V2ResultRecord] = []
        for path in sorted(self.root.glob("*.json")):
            if path.name == M18_V2_PILOT_STORE_MANIFEST:
                continue
            try:
                record = M18V2ResultRecord.from_dict(_read_json(path))
            except Exception as error:
                raise M18V2PilotIntegrityError(f"invalid v2 pilot result: {path.name}") from error
            if path.stem != record.run_id:
                raise M18V2PilotIntegrityError("result filename/run-ID mismatch")
            records.append(record)
        admission = M18V2ResultAdmission(self.expected)
        try:
            for record in records:
                admission.admit(record)
        except Exception as error:
            raise M18V2PilotIntegrityError("v2 pilot result admission failed") from error
        return tuple(records)

    def records(self) -> tuple[M18V2ResultRecord, ...]:
        return self._parse_records()

    def completed_ids(self) -> frozenset[str]:
        return frozenset(record.run_id for record in self.records())

    def missing(self) -> tuple[M18V2RunProvenance, ...]:
        completed = self.completed_ids()
        return tuple(item for item in self.expected if item.run_id not in completed)

    def persist(self, record: M18V2ResultRecord) -> M18V2ResultRecord:
        # Scan first: invalid, unexpected, duplicate, and filename mismatches stop.
        completed = self.completed_ids()
        if record.run_id in completed:
            raise M18V2PilotIntegrityError("duplicate v2 pilot completed run")
        try:
            M18V2ResultAdmission(self.expected).admit(record)
        except Exception as error:
            raise M18V2PilotIntegrityError("v2 pilot record provenance mismatch") from error
        path = self.root / (record.run_id + ".json")
        if path.exists():
            raise M18V2PilotIntegrityError("duplicate v2 pilot result path")
        self._atomic(path, record.to_dict())
        reread = M18V2ResultRecord.from_dict(_read_json(path))
        try:
            M18V2ResultAdmission(self.expected).admit(reread)
        except Exception as error:
            raise M18V2PilotIntegrityError("persisted v2 pilot record failed re-read admission") from error
        return reread

    def digest(self) -> str:
        records = self.records()
        return canonical_hash([record.to_dict() for record in sorted(records, key=lambda item: item.run_id)])


@dataclass(frozen=True)
class M18V2PilotDryRun:
    suite_identity: str
    split: str
    expected: int
    valid_existing: int
    missing: int
    per_comparator: Mapping[str, int]
    per_repetition: Mapping[int, int]


ProviderFactory = Callable[[str], Any]


class M18V2PilotRunner:
    """Pilot-only runner; formal execution is structurally absent."""

    def __init__(self, plan: M18V2PilotPlan, *, result_root: Path | None = None) -> None:
        if not isinstance(plan, M18V2PilotPlan):
            raise TypeError("M18V2PilotPlan required")
        self.plan = plan
        self.result_root = plan.result_root if result_root is None else result_root
        self.store = M18V2PilotResultStore(self.result_root, plan.expected, plan.suite_manifest)

    @classmethod
    def from_repository(cls, repository_root: Path, *, result_root: Path | None = None) -> "M18V2PilotRunner":
        return cls(M18V2PilotPlan.from_repository(repository_root), result_root=result_root)

    def dry_run(self) -> M18V2PilotDryRun:
        records = self.store.records()
        missing = self.store.missing()
        return M18V2PilotDryRun(
            self.plan.suite_manifest["suite_identity"], "pilot", len(self.plan.expected),
            len(records), len(missing),
            {system: sum(item.identity.comparator_condition_id == condition for item in self.plan.expected)
             for system, condition in self.plan.suite_manifest["comparator_conditions"].items()},
            {repetition: sum(item.identity.repetition == repetition for item in self.plan.expected)
             for repetition in self.plan.suite_manifest["repetitions"]},
        )

    @staticmethod
    def _production_provider(system: str) -> Any:
        client = M18SharedProviderClient()
        return {"mind_lite_v11": M18SharedMINDProvider,
                "direct_tool_calling": M18SharedDirectProvider,
                "react": M18SharedReActProvider,
                "plan_and_execute": M18SharedPlanProvider}[system](client)

    @staticmethod
    def _record(result: Any) -> M18V2ResultRecord:
        outcome = result.evaluator_outcome.value if result.evaluator_outcome is not None else None
        failure = None if outcome == M18V2EvaluationCategory.SUCCESS.value else result.terminal.value
        return M18V2ResultRecord(
            result.run_provenance, outcome, failure,
            {"logical_provider_calls": result.logical_provider_calls,
             "transport_attempts": result.transport_attempts}, None,
        )

    def execute(self, *, provider_factory: ProviderFactory | None = None,
                after_persist: Callable[[M18V2ResultRecord], None] | None = None,
                limit: int | None = None) -> tuple[M18V2ResultRecord, ...]:
        """Execute missing pilot identities only; caller must provide explicit authority."""
        self.store.initialize()
        factory = self._production_provider if provider_factory is None else provider_factory
        completed: list[M18V2ResultRecord] = []
        for expected in self.store.missing()[:limit]:
            system = next(key for key, value in self.plan.suite_manifest["comparator_conditions"].items()
                          if value == expected.identity.comparator_condition_id)
            providers = {key: factory(key) for key in self.plan.suite_manifest["comparator_conditions"]}
            adapter = m18_v2_concrete_adapters(providers)[system]
            runtime_condition = M18BenchmarkRuntimeCondition.v2()
            runtime = M18V2SharedExecutionHarness(
                runtime_condition,
                M18V2ResultProvenance(runtime_condition, M18_V2_RUNTIME_ID,
                                      expected.provider_config_hash,
                                      expected.identity.comparator_condition_id),
            )
            case = self.plan.cases_by_id[expected.identity.case_id]
            try:
                result = runtime.dry_run(case, adapter, repetition=expected.identity.repetition,
                                         execution_baseline=expected.execution_baseline,
                                         run_provenance=expected)
            except Exception as error:
                raise M18V2PilotIntegrityError("concrete v2 pilot execution failed before result admission") from error
            record = self.store.persist(self._record(result))
            completed.append(record)
            if after_persist is not None:
                after_persist(record)
        return tuple(completed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M18 v2 pilot execution runner")
    parser.add_argument("--suite", default=M18_V2_SUITE_VERSION)
    parser.add_argument("--split", default="pilot")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--result-root", type=Path)
    args = parser.parse_args(argv)
    if args.suite != M18_V2_SUITE_VERSION:
        parser.error("only frozen m18_suite_v2 is accepted")
    if args.split != "pilot":
        parser.error("formal and all-split execution are unauthorized")
    runner = M18V2PilotRunner.from_repository(Path("."), result_root=args.result_root)
    if not args.execute:
        print(json.dumps(runner.dry_run().__dict__, sort_keys=True))
        return 0
    runner.execute()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
