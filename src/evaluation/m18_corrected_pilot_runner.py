"""Provider-free preparation and guarded execution path for corrected M18 pilots."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.evaluation.m18_corrected_comparator_contract import (
    M18_CORRECTED_COMPARATOR_CONTRACT_ID, M18_CORRECTED_PILOT_RESULT_NAMESPACE,
    M18CorrectedProvenance, M18CorrectedRecord, M18CorrectedResultStore,
    M18CorrectedRunnerPlan, corrected_namespace_counts, select_corrected_condition,
)
from src.evaluation.m18_v2_pilot_runner import M18V2PilotIntegrityError
from src.evaluation.m18_v2_provider_diagnostics import (
    M18V2ProviderExecutionFailure, M18V2SystematicProviderStop,
    M18V2SystematicProviderStopEvent,
)
from src.evaluation.m18_v3_pilot_runner import M18V3PilotPlan, M18_V3_EXPECTED_MANIFEST_HASH
from src.evaluation.m18_v3_runtime import M18V3SharedExecutionHarness, M18_V3_SYSTEMS, m18_v3_concrete_adapters

M18_CORRECTED_PILOT_STORE_MANIFEST = "m18_corrected_pilot_store_v1.json"
M18_CORRECTED_PILOT_STOP = "m18_corrected_pilot_systematic_provider_stop_v1.json"
ProviderFactory = Callable[[str], Any]


def _json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise M18V2PilotIntegrityError("invalid corrected runner control artifact") from error


@dataclass(frozen=True)
class M18CorrectedPilotPlan:
    repository_root: Path
    v3_plan: M18V3PilotPlan
    corrected: M18CorrectedRunnerPlan

    @classmethod
    def from_repository(cls, root: Path) -> "M18CorrectedPilotPlan":
        v3 = M18V3PilotPlan.from_repository(root)
        corrected = M18CorrectedRunnerPlan.from_v3_plan(v3)
        if len(corrected.expected) != 360 or len({item.run_id for item in corrected.expected}) != 360:
            raise M18V2PilotIntegrityError("corrected pilot universe mismatch")
        if any(item.identity.comparator_contract_id != M18_CORRECTED_COMPARATOR_CONTRACT_ID for item in corrected.expected):
            raise M18V2PilotIntegrityError("corrected contract provenance mismatch")
        return cls(root.resolve(), v3, corrected)

    @property
    def expected(self) -> tuple[M18CorrectedProvenance, ...]:
        return self.corrected.expected

    @property
    def cases_by_id(self):
        return self.v3_plan.cases_by_id


@dataclass(frozen=True)
class M18CorrectedPilotPreflight:
    expected: int
    valid: int
    missing: int
    duplicates: int
    invalid: int
    unexpected: int
    condition: str
    run_id_prefix: str
    run_id_schema: str
    formal_records: int


class M18CorrectedPilotRunner:
    """A pilot-only runner; importing/preflight is provider-free and read-only."""

    def __init__(self, plan: M18CorrectedPilotPlan, *, result_root: Path | None = None) -> None:
        if not isinstance(plan, M18CorrectedPilotPlan):
            raise TypeError("M18CorrectedPilotPlan required")
        self.plan = plan
        root = plan.corrected.pilot_root if result_root is None else result_root
        # The closed admission store distinguishes pilot/formal by its final
        # directory name.  Temporary test roots are normalized into a pilot
        # child without weakening that production namespace invariant.
        if root.name != "pilot":
            root = root / "pilot"
        self.store = M18CorrectedResultStore(root, plan.expected, plan.v3_plan.manifest["manifest_hash"])

    @classmethod
    def from_repository(cls, root: Path, *, result_root: Path | None = None) -> "M18CorrectedPilotRunner":
        return cls(M18CorrectedPilotPlan.from_repository(root), result_root=result_root)

    @property
    def control_root(self) -> Path:
        return self.store.root / "controls"

    @property
    def store_manifest_path(self) -> Path:
        return self.control_root / M18_CORRECTED_PILOT_STORE_MANIFEST

    @property
    def stop_path(self) -> Path:
        return self.control_root / M18_CORRECTED_PILOT_STOP

    def _control_write(self, path: Path, value: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        if temporary.exists():
            temporary.unlink()
        temporary.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        if path.exists():
            if _json(path) != value:
                raise M18V2PilotIntegrityError("corrected control artifact conflict")
            temporary.unlink(missing_ok=True)
            return
        temporary.replace(path)

    def _store_manifest(self) -> dict[str, object]:
        return {
            "store_schema": "m18_corrected_pilot_store_v1",
            "condition": M18_CORRECTED_COMPARATOR_CONTRACT_ID,
            "suite_manifest_hash": self.plan.v3_plan.manifest["manifest_hash"],
            "run_id_schema": self.plan.expected[0].identity.schema,
            "expected_run_ids": [item.run_id for item in self.plan.expected],
        }

    def initialize(self) -> None:
        self._control_write(self.store_manifest_path, self._store_manifest())

    def systematic_stop(self) -> M18V2SystematicProviderStopEvent | None:
        if not self.stop_path.exists():
            return None
        return M18V2SystematicProviderStopEvent.from_dict(_json(self.stop_path))

    def _persist_stop(self, event: M18V2SystematicProviderStopEvent) -> None:
        self._control_write(self.stop_path, event.to_dict())

    def preflight(self) -> M18CorrectedPilotPreflight:
        records = self.store.records()
        ids = [record.run_id for record in records]
        valid = sum(self.store._by_id.get(record.run_id) == record.provenance for record in records)
        pilot_count, formal_count = corrected_namespace_counts(self.plan.repository_root)
        if self.store.root.resolve() == self.plan.corrected.pilot_root.resolve() and pilot_count != len(records):
            raise M18V2PilotIntegrityError("unexpected corrected pilot JSON artifact")
        return M18CorrectedPilotPreflight(
            len(self.plan.expected), valid, len(self.store.missing()), len(ids) - len(set(ids)),
            len(records) - valid, 0, M18_CORRECTED_COMPARATOR_CONTRACT_ID, "m18ccv2-",
            self.plan.expected[0].identity.schema, formal_count,
        )

    @staticmethod
    def _production_provider(system: str) -> Any:
        from src.evaluation.m18_shared_provider import (
            M18SharedDirectProvider, M18SharedMINDProvider, M18SharedPlanProvider,
            M18SharedProviderClient, M18SharedReActProvider,
        )
        return {
            "mind_lite_v11": M18SharedMINDProvider,
            "direct_tool_calling": M18SharedDirectProvider,
            "react": M18SharedReActProvider,
            "plan_and_execute": M18SharedPlanProvider,
        }[system](M18SharedProviderClient())

    @staticmethod
    def _record(expected: M18CorrectedProvenance, result: Any | None) -> M18CorrectedRecord:
        if result is None:
            return M18CorrectedRecord(expected, "provider_failure", None)
        return M18CorrectedRecord(expected, result.terminal, result.evaluator_outcome)

    def execute(self, *, provider_factory: ProviderFactory | None = None,
                after_persist: Callable[[M18CorrectedRecord], None] | None = None,
                limit: int | None = None, allow_systematic_resume: bool = False) -> tuple[M18CorrectedRecord, ...]:
        self.initialize()
        prior = self.systematic_stop()
        if prior is not None and not allow_systematic_resume:
            raise M18V2SystematicProviderStop(prior)
        factory = self._production_provider if provider_factory is None else provider_factory
        completed: list[M18CorrectedRecord] = []
        evidence: dict[tuple[str, str, str], list[str]] = {}
        for expected in self.store.missing()[:limit]:
            providers = {system: factory(system) for system in M18_V3_SYSTEMS}
            adapter = m18_v3_concrete_adapters(providers)[expected.identity.comparator_id]
            diagnostic = None
            try:
                result = M18V3SharedExecutionHarness().dry_run(
                    self.plan.cases_by_id[expected.identity.case_id], adapter)
            except M18V2ProviderExecutionFailure as error:
                result, diagnostic = None, error.diagnostic
            record = self.store.persist(self._record(expected, result))
            completed.append(record)
            if after_persist is not None:
                after_persist(record)
            if diagnostic is not None and diagnostic.is_contract_incompatibility:
                key = (diagnostic.comparator, diagnostic.stage, diagnostic.category.value)
                rows = evidence.setdefault(key, [])
                rows.append(record.run_id)
                if len(rows) >= 2:
                    event = M18V2SystematicProviderStopEvent(
                        diagnostic.comparator, diagnostic.stage, diagnostic.category,
                        tuple(rows), len(rows), http_status=diagnostic.http_status)
                    self._persist_stop(event)
                    raise M18V2SystematicProviderStop(event)
        return tuple(completed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M18 corrected-condition pilot runner")
    parser.add_argument("--condition", default=M18_CORRECTED_COMPARATOR_CONTRACT_ID)
    parser.add_argument("--split", default="pilot")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--result-root", type=Path)
    args = parser.parse_args(argv)
    select_corrected_condition(args.condition)
    if args.split != "pilot":
        parser.error("formal, diagnostic, and historical execution are unauthorized")
    runner = M18CorrectedPilotRunner.from_repository(Path("."), result_root=args.result_root)
    if not args.execute:
        print(json.dumps(runner.preflight().__dict__, sort_keys=True))
        return 0
    runner.execute()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
