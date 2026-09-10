"""Frozen, isolated contracts and storage for M16 post-hoc diagnostic v1.

This module is deliberately inert: it defines identity, storage, and resume
rules only.  It never constructs a provider or executes an Agent.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from src.evaluation.m16_diagnostic_telemetry import (
    DIAGNOSTIC_REASON_TAXONOMY_VERSION,
    DIAGNOSTIC_RESULT_DIRECTORY,
    DIAGNOSTIC_SCHEMA_VERSION,
    M16DiagnosticEvent,
    diagnostic_run_id,
    validate_diagnostic_result_directory,
)


DIAGNOSTIC_PROTOCOL_VERSION = "m16-post-hoc-diagnostic-v1"
DIAGNOSTIC_RESULT_SCHEMA_VERSION = "m16-post-hoc-diagnostic-result-v1"
INSTRUMENTATION_COMMIT = "cfbcdf2"
DIAGNOSTIC_BASELINE = "mind_lite_v1"
EXPECTED_DIAGNOSTIC_MANIFEST_HASH = "4fdaa47b47f621662953531af3a0dc703d6ac46550152b49cf8d421800144c74"
HISTORICAL_RESULT_DIRECTORIES = (
    "evaluation/results/m16",
    "evaluation/results/m16_flash_lite",
    "evaluation/results/m16_deepseek_v4_flash",
    "evaluation/results/m16_deepseek_v4_flash_restart1",
)


def canonical_json(value: Any) -> str:
    """Return the one deterministic JSON representation used for identities."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class M16DiagnosticAttemptStatus(str, Enum):
    """Diagnostic terminality, intentionally separate from formal outcomes."""

    TERMINAL_VALID = "terminal_valid"
    PROVIDER_INFRASTRUCTURE_INVALID = "provider_infrastructure_invalid"
    INTERRUPTED_INCOMPLETE = "interrupted_incomplete"


_RESUMABLE = frozenset({
    M16DiagnosticAttemptStatus.PROVIDER_INFRASTRUCTURE_INVALID,
    M16DiagnosticAttemptStatus.INTERRUPTED_INCOMPLETE,
})


