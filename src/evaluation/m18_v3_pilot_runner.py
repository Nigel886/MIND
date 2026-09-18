"""Explicit, pilot-only execution entry point for the frozen M18 v3 suite.

Import and preflight are provider-free and read-only.  Result persistence is
reachable only through :meth:`M18V3PilotRunner.execute` or CLI ``--execute``.
The module deliberately has no formal or dynamic-suite path.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Mapping

from src.evaluation.m18_task_generation import canonical_hash, canonical_json
from src.evaluation.m18_v2_pilot_runner import M18V2PilotIntegrityError, _case_from_private
from src.evaluation.m18_v2_provider_diagnostics import (
    M18V2ProviderDiagnostic, M18V2ProviderExecutionFailure,
    M18V2SystematicProviderStop, M18V2SystematicProviderStopEvent,
)
from src.evaluation.m18_v3_provenance import M18V3RunIdentity
from src.evaluation.m18_v3_runtime import M18V3SharedExecutionHarness, M18_V3_SYSTEMS, m18_v3_concrete_adapters
from src.evaluation.m18_v3_semantics import (
    M18V3Case, M18_V3_BUDGET_ID, M18_V3_ENVIRONMENT_ID, M18_V3_EVALUATOR_ID,
    M18_V3_RUNTIME_ID, M18_V3_SUITE_VERSION,
)
from src.evaluation.m18_v3_suite_freeze import ROOT as M18_V3_SUITE_ROOT, load_and_validate


M18_V3_PILOT_RESULT_NAMESPACE = Path("evaluation/m18/results/v3/pilot/m18_suite_v3")
M18_V3_PILOT_STORE_MANIFEST = "m18_v3_pilot_store_manifest.json"
M18_V3_PILOT_SYSTEMATIC_STOP = "m18_v3_pilot_systematic_provider_stop.json"
M18_V3_RESULT_SCHEMA = "m18_v3_pilot_result_record_v1"
M18_V3_EXECUTION_BASELINE = "provider_free_v3"
M18_V3_EXPECTED_MANIFEST_HASH = "2f88a22a25118d93b30fa3e399562deb21e0034164c04e3fa30caa3103da0db9"


def validate_m18_v3_namespace_integrity(repository_root: Path) -> None:
    """Reject JSON outside the explicit v3 pilot allowlist.

    The canonical pilot store has flat record files plus its two fixed control
    artifacts.  Formal execution remains unauthorized, so any JSON below v3
    that is not an allowed pilot file is evidence-integrity drift.
    """
    root = repository_root.resolve() / "evaluation/m18/results/v3"
    if not root.exists():
        return
    pilot = root / "pilot/m18_suite_v3"
    allowed = {M18_V3_PILOT_STORE_MANIFEST, M18_V3_PILOT_SYSTEMATIC_STOP}
    for path in root.rglob("*.json"):
        if path.parent == pilot and (path.name in allowed or path.stem.startswith("m18v3-")):
            continue
        raise M18V2PilotIntegrityError("stray JSON in immutable v3 evidence tree")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise M18V2PilotIntegrityError("invalid frozen v3 artifact") from error


@dataclass(frozen=True)
class M18V3PilotProvenance:
    identity: M18V3RunIdentity
    manifest_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.identity, M18V3RunIdentity) or self.manifest_hash != M18_V3_EXPECTED_MANIFEST_HASH:
            raise ValueError("v3 run provenance must bind the exact frozen manifest")
        if self.identity.comparator_id not in M18_V3_SYSTEMS or not 1 <= self.identity.repetition <= 5:
            raise ValueError("v3 comparator/repetition is outside the frozen pilot universe")
        if self.identity.provider_config_hash != M18_V3_EXECUTION_BASELINE or self.identity.execution_baseline != M18_V3_EXECUTION_BASELINE:
            raise ValueError("v3 execution identity is not frozen")

    @property
    def run_id(self) -> str: return self.identity.run_id

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity.to_dict(), "run_id": self.run_id, "manifest_hash": self.manifest_hash,
                "result_schema": M18_V3_RESULT_SCHEMA}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "M18V3PilotProvenance":
        expected = {"schema", "suite_identity", "environment_id", "evaluator_id", "budget_id", "runtime_id", "public_action_contract_id", "case_id", "comparator_id", "repetition", "provider_config_hash", "execution_baseline", "run_id", "manifest_hash", "result_schema"}
        if not isinstance(value, Mapping) or set(value) != expected or value.get("result_schema") != M18_V3_RESULT_SCHEMA:
            raise ValueError("v3 provenance schema mismatch")
        identity = M18V3RunIdentity(value["case_id"], value["comparator_id"], value["repetition"], value["provider_config_hash"], value["execution_baseline"], value["schema"], value["suite_identity"])
        if value["run_id"] != identity.run_id: raise ValueError("v3 run ID mismatch")
        # Identity.to_dict closes the environmental/runtime fields too.
        if any(value[key] != identity.to_dict()[key] for key in identity.to_dict()): raise ValueError("v3 identity projection mismatch")
        return cls(identity, value["manifest_hash"])


@dataclass(frozen=True)
class M18V3PilotRecord:
    provenance: M18V3PilotProvenance
    evaluator_outcome: str | None
    terminal: str
    failure_taxonomy: str | None
    provider_accounting: Mapping[str, int]
    provider_diagnostic: M18V2ProviderDiagnostic | None = None
    integrity_hash: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, M18V3PilotProvenance) or not isinstance(self.terminal, str) or not self.terminal:
            raise ValueError("v3 record provenance and terminal are required")
        if self.evaluator_outcome is not None and not isinstance(self.evaluator_outcome, str): raise ValueError("invalid evaluator outcome")
        if self.failure_taxonomy is not None and not isinstance(self.failure_taxonomy, str): raise ValueError("invalid failure taxonomy")
        if set(self.provider_accounting) != {"logical_provider_calls", "transport_attempts"} or any(not isinstance(x, int) or isinstance(x, bool) or x < 0 for x in self.provider_accounting.values()):
            raise ValueError("v3 provider accounting schema mismatch")
        if self.provider_diagnostic is not None and self.failure_taxonomy != "provider_failure":
            raise ValueError("provider diagnostic requires provider_failure")
        expected = canonical_hash(self._protected())
        if not self.integrity_hash: object.__setattr__(self, "integrity_hash", expected)
        elif self.integrity_hash != expected: raise ValueError("v3 result integrity hash mismatch")
        rendered = canonical_json(self.to_dict())
        if any(token in rendered for token in ("expected_final_result", "ground_truth", "chain_of_thought", "hidden_reasoning", "sk-test-", "BearerSecret", "supersecretvalue")):
            raise ValueError("v3 result truth/secret firewall violation")

    @property
    def run_id(self) -> str: return self.provenance.run_id
    def _protected(self) -> dict[str, Any]:
        return {"provenance": self.provenance.to_dict(), "evaluator_outcome": self.evaluator_outcome,
                "terminal": self.terminal, "failure_taxonomy": self.failure_taxonomy,
                "provider_accounting": dict(self.provider_accounting),
                "provider_diagnostic": None if self.provider_diagnostic is None else self.provider_diagnostic.to_dict()}
    def to_dict(self) -> dict[str, Any]: return {**self._protected(), "integrity_hash": self.integrity_hash}
    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "M18V3PilotRecord":
        expected = {"provenance", "evaluator_outcome", "terminal", "failure_taxonomy", "provider_accounting", "provider_diagnostic", "integrity_hash"}
        if not isinstance(value, Mapping) or set(value) != expected: raise ValueError("v3 record schema mismatch")
        return cls(M18V3PilotProvenance.from_dict(value["provenance"]), value["evaluator_outcome"], value["terminal"], value["failure_taxonomy"], dict(value["provider_accounting"]), M18V2ProviderDiagnostic.from_dict(value["provider_diagnostic"]) if value["provider_diagnostic"] is not None else None, value["integrity_hash"])


@dataclass(frozen=True)
class M18V3PilotPlan:
    repository_root: Path
    cases: tuple[M18V3Case, ...]
    expected: tuple[M18V3PilotProvenance, ...]
    manifest: Mapping[str, Any]
    split: Mapping[str, Any]

    @classmethod
    def from_repository(cls, repository_root: Path) -> "M18V3PilotPlan":
        root = repository_root.resolve(); suite_root = root / M18_V3_SUITE_ROOT
        manifest = load_and_validate(suite_root)
        split = _read(suite_root / "manifests/m18_suite_v3_split.json")
        private = _read(suite_root / "pilot/private_cases.json")
        public = _read(suite_root / "pilot/public_cases.json")
        if manifest.get("manifest_hash") != M18_V3_EXPECTED_MANIFEST_HASH:
            raise M18V2PilotIntegrityError("v3 frozen manifest mismatch")
        if (manifest.get("suite_identity"), manifest.get("environment_id"), manifest.get("evaluator_id"), manifest.get("runtime_id"), manifest.get("budget_id"), manifest.get("run_id_schema")) != (M18_V3_SUITE_VERSION, M18_V3_ENVIRONMENT_ID, M18_V3_EVALUATOR_ID, M18_V3_RUNTIME_ID, M18_V3_BUDGET_ID, "m18_v3_logical_run_id_v1"):
            raise M18V2PilotIntegrityError("v3 identity mismatch")
        if not isinstance(private, list) or not isinstance(public, list) or len(private) != 18 or len(public) != 18:
            raise M18V2PilotIntegrityError("v3 pilot fixture count mismatch")
        cases = tuple(M18V3Case(_case_from_private(item["source_private_case"])) for item in private if isinstance(item, Mapping) and set(item) == {"v3", "source_private_case"})
        if len(cases) != 18 or [case.case_id for case in cases] != split.get("pilot_ids") or [item.get("case_id") for item in public] != [case.case_id for case in cases]:
            raise M18V2PilotIntegrityError("v3 pilot membership/order mismatch")
        expected = tuple(M18V3PilotProvenance(M18V3RunIdentity(case.case_id, system, repetition), manifest["manifest_hash"])
                         for case in cases for system in M18_V3_SYSTEMS for repetition in range(1, 6))
        if len(expected) != 360 or len({item.run_id for item in expected}) != 360 or manifest.get("pilot", {}).get("run_count") != 360:
            raise M18V2PilotIntegrityError("v3 pilot run universe mismatch")
        return cls(root, cases, expected, dict(manifest), dict(split))

    @property
    def result_root(self) -> Path: return self.repository_root / M18_V3_PILOT_RESULT_NAMESPACE
    @property
    def cases_by_id(self) -> Mapping[str, M18V3Case]: return {item.case_id: item for item in self.cases}


class M18V3PilotResultStore:
    def __init__(self, root: Path, expected: tuple[M18V3PilotProvenance, ...], manifest: Mapping[str, Any]) -> None:
        self.root, self.expected, self.manifest = root, expected, dict(manifest)
        self._by_id = {item.run_id: item for item in expected}
        if len(self._by_id) != len(expected): raise M18V2PilotIntegrityError("duplicate expected v3 run ID")
    @property
    def manifest_path(self) -> Path: return self.root / M18_V3_PILOT_STORE_MANIFEST
    @property
    def systematic_stop_path(self) -> Path: return self.root / M18_V3_PILOT_SYSTEMATIC_STOP
    @staticmethod
    def _atomic(path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
            handle.write(canonical_json(dict(value)) + "\n"); handle.flush(); os.fsync(handle.fileno()); temporary = Path(handle.name)
        try:
            if path.exists(): raise FileExistsError("no-overwrite persistence violation")
            os.replace(temporary, path)
        except Exception:
            temporary.unlink(missing_ok=True); raise
    def _store_manifest(self) -> dict[str, Any]:
        return {"store_schema": "m18_v3_pilot_store_v1", "suite_manifest_hash": self.manifest["manifest_hash"], "split": "pilot", "expected_run_ids": [item.run_id for item in self.expected]}
    def initialize(self) -> None:
        value = self._store_manifest()
        if self.manifest_path.exists():
            if _read(self.manifest_path) != value: raise M18V2PilotIntegrityError("v3 store manifest drift")
        else: self._atomic(self.manifest_path, value)
    def records(self) -> tuple[M18V3PilotRecord, ...]:
        if not self.root.exists(): return ()
        for path in self.root.rglob("*.json"):
            if path.parent != self.root:
                raise M18V2PilotIntegrityError("nested JSON is not an admitted v3 pilot record")
        records=[]
        for path in sorted(self.root.glob("*.json")):
            if path.name in {M18_V3_PILOT_STORE_MANIFEST, M18_V3_PILOT_SYSTEMATIC_STOP}: continue
            try: record=M18V3PilotRecord.from_dict(_read(path))
            except Exception as error: raise M18V2PilotIntegrityError("invalid v3 pilot record") from error
            if path.stem != record.run_id: raise M18V2PilotIntegrityError("v3 result filename mismatch")
            if self._by_id.get(record.run_id) != record.provenance: raise M18V2PilotIntegrityError("v3 result provenance mismatch")
            records.append(record)
        if len({item.run_id for item in records}) != len(records): raise M18V2PilotIntegrityError("duplicate v3 records")
        return tuple(records)
    def missing(self) -> tuple[M18V3PilotProvenance, ...]:
        completed={item.run_id for item in self.records()}; return tuple(item for item in self.expected if item.run_id not in completed)
    def persist(self, record: M18V3PilotRecord) -> M18V3PilotRecord:
        if self._by_id.get(record.run_id) != record.provenance or record.run_id in {item.run_id for item in self.records()}:
            raise M18V2PilotIntegrityError("v3 result admission rejected")
        path=self.root/(record.run_id+".json")
        if path.exists(): raise M18V2PilotIntegrityError("duplicate v3 result path")
        self._atomic(path, record.to_dict())
        reread=M18V3PilotRecord.from_dict(_read(path))
        if self._by_id.get(reread.run_id) != reread.provenance: raise M18V2PilotIntegrityError("v3 re-read admission rejected")
        return reread
    def systematic_stop(self) -> M18V2SystematicProviderStopEvent | None:
        if not self.systematic_stop_path.exists(): return None
        try: return M18V2SystematicProviderStopEvent.from_dict(_read(self.systematic_stop_path))
        except Exception as error: raise M18V2PilotIntegrityError("invalid v3 systematic stop") from error
    def persist_systematic_stop(self, event: M18V2SystematicProviderStopEvent) -> None:
        if self.systematic_stop_path.exists():
            if self.systematic_stop()!=event: raise M18V2PilotIntegrityError("conflicting v3 systematic stop")
            return
        self._atomic(self.systematic_stop_path,event.to_dict())


@dataclass(frozen=True)
class M18V3PilotPreflight:
    expected: int; valid: int; missing: int; duplicates: int; invalid: int; unexpected: int


ProviderFactory = Callable[[str], Any]


class M18V3PilotRunner:
    def __init__(self, plan: M18V3PilotPlan, *, result_root: Path | None = None) -> None:
        if not isinstance(plan, M18V3PilotPlan): raise TypeError("M18V3PilotPlan required")
        self.plan=plan; self.store=M18V3PilotResultStore(plan.result_root if result_root is None else result_root,plan.expected,plan.manifest)
    @classmethod
    def from_repository(cls, root: Path, *, result_root: Path | None=None) -> "M18V3PilotRunner": return cls(M18V3PilotPlan.from_repository(root),result_root=result_root)
    def preflight(self) -> M18V3PilotPreflight:
        records=self.store.records(); ids=[item.run_id for item in records]
        valid=sum(self.store._by_id.get(item.run_id)==item.provenance for item in records)
        return M18V3PilotPreflight(len(self.plan.expected),valid,len(self.store.missing()),len(ids)-len(set(ids)),len(records)-valid,0)
    @staticmethod
    def _production_provider(system: str) -> Any:
        from src.evaluation.m18_shared_provider import M18SharedDirectProvider, M18SharedMINDProvider, M18SharedPlanProvider, M18SharedProviderClient, M18SharedReActProvider
        return {"mind_lite_v11":M18SharedMINDProvider,"direct_tool_calling":M18SharedDirectProvider,"react":M18SharedReActProvider,"plan_and_execute":M18SharedPlanProvider}[system](M18SharedProviderClient())
    @staticmethod
    def _record(expected: M18V3PilotProvenance, result: Any | None, error: M18V2ProviderExecutionFailure | None) -> M18V3PilotRecord:
        if error is not None:
            d=error.diagnostic
            # Existing adapters can wrap a structural provider message in a
            # generic local exception type.  Preserve the trusted accounting
            # and stage while reclassifying only that finite diagnostic value;
            # no raw provider text enters the record.
            category = d.message_summary if d.category.value == "unknown_provider_error" else d.category
            # Persist a constant, non-provider-derived summary.  The category,
            # stage, status and counters retain the operational information,
            # while even unusual raw error text cannot become a result side
            # channel.
            d=M18V2ProviderDiagnostic(category,d.comparator,d.stage,d.logical_call_index,d.transport_attempts,d.retry_exhausted,"provider_failure",d.http_status)
            return M18V3PilotRecord(expected,None,"provider_failure","provider_failure",{"logical_provider_calls":d.logical_call_index,"transport_attempts":d.transport_attempts},d)
        assert result is not None
        failure=None if result.evaluator_outcome=="success" else result.terminal
        return M18V3PilotRecord(expected,result.evaluator_outcome,result.terminal,failure,{"logical_provider_calls":result.logical_provider_calls,"transport_attempts":result.transport_attempts})
    def execute(self, *, provider_factory: ProviderFactory | None=None, after_persist: Callable[[M18V3PilotRecord],None] | None=None, limit: int | None=None, allow_systematic_resume: bool=False) -> tuple[M18V3PilotRecord,...]:
        self.store.initialize(); prior=self.store.systematic_stop()
        if prior is not None and not allow_systematic_resume: raise M18V2SystematicProviderStop(prior)
        factory=self._production_provider if provider_factory is None else provider_factory; completed=[]; evidence={}
        for expected in self.store.missing()[:limit]:
            providers={system:factory(system) for system in M18_V3_SYSTEMS}; adapter=m18_v3_concrete_adapters(providers)[expected.identity.comparator_id]
            try: result=M18V3SharedExecutionHarness().dry_run(self.plan.cases_by_id[expected.identity.case_id],adapter); record=self._record(expected,result,None)
            except M18V2ProviderExecutionFailure as error: record=self._record(expected,None,error)
            persisted=self.store.persist(record); completed.append(persisted)
            if after_persist is not None: after_persist(persisted)
            diagnostic=persisted.provider_diagnostic
            if diagnostic is not None and diagnostic.is_contract_incompatibility:
                key=(diagnostic.comparator,diagnostic.stage,diagnostic.category.value); rows=evidence.setdefault(key,[]); rows.append(persisted.run_id)
                if len(rows)>=2:
                    event=M18V2SystematicProviderStopEvent(diagnostic.comparator,diagnostic.stage,diagnostic.category,tuple(rows),len(rows),http_status=diagnostic.http_status)
                    self.store.persist_systematic_stop(event); raise M18V2SystematicProviderStop(event)
        return tuple(completed)


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description="M18 v3 pilot execution runner")
    parser.add_argument("--suite",default=M18_V3_SUITE_VERSION); parser.add_argument("--split",default="pilot"); parser.add_argument("--execute",action="store_true"); parser.add_argument("--result-root",type=Path)
    args=parser.parse_args(argv)
    if args.suite != M18_V3_SUITE_VERSION: parser.error("only frozen m18_suite_v3 is accepted")
    if args.split != "pilot": parser.error("formal, diagnostic, and historical execution are unauthorized")
    runner=M18V3PilotRunner.from_repository(Path("."),result_root=args.result_root)
    if not args.execute: print(json.dumps(runner.preflight().__dict__,sort_keys=True)); return 0
    runner.execute(); return 0


if __name__ == "__main__": raise SystemExit(main())
