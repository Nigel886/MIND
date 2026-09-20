"""Guarded, provider-free preparation for the M18 power-calibration condition.

This module deliberately creates no production evidence unless ``execute`` is
called with an injected provider.  The command-line entry point only preflights;
there is no CLI real-execution switch in Issue #195.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Iterable, Mapping

from src.evaluation.m18_task_generation import canonical_hash, canonical_json
from src.evaluation.m18_v2_pilot_runner import M18V2PilotIntegrityError
from src.evaluation.m18_v2_provider_diagnostics import (
    M18V2ProviderDiagnostic, M18V2ProviderExecutionFailure,
    M18V2SystematicProviderStop, M18V2SystematicProviderStopEvent,
)
from src.evaluation.m18_shared_provider import (
    M18SharedDirectProvider, M18SharedMINDProvider, M18SharedProviderClient,
    M18SharedProviderConfiguration,
)
from src.evaluation.m18_task_generation import M18Cohort, M18Difficulty, M18Namespace
from src.evaluation.m18_v2_semantics import M18V2Case, M18V2PublicCase, generate_m18_v2_case
from src.evaluation.m18_v3_runtime import M18V3DirectAdapter, M18V3MINDAdapter, M18V3SharedExecutionHarness
from src.evaluation.m18_v3_semantics import (
    M18V3Case, M18_V3_BUDGET_ID, M18_V3_ENVIRONMENT_ID, M18_V3_EVALUATOR_ID,
    M18_V3_RUNTIME_ID,
)

M18_POWER_CALIBRATION_ID = "m18_power_calibration_v1"
M18_POWER_CALIBRATION_DESIGN_VERSION = "m18_power_calibration_design_v1"
M18_POWER_CALIBRATION_RUN_SCHEMA = "m18_power_calibration_v1_logical_run_id_v1"
M18_POWER_CALIBRATION_RESULT_SCHEMA = "m18_power_calibration_v1_result_v1"
M18_POWER_CALIBRATION_NAMESPACE = Path("evaluation/m18/results/m18_power_calibration_v1/pilot")
M18_POWER_CALIBRATION_PREFIX = "m18pcv1-"
M18_POWER_CALIBRATION_COMPARATORS = ("mind_lite_v11", "direct_tool_calling")
M18_POWER_CALIBRATION_CONTRACT = "m18_v3_comparator_contract_v2"
M18_POWER_CALIBRATION_PROVIDER_HASH = "0f251e14722603e6e39416374467a3598cd72e1d28673e60daf8440dd6115ee2"
_FAMILIES = ("dependent_stateful_composition_a", "dependent_stateful_composition_b")
_STRATA = ("low", "medium", "high")


class M18PowerCalibrationPreflightError(M18V2PilotIntegrityError):
    """Typed, fail-closed refusal before a real calibration call."""


@dataclass(frozen=True)
class M18PowerCalibrationDispatch:
    """The minimal binding evidence required from a real comparator adapter."""
    comparator_id: str
    comparator_contract_id: str
    strict_integer_answer: bool

    def __post_init__(self) -> None:
        if (self.comparator_id not in M18_POWER_CALIBRATION_COMPARATORS or
                self.comparator_contract_id != M18_POWER_CALIBRATION_CONTRACT or
                self.strict_integer_answer is not True):
            raise M18PowerCalibrationPreflightError("calibration dispatch contract rejected")


@dataclass(frozen=True)
class M18PowerCalibrationEpisode:
    """One closed calibration-ID to corrected executable-episode binding."""
    provenance: "M18PowerCalibrationProvenance"
    case: M18V3Case
    adapter_type: type
    provider_config_hash: str

    def __post_init__(self) -> None:
        identity = self.provenance.identity
        expected_adapter = M18V3MINDAdapter if identity.comparator_id == "mind_lite_v11" else M18V3DirectAdapter
        declared = identity.to_dict()
        if (not isinstance(self.case, M18V3Case) or self.case.case_id != identity.case_id or
                declared["environment_id"] != self.case.environment_id or
                declared["evaluator_id"] != self.case.evaluator_id or
                declared["runtime_id"] != M18_V3_RUNTIME_ID or declared["budget_id"] != M18_V3_BUDGET_ID or
                declared["comparator_contract_id"] != M18_POWER_CALIBRATION_CONTRACT or
                self.adapter_type is not expected_adapter or self.provider_config_hash != M18_POWER_CALIBRATION_PROVIDER_HASH):
            raise M18PowerCalibrationPreflightError("calibration executable bridge rejected")

    @property
    def run_id(self) -> str: return self.provenance.run_id
    @property
    def identity(self) -> "M18PowerCalibrationIdentity": return self.provenance.identity

    def recovered_identity(self) -> dict[str, Any]:
        return {**self.provenance.identity.to_dict(), "logical_run_id": self.run_id,
                "provider_config_hash": self.provider_config_hash,
                "adapter": self.adapter_type.__name__}


def _logical_ids_in(value: Any) -> set[str]:
    """Extract identities only; outcome fields are deliberately ignored."""
    if isinstance(value, Mapping):
        own = {str(value[key]) for key in ("run_id", "logical_run_id") if isinstance(value.get(key), str)}
        return own | set().union(*(_logical_ids_in(item) for item in value.values())) if value else own
    if isinstance(value, list): return set().union(*(_logical_ids_in(item) for item in value)) if value else set()
    return set()


def historical_calibration_collision_ids(repository_root: Path, expected_ids: Iterable[str]) -> set[str]:
    """Compare calibration IDs to defined historical/formal identity artifacts."""
    domains = (
        "evaluation/m18/results/v3", "evaluation/m18/results/m18_v3_comparator_contract_v2",
        "evaluation/m18/results/v2", "evaluation/m18/results/v1", "evaluation/results/m16",
        "evaluation/m18/results/m18_power_calibration_v1/formal",
    )
    observed: set[str] = set()
    for domain in domains:
        base = repository_root / domain
        if not base.exists(): continue
        for path in base.rglob("*.json"):
            try: observed |= _logical_ids_in(_read(path))
            except M18V2PilotIntegrityError: continue
    return set(expected_ids) & observed


def _read(path: Path) -> Any:
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error: raise M18V2PilotIntegrityError("invalid calibration artifact") from error


def _atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(canonical_json(dict(value)) + "\n"); handle.flush(); os.fsync(handle.fileno()); temporary = Path(handle.name)
    try:
        if path.exists(): raise FileExistsError("no-overwrite calibration persistence")
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True); raise


@dataclass(frozen=True)
class M18PowerCalibrationIdentity:
    case_id: str; source_family: str; difficulty: str; comparator_id: str; repetition: int
    provider_config_id: str = M18_POWER_CALIBRATION_PROVIDER_HASH
    def __post_init__(self) -> None:
        if (self.source_family not in _FAMILIES or self.difficulty not in _STRATA or
                self.comparator_id not in M18_POWER_CALIBRATION_COMPARATORS or not 1 <= self.repetition <= 5):
            raise ValueError("calibration identity is outside frozen design")
    @property
    def paired_cell_key(self) -> str: return f"{self.case_id}:r{self.repetition}"
    def to_dict(self) -> dict[str, Any]:
        return {"schema": M18_POWER_CALIBRATION_RUN_SCHEMA, "calibration_condition_id": M18_POWER_CALIBRATION_ID,
                "calibration_design_id": M18_POWER_CALIBRATION_DESIGN_VERSION, "case_id": self.case_id,
                "source_family": self.source_family, "difficulty_stratum": self.difficulty,
                "comparator_id": self.comparator_id, "repetition": self.repetition, "paired_cell_key": self.paired_cell_key,
                "suite_id": M18_POWER_CALIBRATION_ID, "environment_id": M18_V3_ENVIRONMENT_ID,
                "evaluator_id": M18_V3_EVALUATOR_ID, "runtime_id": M18_V3_RUNTIME_ID,
                "budget_id": M18_V3_BUDGET_ID, "public_action_contract_id": "m18_v3_public_action_contract_v1",
                "comparator_contract_id": M18_POWER_CALIBRATION_CONTRACT, "provider_config_id": self.provider_config_id}
    @property
    def run_id(self) -> str: return M18_POWER_CALIBRATION_PREFIX + canonical_hash(self.to_dict())


@dataclass(frozen=True)
class M18PowerCalibrationProvenance:
    identity: M18PowerCalibrationIdentity; manifest_hash: str
    @property
    def run_id(self) -> str: return self.identity.run_id
    def to_dict(self) -> dict[str, Any]: return {**self.identity.to_dict(), "logical_run_id": self.run_id, "manifest_hash": self.manifest_hash, "result_schema": M18_POWER_CALIBRATION_RESULT_SCHEMA}
    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "M18PowerCalibrationProvenance":
        keys = set(M18PowerCalibrationIdentity("x", _FAMILIES[0], _STRATA[0], M18_POWER_CALIBRATION_COMPARATORS[0], 1).to_dict()) | {"logical_run_id", "manifest_hash", "result_schema"}
        if not isinstance(value, Mapping) or set(value) != keys or value.get("result_schema") != M18_POWER_CALIBRATION_RESULT_SCHEMA: raise ValueError("calibration provenance schema mismatch")
        identity = M18PowerCalibrationIdentity(value["case_id"], value["source_family"], value["difficulty_stratum"], value["comparator_id"], value["repetition"], value["provider_config_id"])
        if value["logical_run_id"] != identity.run_id or any(value[k] != identity.to_dict()[k] for k in identity.to_dict()): raise ValueError("calibration provenance mismatch")
        return cls(identity, value["manifest_hash"])


@dataclass(frozen=True)
class M18PowerCalibrationRecord:
    provenance: M18PowerCalibrationProvenance; terminal: str; evaluator_outcome: str | None; integrity_hash: str = ""
    def __post_init__(self) -> None:
        if not isinstance(self.terminal, str) or not self.terminal: raise ValueError("invalid calibration terminal")
        protected = {"provenance": self.provenance.to_dict(), "terminal": self.terminal, "evaluator_outcome": self.evaluator_outcome}
        digest = canonical_hash(protected)
        if not self.integrity_hash: object.__setattr__(self, "integrity_hash", digest)
        elif self.integrity_hash != digest: raise ValueError("calibration record tampered")
        if any(secret in canonical_json(protected) for secret in ("BearerSecret", "supersecretvalue", "sk-test-")): raise ValueError("secret firewall violation")
    @property
    def run_id(self) -> str: return self.provenance.run_id
    def to_dict(self) -> dict[str, Any]: return {"provenance": self.provenance.to_dict(), "terminal": self.terminal, "evaluator_outcome": self.evaluator_outcome, "integrity_hash": self.integrity_hash}
    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "M18PowerCalibrationRecord":
        if not isinstance(value, Mapping) or set(value) != {"provenance", "terminal", "evaluator_outcome", "integrity_hash"}: raise ValueError("calibration record schema mismatch")
        return cls(M18PowerCalibrationProvenance.from_dict(value["provenance"]), value["terminal"], value["evaluator_outcome"], value["integrity_hash"])


@dataclass(frozen=True)
class M18PowerCalibrationPlan:
    repository_root: Path; manifest: Mapping[str, Any]; expected: tuple[M18PowerCalibrationProvenance, ...]
    @classmethod
    def from_repository(cls, root: Path) -> "M18PowerCalibrationPlan":
        cases = []
        for family in _FAMILIES:
            for stratum in _STRATA:
                for ordinal in range(1, 9):
                    case_id = f"m18pcv1-{family[-1]}-{stratum}-{ordinal:02d}"
                    seed = hashlib.sha256(case_id.encode()).hexdigest()
                    cases.append({"case_id": case_id, "source_family": family, "difficulty_stratum": stratum,
                                  "eligibility_proof": {"primary_eligible": True, "public_transitions": 2, "dependent_later_action": True, "deterministic": True},
                                  "source_seed": seed[:16], "fixture_seed": seed[16:32], "environment_seed": seed[32:48], "order_seed": seed[48:]})
        manifest_core = {"suite_id": M18_POWER_CALIBRATION_ID, "design_id": M18_POWER_CALIBRATION_DESIGN_VERSION,
                         "run_id_schema": M18_POWER_CALIBRATION_RUN_SCHEMA, "result_schema": M18_POWER_CALIBRATION_RESULT_SCHEMA,
                         "comparator_contract_id": M18_POWER_CALIBRATION_CONTRACT, "comparators": list(M18_POWER_CALIBRATION_COMPARATORS), "cases": cases}
        manifest_hash = canonical_hash(manifest_core); manifest = {**manifest_core, "manifest_hash": manifest_hash}
        expected = tuple(M18PowerCalibrationProvenance(M18PowerCalibrationIdentity(c["case_id"], c["source_family"], c["difficulty_stratum"], comparator, repetition), manifest_hash)
                         for c in cases for repetition in range(1, 6) for comparator in M18_POWER_CALIBRATION_COMPARATORS)
        if len(cases) != 48 or len(expected) != 480 or len({p.run_id for p in expected}) != 480: raise M18V2PilotIntegrityError("frozen calibration universe mismatch")
        return cls(root.resolve(), manifest, expected)
    @property
    def result_root(self) -> Path: return self.repository_root / M18_POWER_CALIBRATION_NAMESPACE

    @staticmethod
    def _case_for(identity: M18PowerCalibrationIdentity) -> M18V3Case:
        """Deterministically construct the held-out fixture represented by its seed."""
        seed = int(hashlib.sha256((identity.case_id + ":fixture").encode()).hexdigest()[:12], 16)
        difficulty = {"low": M18Difficulty.EASY, "medium": M18Difficulty.MEDIUM, "high": M18Difficulty.HARD}[identity.difficulty]
        generated = generate_m18_v2_case(M18Cohort.A, difficulty, seed, M18Namespace.FORMAL, int(identity.case_id[-2:]))
        public = M18V2PublicCase(identity.case_id, generated.public.task_text, generated.public.capabilities, generated.public.task_config)
        # M18V2Case permits a domain-separated public identity while retaining
        # the frozen evaluator/runtime representation consumed by M18V3Case.
        source = M18V2Case(identity.case_id, generated.namespace, generated.cohort, generated.difficulty,
                           generated.generation_seed, public, generated.evaluator, generated.failure_subtype)
        return M18V3Case(source)

    def resolve(self, provenance: M18PowerCalibrationProvenance) -> M18PowerCalibrationEpisode:
        if self.expected_by_id.get(provenance.run_id) != provenance:
            raise M18PowerCalibrationPreflightError("unknown calibration logical identity")
        identity = provenance.identity
        adapter = M18V3MINDAdapter if identity.comparator_id == "mind_lite_v11" else M18V3DirectAdapter
        return M18PowerCalibrationEpisode(provenance, self._case_for(identity), adapter, identity.provider_config_id)

    @property
    def expected_by_id(self) -> dict[str, M18PowerCalibrationProvenance]:
        return {item.run_id: item for item in self.expected}

    def bridge(self) -> tuple[M18PowerCalibrationEpisode, ...]:
        rows = tuple(self.resolve(item) for item in self.expected)
        if len(rows) != 480 or len({item.run_id for item in rows}) != 480:
            raise M18PowerCalibrationPreflightError("calibration bridge cardinality mismatch")
        return rows


class M18PowerCalibrationStore:
    def __init__(self, root: Path, plan: M18PowerCalibrationPlan) -> None:
        if root.name != "pilot": raise ValueError("calibration records only belong in pilot namespace")
        self.root, self.plan, self._by_id = root, plan, {p.run_id: p for p in plan.expected}
    @property
    def stop_path(self) -> Path: return self.root / "m18_power_calibration_systematic_provider_stop_v1.json"
    def records(self) -> tuple[M18PowerCalibrationRecord, ...]:
        if not self.root.exists(): return ()
        rows=[]
        for path in sorted(self.root.glob("*.json")):
            if path == self.stop_path: continue
            try: row=M18PowerCalibrationRecord.from_dict(_read(path))
            except Exception as error: raise M18V2PilotIntegrityError("invalid calibration record") from error
            if path.stem != row.run_id or self._by_id.get(row.run_id) != row.provenance or row.provenance.manifest_hash != self.plan.manifest["manifest_hash"]: raise M18V2PilotIntegrityError("calibration admission rejected")
            rows.append(row)
        return tuple(rows)
    def missing(self) -> tuple[M18PowerCalibrationProvenance, ...]:
        admitted={r.run_id for r in self.records()}; return tuple(p for p in self.plan.expected if p.run_id not in admitted)
    def persist(self, record: M18PowerCalibrationRecord) -> M18PowerCalibrationRecord:
        if self._by_id.get(record.run_id) != record.provenance or record.provenance.manifest_hash != self.plan.manifest["manifest_hash"]: raise M18V2PilotIntegrityError("calibration provenance rejection")
        path=self.root / f"{record.run_id}.json"
        # Atomic create performs the duplicate check at the persistence
        # boundary; avoid an O(n^2) directory reread during a 480-run resume.
        if path.exists(): raise M18V2PilotIntegrityError("calibration duplicate rejection")
        _atomic(path, record.to_dict()); reread=M18PowerCalibrationRecord.from_dict(_read(path))
        if self._by_id.get(reread.run_id) != reread.provenance: raise M18V2PilotIntegrityError("calibration reread admission rejected")
        return reread
    def systematic_stop(self) -> M18V2SystematicProviderStopEvent | None:
        return None if not self.stop_path.exists() else M18V2SystematicProviderStopEvent.from_dict(_read(self.stop_path))
    def persist_stop(self, event: M18V2SystematicProviderStopEvent) -> None:
        if self.stop_path.exists():
            if self.systematic_stop() != event: raise M18V2PilotIntegrityError("conflicting calibration stop")
            return
        _atomic(self.stop_path, event.to_dict())


@dataclass(frozen=True)
class M18PowerCalibrationPreflight:
    expected: int; valid: int; missing: int; duplicates: int; invalid: int; unexpected: int; formal_records: int


class M18PowerCalibrationRunner:
    def __init__(self, plan: M18PowerCalibrationPlan, *, result_root: Path | None = None) -> None:
        self.plan=plan; root=plan.result_root if result_root is None else result_root
        if root.name != "pilot": root=root / "pilot"
        self.store=M18PowerCalibrationStore(root, plan)
    @classmethod
    def from_repository(cls, root: Path, *, result_root: Path | None = None) -> "M18PowerCalibrationRunner": return cls(M18PowerCalibrationPlan.from_repository(root), result_root=result_root)
    def _validate_dispatches(self, dispatches: Mapping[str, M18PowerCalibrationDispatch] | None) -> None:
        if dispatches is None or set(dispatches) != set(M18_POWER_CALIBRATION_COMPARATORS):
            raise M18PowerCalibrationPreflightError("both corrected calibration dispatches are required")
        for comparator in M18_POWER_CALIBRATION_COMPARATORS:
            binding = dispatches[comparator]
            if (not isinstance(binding, M18PowerCalibrationDispatch) or binding.comparator_id != comparator or
                    binding.comparator_contract_id != M18_POWER_CALIBRATION_CONTRACT or
                    binding.strict_integer_answer is not True):
                raise M18PowerCalibrationPreflightError("calibration dispatch identity rejected")

    @staticmethod
    def corrected_dispatches() -> dict[str, M18PowerCalibrationDispatch]:
        return {item: M18PowerCalibrationDispatch(item, M18_POWER_CALIBRATION_CONTRACT, True)
                for item in M18_POWER_CALIBRATION_COMPARATORS}

    def _validate_provider_configuration(self, provider_configuration: M18SharedProviderConfiguration | None) -> None:
        if provider_configuration is None or provider_configuration.config_hash != M18_POWER_CALIBRATION_PROVIDER_HASH:
            raise M18PowerCalibrationPreflightError("frozen calibration provider configuration mismatch")

    def preflight(self, *, require_empty: bool = False, historical_ids: Iterable[str] | None = None,
                  provider_configuration: M18SharedProviderConfiguration | None = None) -> M18PowerCalibrationPreflight:
        records=self.store.records(); ids=[r.run_id for r in records]
        formal = self.plan.repository_root / "evaluation/m18/results/m18_power_calibration_v1/formal"
        outcome = M18PowerCalibrationPreflight(480, len(records), len(self.store.missing()), len(ids)-len(set(ids)), 0, 0, sum(1 for _ in formal.rglob("*.json")) if formal.exists() else 0)
        collisions = set(historical_ids) & set(self.store._by_id) if historical_ids is not None else historical_calibration_collision_ids(self.plan.repository_root, self.store._by_id)
        if require_empty:
            self._validate_provider_configuration(provider_configuration)
            if len(self.plan.bridge()) != 480 or outcome.valid != 0 or outcome.missing != 480 or outcome.formal_records != 0 or collisions or self.store.systematic_stop() is not None:
                raise M18PowerCalibrationPreflightError("calibration preflight blocked")
        return outcome
    @staticmethod
    def _native_result(episode: M18PowerCalibrationEpisode, client: M18SharedProviderClient):
        """The only execution path: native adapter, environment, evaluator, and runtime."""
        if not isinstance(client, M18SharedProviderClient):
            raise M18PowerCalibrationPreflightError("shared provider client required")
        provider = M18SharedMINDProvider(client) if episode.identity.comparator_id == "mind_lite_v11" else M18SharedDirectProvider(client)
        adapter = episode.adapter_type(provider)
        return M18V3SharedExecutionHarness().dry_run(episode.case, adapter)

    def execute(self, *, provider_client: M18SharedProviderClient, dispatches: Mapping[str, M18PowerCalibrationDispatch] | None = None, limit: int | None = None, after_persist: Callable[[M18PowerCalibrationRecord], None] | None = None, historical_ids: Iterable[str] | None = None) -> tuple[M18PowerCalibrationRecord, ...]:
        self._validate_dispatches(dispatches)
        self._validate_provider_configuration(provider_client.configuration if isinstance(provider_client, M18SharedProviderClient) else None)
        if self.store.systematic_stop() is not None: raise M18V2SystematicProviderStop(self.store.systematic_stop())
        # The initial execution is the real-execution admission boundary. A
        # resume derives work solely from admitted canonical records.
        if not self.store.records(): self.preflight(require_empty=True, historical_ids=historical_ids, provider_configuration=provider_client.configuration)
        completed=[]; evidence={}
        for expected in self.store.missing()[:limit]:
            episode = self.plan.resolve(expected)
            try:
                result = self._native_result(episode, provider_client)
                row=M18PowerCalibrationRecord(expected, result.terminal, result.evaluator_outcome)
            except M18V2ProviderExecutionFailure as error:
                # Diagnostics never cross into result records; only typed stop evidence does.
                diagnostic=error.diagnostic; row=M18PowerCalibrationRecord(expected, "provider_failure", None)
                if diagnostic.is_contract_incompatibility:
                    key=(expected.identity.comparator_id, diagnostic.stage, diagnostic.category.value); evidence.setdefault(key, []).append(expected.run_id)
            persisted=self.store.persist(row); completed.append(persisted)
            if after_persist: after_persist(persisted)
            for (comparator, stage, category), ids in evidence.items():
                if len(ids) >= 2:
                    event=M18V2SystematicProviderStopEvent(comparator, stage, category, tuple(ids), len(ids))
                    self.store.persist_stop(event); raise M18V2SystematicProviderStop(event)
        return tuple(completed)


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser=argparse.ArgumentParser(description="M18 power-calibration preflight (execution requires explicit API authorization)")
    parser.add_argument("--condition", default=M18_POWER_CALIBRATION_ID); parser.add_argument("--result-root", type=Path)
    args=parser.parse_args(argv)
    if args.condition != M18_POWER_CALIBRATION_ID: parser.error("only frozen calibration condition is accepted")
    print(json.dumps(M18PowerCalibrationRunner.from_repository(Path(".")).preflight(require_empty=True, provider_configuration=M18SharedProviderConfiguration()).__dict__, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