@dataclass(frozen=True)
class M16MindFailureDiagnosticManifest:
    """Canonical post-hoc mechanism-localization contract, not a benchmark."""

    diagnostic_protocol_version: str
    post_hoc: bool
    purpose: str
    instrumentation_commit: str
    telemetry_schema_version: str
    reason_taxonomy_version: str
    provider_identity: str
    provider_config_hash: str
    request_model: str
    documented_model_version: str
    returned_model_observation_policy: str
    mind_prompt_hash: str
    mind_schema_hash: str
    calculator_schema_hash: str
    source_suite_version: str
    source_suite_hash: str
    source_split_hash: str
    source_case_count: int
    baseline: str
    repetitions: int
    expected_run_count: int
    result_directory: str
    ordering_rule: str
    resume_semantics: str
    historical_exclusions: tuple[str, ...]
    claim_boundary: str

    def __post_init__(self) -> None:
        if not self.post_hoc or self.purpose != "failure_mechanism_localization":
            raise ValueError("diagnostic manifest must remain a post-hoc localization contract")
        if self.source_case_count != 96 or self.repetitions != 1 or self.expected_run_count != 96:
            raise ValueError("diagnostic v1 requires exactly 96 MIND-only runs")
        if self.baseline != DIAGNOSTIC_BASELINE:
            raise ValueError("diagnostic v1 admits only the MIND baseline")
        if self.result_directory != str(DIAGNOSTIC_RESULT_DIRECTORY).replace("\\", "/"):
            raise ValueError("diagnostic manifest result directory is not isolated")
        if tuple(self.historical_exclusions) != HISTORICAL_RESULT_DIRECTORIES:
            raise ValueError("historical exclusions must be frozen")
        if not all(isinstance(value, str) and value for value in self.to_dict().values() if isinstance(value, str)):
            raise ValueError("diagnostic manifest contains an empty identity")

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.__dict__)
        data["historical_exclusions"] = list(self.historical_exclusions)
        return data

    @property
    def manifest_hash(self) -> str:
        return hashlib.sha256(canonical_json(self.to_dict()).encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "M16MindFailureDiagnosticManifest":
        data = dict(data)
        data["historical_exclusions"] = tuple(data["historical_exclusions"])
        return cls(**data)


def load_frozen_m16_mind_failure_diagnostic_manifest() -> M16MindFailureDiagnosticManifest:
    """Derive v1 identity from the tracked, byte-frozen DeepSeek configuration."""
    root = Path(__file__).resolve().parents[2]
    config_bytes = (root / "evaluation" / "config" / "m16_deepseek_v4_flash_v1.json").read_bytes()
    config = json.loads(config_bytes.decode("utf-8"))
    return M16MindFailureDiagnosticManifest(
        diagnostic_protocol_version=DIAGNOSTIC_PROTOCOL_VERSION,
        post_hoc=True,
        purpose="failure_mechanism_localization",
        instrumentation_commit=INSTRUMENTATION_COMMIT,
        telemetry_schema_version=DIAGNOSTIC_SCHEMA_VERSION,
        reason_taxonomy_version=DIAGNOSTIC_REASON_TAXONOMY_VERSION,
        provider_identity=config["formal_provider_identity"],
        provider_config_hash=hashlib.sha256(config_bytes).hexdigest(),
        request_model=config["request_model_id"],
        documented_model_version=config["official_documented_model_version"],
        returned_model_observation_policy=config["returned_model_observation_policy"],
        mind_prompt_hash=config["MIND"]["prompt_hash"],
        mind_schema_hash=config["MIND"]["schema_hash"],
        calculator_schema_hash=config["tool"]["tool_schema_hash"],
        source_suite_version=config["suite"]["version"],
        source_suite_hash=config["suite"]["hash"],
        source_split_hash=config["split_hash"],
        source_case_count=96,
        baseline=DIAGNOSTIC_BASELINE,
        repetitions=1,
        expected_run_count=96,
        result_directory=str(DIAGNOSTIC_RESULT_DIRECTORY).replace("\\", "/"),
        ordering_rule="case-id-ascending/repetition-1",
        resume_semantics="terminal-immutable;provider-infrastructure-invalid-and-interrupted-resumable;partial-attempt-events-never-merge",
        historical_exclusions=HISTORICAL_RESULT_DIRECTORIES,
        claim_boundary=("post-hoc exploratory mechanism localization only; does not explain historical failures "
                        "without separate historical evidence"),
    )


@dataclass(frozen=True)
class M16DiagnosticRunDefinition:
    manifest_hash: str
    public_case_id: str
    repetition: int = 1

    @property
    def run_id(self) -> str:
        return diagnostic_run_id(self.manifest_hash, self.public_case_id, self.repetition)

    def attempt_id(self, attempt_number: int) -> str:
        if not isinstance(attempt_number, int) or attempt_number < 1:
            raise ValueError("attempt number begins at 1")
        return f"{self.run_id}:a{attempt_number}"


def diagnostic_schedule(manifest: M16MindFailureDiagnosticManifest, public_case_ids: Iterable[str]) -> tuple[M16DiagnosticRunDefinition, ...]:
    ids = tuple(sorted(public_case_ids))
    if len(ids) != manifest.source_case_count or len(set(ids)) != len(ids):
        raise ValueError("diagnostic v1 requires exactly 96 unique public case IDs")
    definitions = tuple(M16DiagnosticRunDefinition(manifest.manifest_hash, identifier) for identifier in ids)
    if len({item.run_id for item in definitions}) != manifest.expected_run_count:
        raise ValueError("diagnostic run identities are not unique")
    return definitions


@dataclass(frozen=True)
class M16DiagnosticAttemptRecord:
    schema_version: str
    manifest_hash: str
    run_id: str
    attempt_id: str
    attempt_number: int
    public_case_id: str
    repetition: int
    status: M16DiagnosticAttemptStatus
    observed_outcome: str
    telemetry_event_count: int

    def __post_init__(self) -> None:
        if self.schema_version != DIAGNOSTIC_RESULT_SCHEMA_VERSION:
            raise ValueError("unknown diagnostic result schema")
        if self.attempt_number < 1 or self.repetition != 1 or self.telemetry_event_count < 0:
            raise ValueError("invalid diagnostic attempt counters")
        if not self.run_id.startswith("m16diag:v1:") or not self.manifest_hash:
            raise ValueError("diagnostic record identity is invalid")

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.__dict__)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "M16DiagnosticAttemptRecord":
        data = dict(data)
        data["status"] = M16DiagnosticAttemptStatus(data["status"])
        return cls(**data)


