"""Read-only post-hoc analysis for completed M16 Diagnostic v1 artifacts."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from src.evaluation.m16_mind_failure_diagnostic_v1 import EXPECTED_DIAGNOSTIC_MANIFEST_HASH, M16MindFailureDiagnosticManifest


RESULT_DIRECTORY = Path("evaluation/results/m16_mind_failure_diagnostic_v1")
OUTPUT_DIRECTORY = Path("evaluation/analysis/m16_mind_failure_diagnostic_v1")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def analyze(result_directory: str | Path = RESULT_DIRECTORY) -> dict[str, Any]:
    """Return derived summaries without changing any diagnostic record."""
    directory = Path(result_directory)
    manifest = M16MindFailureDiagnosticManifest.from_dict(json.loads((directory / "diagnostic_manifest_v1.json").read_text(encoding="utf-8")))
    if manifest.manifest_hash != EXPECTED_DIAGNOSTIC_MANIFEST_HASH:
        raise ValueError("unexpected Diagnostic v1 manifest")
    attempts = _read_jsonl(directory / "diagnostic_attempts_v1.jsonl")
    events = _read_jsonl(directory / "diagnostic_stage_events_v1.jsonl")
    by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in events:
        if item["manifest_hash"] != manifest.manifest_hash:
            raise ValueError("foreign diagnostic event")
        by_run[item["run_id"]].append(item)
    if len(attempts) != 96 or len(by_run) != 96 or len({item["run_id"] for item in attempts}) != 96:
        raise ValueError("incomplete or duplicate diagnostic run set")
    if any(item["manifest_hash"] != manifest.manifest_hash for item in attempts):
        raise ValueError("foreign diagnostic attempt")

    signatures: Counter[str] = Counter()
    for run_id, values in by_run.items():
        ordered = sorted(values, key=lambda item: item["event"]["stage_ordinal"])
        if [item["event"]["stage_ordinal"] for item in ordered] != list(range(1, len(ordered) + 1)):
            raise ValueError(f"non-canonical event order for {run_id}")
        signatures[">".join(item["event"]["stage_name"] for item in ordered)] += 1

    stage_counts = Counter(item["event"]["stage_name"] for item in events)
    reason_counts = Counter(item["event"]["normalized_reason"] for item in events if item["event"]["normalized_reason"] is not None)
    terminal_rows: list[dict[str, Any]] = []
    for stage in ("terminal_adapter_action", "terminal_reason"):
        values = [item for item in events if item["event"]["stage_name"] == stage]
        payloads = Counter(
            (item["event"]["action_type"], item["event"]["terminal_category"], item["event"]["normalized_reason"])
            for item in values
        )
        terminal_rows.append({
            "stage": stage,
            "count": len(values),
            "per_run": len(values) / 96,
            "ordinals": json.dumps(dict(sorted(Counter(item["event"]["stage_ordinal"] for item in values).items())), separators=(",", ":")),
            "payload_variants": json.dumps(
                [{"action_type": key[0], "terminal_category": key[1], "normalized_reason": key[2], "count": count} for key, count in sorted(payloads.items(), key=lambda item: str(item[0]))],
                sort_keys=True, separators=(",", ":"),
            ),
        })

    strata: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"run_count": 0, "malformed_structured_output": 0, "admission_failure": 0, "agent_fail": 0})
    for attempt in attempts:
        _, _, family, difficulty, _ = attempt["public_case_id"].split(".")
        row = strata[(family, difficulty)]
        row["run_count"] += 1
        row["agent_fail"] += int(attempt["observed_outcome"] == "agent_fail")
        run_reasons = Counter(item["event"]["normalized_reason"] for item in by_run[attempt["run_id"]])
        row["malformed_structured_output"] += run_reasons["malformed_structured_output"]
        row["admission_failure"] += run_reasons["admission_failure"]

    return {
        "manifest": manifest,
        "attempts": attempts,
        "events": events,
        "signatures": signatures,
        "stage_counts": stage_counts,
        "reason_counts": reason_counts,
        "terminal_rows": terminal_rows,
        "strata": strata,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def write_summaries(result_directory: str | Path = RESULT_DIRECTORY, output_directory: str | Path = OUTPUT_DIRECTORY) -> dict[str, Any]:
    """Write derived analysis tables only; raw result files are never opened for write."""
    report = analyze(result_directory)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    attempts, events = report["attempts"], report["events"]
    integrity = {
        "manifest_hash": report["manifest"].manifest_hash,
        "expected_runs": 96,
        "attempts": len(attempts),
        "terminal_completed": sum(item["status"] == "terminal_valid" for item in attempts),
        "incomplete": sum(item["status"] == "interrupted_incomplete" for item in attempts),
        "unique_run_ids": len({item["run_id"] for item in attempts}),
        "duplicate_run_ids": len(attempts) - len({item["run_id"] for item in attempts}),
        "telemetry_events": len(events),
        "raw_results_modified": False,
        "post_hoc_exploratory": True,
    }
    (output / "run_integrity.json").write_text(json.dumps(integrity, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    _write_csv(output / "event_sequence_signatures.csv", [{"signature": key, "run_count": value} for key, value in sorted(report["signatures"].items())], ["signature", "run_count"])
    _write_csv(output / "stage_counts.csv", [{"stage": key, "count": value} for key, value in sorted(report["stage_counts"].items())], ["stage", "count"])
    _write_csv(output / "reason_counts.csv", [{"reason": key, "count": value} for key, value in sorted(report["reason_counts"].items())], ["reason", "count"])
    rows = [{"family": family, "difficulty": difficulty, **values} for (family, difficulty), values in sorted(report["strata"].items())]
    family: dict[str, dict[str, int]] = defaultdict(lambda: {"run_count": 0, "malformed_structured_output": 0, "admission_failure": 0, "agent_fail": 0})
    for row in rows:
        target = family[row["family"]]
        for key in target: target[key] += row[key]
    _write_csv(output / "family_breakdown.csv", [{"family": key, **value} for key, value in sorted(family.items())], ["family", "run_count", "malformed_structured_output", "admission_failure", "agent_fail"])
    difficulty: dict[str, dict[str, int]] = defaultdict(lambda: {"run_count": 0, "malformed_structured_output": 0, "admission_failure": 0, "agent_fail": 0})
    for row in rows:
        target = difficulty[row["difficulty"]]
        for key in target: target[key] += row[key]
    _write_csv(output / "difficulty_breakdown.csv", [{"difficulty": key, **value} for key, value in sorted(difficulty.items())], ["difficulty", "run_count", "malformed_structured_output", "admission_failure", "agent_fail"])
    _write_csv(output / "terminal_event_audit.csv", report["terminal_rows"], ["stage", "count", "per_run", "ordinals", "payload_variants"])
    return integrity


if __name__ == "__main__":
    print(json.dumps(write_summaries(), sort_keys=True))
