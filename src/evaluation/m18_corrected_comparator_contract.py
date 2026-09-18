"""Provider-free identity and namespace contract for corrected M18 comparators.

This module deliberately has no provider construction or execution entry point.
It domain-separates future corrected evidence from the immutable M18 v3 pilot.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping

from src.evaluation.m18_task_generation import canonical_hash
from src.evaluation.m18_v3_runtime import M18_V3_SYSTEMS
from src.evaluation.m18_v2_pilot_runner import M18V2PilotIntegrityError
from src.evaluation.m18_v3_semantics import (
    M18_V3_BUDGET_ID, M18_V3_ENVIRONMENT_ID, M18_V3_EVALUATOR_ID,
    M18_V3_PUBLIC_ACTION_CONTRACT_ID, M18_V3_RUNTIME_ID, M18_V3_SUITE_VERSION,
)


M18_CORRECTED_COMPARATOR_CONTRACT_ID = "m18_v3_comparator_contract_v2"
M18_CORRECTED_RUN_ID_SCHEMA = "m18_v3_comparator_contract_v2_logical_run_id_v1"
M18_CORRECTED_PILOT_RESULT_NAMESPACE = Path("evaluation/m18/results/m18_v3_comparator_contract_v2/pilot")
M18_CORRECTED_FORMAL_RESULT_NAMESPACE = Path("evaluation/m18/results/m18_v3_comparator_contract_v2/formal")


@dataclass(frozen=True)
class M18CorrectedRunIdentity:
    case_id: str
    comparator_id: str
    repetition: int
    provider_config_hash: str = "provider_free_v3"
    execution_baseline: str = "provider_free_v3"
    comparator_contract_id: str = M18_CORRECTED_COMPARATOR_CONTRACT_ID
    schema: str = M18_CORRECTED_RUN_ID_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != M18_CORRECTED_RUN_ID_SCHEMA or self.comparator_contract_id != M18_CORRECTED_COMPARATOR_CONTRACT_ID:
            raise ValueError("corrected identity is closed and domain-separated")
        if not self.case_id or self.comparator_id not in M18_V3_SYSTEMS or not isinstance(self.repetition, int) or isinstance(self.repetition, bool) or self.repetition < 1:
            raise ValueError("corrected case, comparator, and repetition are required")
        if not self.provider_config_hash or not self.execution_baseline:
            raise ValueError("corrected provider provenance is required")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema, "comparator_contract_id": self.comparator_contract_id,
            "suite_identity": M18_V3_SUITE_VERSION, "environment_id": M18_V3_ENVIRONMENT_ID,
            "evaluator_id": M18_V3_EVALUATOR_ID, "budget_id": M18_V3_BUDGET_ID,
            "runtime_id": M18_V3_RUNTIME_ID, "public_action_contract_id": M18_V3_PUBLIC_ACTION_CONTRACT_ID,
            "case_id": self.case_id, "comparator_id": self.comparator_id, "repetition": self.repetition,
            "provider_config_hash": self.provider_config_hash, "execution_baseline": self.execution_baseline,
        }

    @property
    def run_id(self) -> str:
        return "m18ccv2-" + canonical_hash(self.to_dict())


def corrected_namespace_counts(repository_root: Path) -> tuple[int, int]:
    """Return corrected pilot/formal record counts without creating either namespace."""
    root = repository_root.resolve()
    return tuple(sum(1 for item in root.joinpath(namespace).rglob("*.json") if item.is_file())
                 if root.joinpath(namespace).exists() else 0
                 for namespace in (M18_CORRECTED_PILOT_RESULT_NAMESPACE, M18_CORRECTED_FORMAL_RESULT_NAMESPACE))


def select_corrected_condition(condition_id: str) -> str:
    """Closed future-runner selection; the historical v3 condition is rejected."""
    if condition_id != M18_CORRECTED_COMPARATOR_CONTRACT_ID:
        raise ValueError("only the corrected comparator contract is selectable here")
    return condition_id


@dataclass(frozen=True)
class M18CorrectedProvenance:
    """Closed, persisted provenance for one corrected-condition logical run."""
    identity: M18CorrectedRunIdentity
    manifest_hash: str
    result_schema: str = "m18_v3_comparator_contract_v2_result_v1"

    def __post_init__(self) -> None:
        if not isinstance(self.identity, M18CorrectedRunIdentity) or not self.manifest_hash or self.result_schema != "m18_v3_comparator_contract_v2_result_v1":
            raise ValueError("corrected provenance is closed")

    @property
    def run_id(self) -> str: return self.identity.run_id
    def to_dict(self) -> dict[str, Any]: return {**self.identity.to_dict(), "run_id": self.run_id, "manifest_hash": self.manifest_hash, "result_schema": self.result_schema}
    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "M18CorrectedProvenance":
        expected={"schema","comparator_contract_id","suite_identity","environment_id","evaluator_id","budget_id","runtime_id","public_action_contract_id","case_id","comparator_id","repetition","provider_config_hash","execution_baseline","run_id","manifest_hash","result_schema"}
        if not isinstance(value, Mapping) or set(value) != expected: raise ValueError("corrected provenance schema mismatch")
        identity=M18CorrectedRunIdentity(value["case_id"],value["comparator_id"],value["repetition"],value["provider_config_hash"],value["execution_baseline"],value["comparator_contract_id"],value["schema"])
        if value["run_id"] != identity.run_id: raise ValueError("corrected run ID mismatch")
        if any(value[key] != identity.to_dict()[key] for key in identity.to_dict()): raise ValueError("corrected identity projection mismatch")
        return cls(identity, value["manifest_hash"], value["result_schema"])


@dataclass(frozen=True)
class M18CorrectedRecord:
    provenance: M18CorrectedProvenance
    terminal: str
    evaluator_outcome: str | None
    integrity_hash: str = ""
    def __post_init__(self) -> None:
        if not isinstance(self.provenance, M18CorrectedProvenance) or not isinstance(self.terminal, str) or not self.terminal: raise ValueError("corrected record fields invalid")
        protected={"provenance":self.provenance.to_dict(),"terminal":self.terminal,"evaluator_outcome":self.evaluator_outcome}
        expected=canonical_hash(protected)
        if not self.integrity_hash: object.__setattr__(self,"integrity_hash",expected)
        elif self.integrity_hash != expected: raise ValueError("corrected record integrity mismatch")
    @property
    def run_id(self) -> str: return self.provenance.run_id
    def to_dict(self) -> dict[str, Any]: return {"provenance":self.provenance.to_dict(),"terminal":self.terminal,"evaluator_outcome":self.evaluator_outcome,"integrity_hash":self.integrity_hash}
    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "M18CorrectedRecord":
        if not isinstance(value, Mapping) or set(value) != {"provenance","terminal","evaluator_outcome","integrity_hash"}: raise ValueError("corrected record schema mismatch")
        return cls(M18CorrectedProvenance.from_dict(value["provenance"]),value["terminal"],value["evaluator_outcome"],value["integrity_hash"])


class M18CorrectedResultStore:
    """Atomic, missing-only admission store; it cannot admit v3 provenance."""
    def __init__(self, root: Path, expected: tuple[M18CorrectedProvenance, ...], manifest_hash: str) -> None:
        if root.name not in {"pilot","formal"}: raise ValueError("corrected namespace must be pilot or formal")
        self.root,self.expected,self.manifest_hash=root,expected,manifest_hash; self._by_id={item.run_id:item for item in expected}
        if len(self._by_id) != len(expected): raise ValueError("duplicate corrected expected IDs")
    @staticmethod
    def _atomic(path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True,exist_ok=True)
        with NamedTemporaryFile("w",encoding="utf-8",delete=False,dir=path.parent,suffix=".tmp") as handle:
            handle.write(json.dumps(dict(value),sort_keys=True,separators=(",",":"))+"\n"); handle.flush(); os.fsync(handle.fileno()); temporary=Path(handle.name)
        try:
            if path.exists(): raise FileExistsError("no-overwrite admission")
            os.replace(temporary,path)
        except Exception: temporary.unlink(missing_ok=True); raise
    def records(self) -> tuple[M18CorrectedRecord,...]:
        if not self.root.exists(): return ()
        records=[]
        for path in sorted(self.root.glob("*.json")):
            try: record=M18CorrectedRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except Exception as error: raise M18V2PilotIntegrityError("invalid corrected record") from error
            if path.stem != record.run_id or self._by_id.get(record.run_id) != record.provenance or record.provenance.manifest_hash != self.manifest_hash: raise M18V2PilotIntegrityError("corrected admission rejected")
            records.append(record)
        if len({record.run_id for record in records}) != len(records): raise M18V2PilotIntegrityError("duplicate corrected record")
        return tuple(records)
    def missing(self) -> tuple[M18CorrectedProvenance,...]:
        seen={record.run_id for record in self.records()}; return tuple(item for item in self.expected if item.run_id not in seen)
    def persist(self, record: M18CorrectedRecord) -> M18CorrectedRecord:
        if self._by_id.get(record.run_id) != record.provenance or record.provenance.manifest_hash != self.manifest_hash or record.run_id in {item.run_id for item in self.records()}: raise M18V2PilotIntegrityError("corrected result admission rejected")
        path=self.root/(record.run_id+".json"); self._atomic(path,record.to_dict()); reread=M18CorrectedRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
        if self._by_id.get(reread.run_id) != reread.provenance: raise M18V2PilotIntegrityError("corrected re-read admission rejected")
        return reread


@dataclass(frozen=True)
class M18CorrectedRunnerPlan:
    """Provider-free future runner preparation; deliberately has no execute method."""
    expected: tuple[M18CorrectedProvenance,...]
    pilot_root: Path
    formal_root: Path
    @classmethod
    def from_v3_plan(cls, plan: Any) -> "M18CorrectedRunnerPlan":
        expected=tuple(M18CorrectedProvenance(M18CorrectedRunIdentity(case.case_id,system,repetition),plan.manifest["manifest_hash"])
                       for case in plan.cases for system in M18_V3_SYSTEMS for repetition in range(1,6))
        if len(expected) != 360 or len({item.run_id for item in expected}) != 360: raise ValueError("corrected pilot universe mismatch")
        return cls(expected,plan.repository_root / M18_CORRECTED_PILOT_RESULT_NAMESPACE,plan.repository_root / M18_CORRECTED_FORMAL_RESULT_NAMESPACE)
    def pilot_store(self) -> M18CorrectedResultStore: return M18CorrectedResultStore(self.pilot_root,self.expected,self.expected[0].manifest_hash)