class M16MindFailureDiagnosticStore:
    """Append-only, manifest-bound diagnostic results and event traces."""

    def __init__(self, directory: str | Path, manifest: M16MindFailureDiagnosticManifest) -> None:
        self.directory = validate_diagnostic_result_directory(directory)
        self.manifest = manifest
        self.manifest_path = self.directory / "diagnostic_manifest_v1.json"
        self.attempts_path = self.directory / "diagnostic_attempts_v1.jsonl"
        self.events_path = self.directory / "diagnostic_stage_events_v1.jsonl"

    def initialize(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        allowed = {self.manifest_path.name, self.attempts_path.name, self.events_path.name}
        unknown = {item.name for item in self.directory.iterdir()} - allowed
        if unknown:
            raise ValueError("diagnostic result directory contains unrelated files")
        if self.manifest_path.exists():
            existing = M16MindFailureDiagnosticManifest.from_dict(json.loads(self.manifest_path.read_text(encoding="utf-8")))
            if existing.manifest_hash != self.manifest.manifest_hash:
                raise ValueError("foreign diagnostic manifest")
        else:
            if any(path.exists() and path.stat().st_size for path in (self.attempts_path, self.events_path)):
                raise ValueError("diagnostic records require a manifest")
            self.manifest_path.write_text(canonical_json(self.manifest.to_dict()), encoding="utf-8")
        self.load_attempts(); self.load_events()

    def load_attempts(self) -> tuple[M16DiagnosticAttemptRecord, ...]:
        if not self.attempts_path.exists():
            return ()
        records: list[M16DiagnosticAttemptRecord] = []
        seen: set[str] = set()
        for line in self.attempts_path.read_text(encoding="utf-8").splitlines():
            try:
                record = M16DiagnosticAttemptRecord.from_dict(json.loads(line))
            except Exception as error:
                raise ValueError("malformed diagnostic attempt record") from error
            if record.manifest_hash != self.manifest.manifest_hash or record.attempt_id in seen:
                raise ValueError("foreign or duplicate diagnostic attempt")
            seen.add(record.attempt_id); records.append(record)
        return tuple(records)

    def load_events(self) -> tuple[dict[str, Any], ...]:
        if not self.events_path.exists():
            return ()
        events: list[dict[str, Any]] = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError("malformed diagnostic event record") from error
            if set(record) != {"manifest_hash", "run_id", "attempt_id", "event"} or record["manifest_hash"] != self.manifest.manifest_hash:
                raise ValueError("foreign diagnostic event")
            event = record["event"]
            if not isinstance(event, dict):
                raise ValueError("invalid diagnostic event payload")
            required = {"schema_version", "stage_name", "stage_ordinal", "success", "normalized_reason", "selected_capability", "selected_strategy", "action_type", "tool_name", "provider_request_count", "model_call_count", "session_phase", "terminal_category", "metadata"}
            if set(event) != required or event["schema_version"] != DIAGNOSTIC_SCHEMA_VERSION:
                raise ValueError("invalid diagnostic event payload")
            if event["metadata"] and set(event["metadata"]) - {"attempt_number", "diagnostic_run_id", "resume_attempt"}:
                raise ValueError("unsafe diagnostic event metadata")
            events.append(record)
        return tuple(events)

    def append_attempt(self, record: M16DiagnosticAttemptRecord) -> None:
        if record.manifest_hash != self.manifest.manifest_hash:
            raise ValueError("diagnostic attempt manifest mismatch")
        if record.attempt_id in {item.attempt_id for item in self.load_attempts()}:
            raise ValueError("diagnostic attempt already exists")
        if record.run_id in self.completed_run_ids():
            raise ValueError("completed diagnostic runs are immutable and never rerun")
        self._append(self.attempts_path, record.to_dict())

    def append_events(self, run_id: str, attempt_id: str, events: Iterable[M16DiagnosticEvent]) -> None:
        values = tuple(events)
        if any(not isinstance(event, M16DiagnosticEvent) for event in values):
            raise TypeError("diagnostic events must use the frozen event model")
        if tuple(event.stage_ordinal for event in values) != tuple(range(1, len(values) + 1)):
            raise ValueError("diagnostic event order is not canonical")
        known = {(item["run_id"], item["attempt_id"]) for item in self.load_events()}
        if (run_id, attempt_id) in known:
            raise ValueError("diagnostic attempt events already exist")
        for event in values:
            self._append(self.events_path, {
                "manifest_hash": self.manifest.manifest_hash,
                "run_id": run_id,
                "attempt_id": attempt_id,
                "event": event.to_dict(),
            })

    def completed_run_ids(self) -> frozenset[str]:
        return frozenset(item.run_id for item in self.load_attempts() if item.status not in _RESUMABLE)

    def next_attempt_number(self, run_id: str) -> int:
        used = [item.attempt_number for item in self.load_attempts() if item.run_id == run_id]
        for event in self.load_events():
            if event["run_id"] == run_id:
                suffix = event["attempt_id"].rsplit(":a", 1)
                if len(suffix) == 2 and suffix[1].isdigit():
                    used.append(int(suffix[1]))
        return max(used, default=0) + 1

    @staticmethod
    def _append(path: Path, value: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(value) + "\n")
