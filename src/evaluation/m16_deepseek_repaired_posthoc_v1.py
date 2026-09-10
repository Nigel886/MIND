"""Frozen contracts and isolated storage for repaired M16 post-hoc evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any

from src.evaluation.m16_benchmark_contracts import M16BaselineID, M16FailureCategory, M16FormalBudget, M16RunAttemptRecord


RESULT_DIRECTORY = "evaluation/results/m16_deepseek_repaired_posthoc_v1"
REPAIR_COMMIT = "5b942df"
MIND_REQUEST_HASH = "b1e64996a00eb237b7c26cab21103cdc68c392384b06e19c06b822f16a74edf5"
MIND_SCHEMA_HASH = "f041d3f276051380edb7e3a7d520aec770592efb5a348616999e8d9197c73ccf"
DIRECT_REQUEST_HASH = "db59e3676a3fd2c719c7a18eded0db9443c3a83303e3831431b808990ae87078"
PROVIDER_CONFIG_HASH = "c074c0e08e6b7be9a93b955a5c5f85da52bb7e9cf83601477ab2e18dad4bc780"
SUITE_HASH = "a450c6fa2955136da5d4db08b892af442ab7be66034412739d91e7cbf076445c"
SPLIT_HASH = "a41ca5a326da4f722de1fcca4c7a4b85fcf860767ba1bb0311aa6cc4176aefe3"
HISTORICAL_EXCLUSIONS = (
    "evaluation/results/m16", "evaluation/results/m16_flash_lite",
    "evaluation/results/m16_deepseek_v4_flash",
    "evaluation/results/m16_deepseek_v4_flash_restart1",
    "evaluation/results/m16_mind_failure_diagnostic_v1",
)
_RESUMABLE = frozenset({M16FailureCategory.PROVIDER_INFRASTRUCTURE_INVALID_RUN, M16FailureCategory.INTERRUPTED_INCOMPLETE})


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class M16RepairedPostHocManifest:
    protocol_version: str = "1.2.0"
    post_hoc: bool = True
    experiment_purpose: str = "repaired_agent_quality_evaluation"
    repair_commit: str = REPAIR_COMMIT
    mind_request_template_hash: str = MIND_REQUEST_HASH
    canonical_schema_hash: str = MIND_SCHEMA_HASH
    direct_request_hash: str = DIRECT_REQUEST_HASH
    provider_config_hash: str = PROVIDER_CONFIG_HASH
    provider: str = "DeepSeek API"
    request_model_id: str = "deepseek-v4-flash"
    returned_model_alias: str = "deepseek-flash"
    suite_version: str = "1.0.0"
    suite_hash: str = SUITE_HASH
    split_hash: str = SPLIT_HASH
    suite_generation_protocol_version: str = "1.1.0"
    completion_semantics_version: str = "m16_completion_v2"
    baseline_ids: tuple[M16BaselineID, ...] = (M16BaselineID.MIND_LITE_V1, M16BaselineID.DIRECT_TOOL_CALLING)
    repetitions: int = 5
    expected_runs: int = 960
    ordering_policy: str = "repetition-major/case-major/counterbalanced-v1"
    budget_contract: M16FormalBudget = field(default_factory=M16FormalBudget)
    result_namespace: str = RESULT_DIRECTORY
    resume_policy: str = "terminal-valid-immutable;provider-infrastructure-invalid-and-interrupted-resumable"
    historical_exclusions: tuple[str, ...] = HISTORICAL_EXCLUSIONS
    claim_boundary: str = "post-hoc repaired implementation evaluation; no pooling with historical M16 results"

    def __post_init__(self) -> None:
        if not self.post_hoc or self.experiment_purpose != "repaired_agent_quality_evaluation": raise ValueError("invalid post-hoc purpose")
        if self.repetitions != 5 or self.expected_runs != 960 or set(self.baseline_ids) != set(M16BaselineID): raise ValueError("invalid repaired schedule")
        if self.result_namespace in self.historical_exclusions: raise ValueError("result namespace must be isolated")
        if tuple(self.historical_exclusions) != HISTORICAL_EXCLUSIONS: raise ValueError("historical exclusions are frozen")
        if not isinstance(self.budget_contract, M16FormalBudget): raise TypeError("budget_contract must be M16FormalBudget")

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.__dict__)
        data["baseline_ids"] = [item.value for item in self.baseline_ids]
        data["budget_contract"] = self.budget_contract.to_dict()
        data["historical_exclusions"] = list(self.historical_exclusions)
        return data

    @property
    def manifest_hash(self) -> str:
        return hashlib.sha256(_canonical(self.to_dict()).encode()).hexdigest()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "M16RepairedPostHocManifest":
        data = dict(data)
        data["baseline_ids"] = tuple(M16BaselineID(item) for item in data["baseline_ids"])
        data["budget_contract"] = M16FormalBudget(**data["budget_contract"])
        data["historical_exclusions"] = tuple(data["historical_exclusions"])
        return cls(**data)


def load_repaired_posthoc_manifest() -> M16RepairedPostHocManifest:
    return M16RepairedPostHocManifest()


@dataclass(frozen=True)
class M16RepairedPostHocRunDefinition:
    manifest_hash: str
    evaluation_id: str
    baseline_id: M16BaselineID
    repetition: int
    case_index: int

    @property
    def run_id(self) -> str:
        return f"m16-repaired-posthoc-v1:{self.manifest_hash}:{self.evaluation_id}:{self.baseline_id.value}:r{self.repetition}"

    def attempt_id(self, attempt_number: int) -> str:
        if attempt_number < 1: raise ValueError("attempt number begins at 1")
        return f"{self.run_id}:a{attempt_number}"


def repaired_posthoc_schedule(manifest: M16RepairedPostHocManifest, evaluation_ids: tuple[str, ...]) -> tuple[M16RepairedPostHocRunDefinition, ...]:
    ordered = tuple(sorted(evaluation_ids))
    if len(ordered) != 96 or len(set(ordered)) != 96: raise ValueError("repaired suite must contain 96 unique cases")
    output = []
    for repetition in range(1, manifest.repetitions + 1):
        for index, evaluation_id in enumerate(ordered):
            baselines = manifest.baseline_ids if (index + repetition) % 2 == 0 else tuple(reversed(manifest.baseline_ids))
            output.extend(M16RepairedPostHocRunDefinition(manifest.manifest_hash, evaluation_id, baseline, repetition, index) for baseline in baselines)
    if len(output) != manifest.expected_runs or len({item.run_id for item in output}) != manifest.expected_runs: raise ValueError("repaired schedule is not unique")
    return tuple(output)


class M16RepairedPostHocResultStore:
    def __init__(self, directory: str | Path, manifest: M16RepairedPostHocManifest) -> None:
        self.directory, self.manifest = Path(directory), manifest
        self.manifest_path = self.directory / "repaired_posthoc_manifest_v1.json"
        self.records_path = self.directory / "repaired_posthoc_attempts_v1.jsonl"

    def inspect(self) -> tuple[M16RunAttemptRecord, ...]:
        if not self.directory.exists(): return ()
        if not self.directory.is_dir(): raise ValueError("result namespace is not a directory")
        allowed = {self.manifest_path.name, self.records_path.name}
        if {item.name for item in self.directory.iterdir()} - allowed: raise ValueError("result namespace contains unrelated files")
        if not self.manifest_path.exists():
            if self.records_path.exists() and self.records_path.stat().st_size: raise ValueError("records require a manifest")
            return ()
        existing = M16RepairedPostHocManifest.from_dict(json.loads(self.manifest_path.read_text(encoding="utf-8")))
        if existing.manifest_hash != self.manifest.manifest_hash: raise ValueError("foreign repaired manifest")
        return self.load_records()

    def initialize(self) -> None:
        records = self.inspect()
        self.directory.mkdir(parents=True, exist_ok=True)
        if not self.manifest_path.exists(): self.manifest_path.write_text(_canonical(self.manifest.to_dict()), encoding="utf-8")
        if records: self.load_records()

    def load_records(self) -> tuple[M16RunAttemptRecord, ...]:
        if not self.records_path.exists(): return ()
        records, attempts = [], set()
        for line in self.records_path.read_text(encoding="utf-8").splitlines():
            record = M16RunAttemptRecord.from_dict(json.loads(line))
            if record.manifest_hash != self.manifest.manifest_hash or record.attempt_id in attempts: raise ValueError("foreign or duplicate repaired record")
            attempts.add(record.attempt_id); records.append(record)
        return tuple(records)

    def append(self, record: M16RunAttemptRecord) -> None:
        if record.manifest_hash != self.manifest.manifest_hash: raise ValueError("record manifest mismatch")
        if record.attempt_id in {item.attempt_id for item in self.load_records()}: raise ValueError("duplicate attempt")
        with self.records_path.open("a", encoding="utf-8", newline="\n") as handle: handle.write(_canonical(record.to_dict()) + "\n")

    def completed_run_ids(self) -> frozenset[str]:
        return frozenset(item.run_id for item in self.load_records() if item.failure_category not in _RESUMABLE)
