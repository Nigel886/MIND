"""Append-only, manifest-bound JSONL storage for M16 attempts."""
from __future__ import annotations
import json
from pathlib import Path
from src.evaluation.m16_benchmark_contracts import M16FormalExecutionManifest, M16RunAttemptRecord, M16FailureCategory


_RESUMABLE_CATEGORIES = frozenset({
    M16FailureCategory.PROVIDER_INFRASTRUCTURE_INVALID_RUN,
    M16FailureCategory.INTERRUPTED_INCOMPLETE,
})

class M16ResultStore:
    def __init__(self, directory: str | Path, manifest: M16FormalExecutionManifest) -> None:
        self.directory = Path(directory); self.manifest = manifest
        self.manifest_path = self.directory / "formal_execution_manifest_v1.json"
        self.records_path = self.directory / "formal_run_attempts_v1.jsonl"

    def initialize(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        unknown = {p.name for p in self.directory.iterdir()} - {self.manifest_path.name, self.records_path.name}
        if unknown: raise ValueError("result directory contains unrelated files")
        if self.manifest_path.exists():
            existing = M16FormalExecutionManifest.from_dict(json.loads(self.manifest_path.read_text(encoding="utf-8")))
            if existing.manifest_hash != self.manifest.manifest_hash: raise ValueError("incompatible formal manifest")
        else:
            if self.records_path.exists() and self.records_path.stat().st_size: raise ValueError("records without manifest")
            self.manifest_path.write_text(json.dumps(self.manifest.to_dict(), sort_keys=True, separators=(",",":")), encoding="utf-8")
        self.load_records()

    def load_records(self) -> tuple[M16RunAttemptRecord, ...]:
        if not self.records_path.exists(): return ()
        records=[]; seen=set()
        for line in self.records_path.read_text(encoding="utf-8").splitlines():
            try: record=M16RunAttemptRecord.from_dict(json.loads(line))
            except Exception as error: raise ValueError("malformed result JSONL") from error
            if record.manifest_hash != self.manifest.manifest_hash or record.attempt_id in seen: raise ValueError("conflicting result record")
            seen.add(record.attempt_id); records.append(record)
        return tuple(records)

    def append(self, record: M16RunAttemptRecord) -> None:
        if record.manifest_hash != self.manifest.manifest_hash: raise ValueError("record manifest mismatch")
        if record.attempt_id in {r.attempt_id for r in self.load_records()}: raise ValueError("attempt record already exists")
        with self.records_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record.to_dict(), sort_keys=True, separators=(",",":"), ensure_ascii=False) + "\n")

    def completed_run_ids(self) -> frozenset[str]:
        """Return only run IDs with at least one immutable terminal attempt."""
        return frozenset(
            record.run_id
            for record in self.load_records()
            if record.failure_category not in _RESUMABLE_CATEGORIES
        )
