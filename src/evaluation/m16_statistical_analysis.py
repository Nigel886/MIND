"""Deterministic, case-clustered analysis for the completed M16 restart1 run.

This module deliberately reads only a caller-supplied result directory.  It
does not import suites, providers, agents, or benchmark runners.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


MIND = "mind_lite_v1"
DIRECT = "direct_tool_calling"
BASELINES = (MIND, DIRECT)
PERMUTATION_SEED = 913202609
BOOTSTRAP_SEED = 913202610
PERMUTATION_DRAWS = 100_000
BOOTSTRAP_DRAWS = 10_000
EXPECTED_MANIFEST_HASH = "559c5e5dec527d5abffedb409725b89580818bd832846f64adedcd328d081ac9"


def _canonical(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_restart1_records(directory: str | Path) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Read, validate, and return only terminal restart1 records."""
    root = Path(directory)
    manifest = json.loads((root / "formal_execution_manifest_v1.json").read_text(encoding="utf-8"))
    records = tuple(
        json.loads(line)
        for line in (root / "formal_run_attempts_v1.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    validate_dataset(manifest, records)
    return manifest, records


def validate_dataset(manifest: dict[str, Any], records: Iterable[dict[str, Any]]) -> None:
    records = tuple(records)
    # The frozen manifest hash is a derived contract property and is recorded
    # on every append-only attempt, not serialized as a field in the manifest.
    if {r.get("manifest_hash") for r in records} != {EXPECTED_MANIFEST_HASH}:
        raise ValueError("unexpected restart1 manifest hash")
    if len(records) != 960 or len({r.get("run_id") for r in records}) != 960:
        raise ValueError("expected 960 unique terminal run records")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.get("baseline_id") not in BASELINES or record.get("repetition") not in range(1, 6):
            raise ValueError("invalid baseline or repetition")
        grouped[record["evaluation_id"]].append(record)
    if len(grouped) != 96:
        raise ValueError("expected 96 case clusters")
    for case_records in grouped.values():
        if len(case_records) != 10:
            raise ValueError("each case must have 10 records")
        for baseline in BASELINES:
            reps = [r["repetition"] for r in case_records if r["baseline_id"] == baseline]
            if sorted(reps) != [1, 2, 3, 4, 5]:
                raise ValueError("each baseline must have five repetitions per case")


def case_rows(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["evaluation_id"]].append(record)
    rows = []
    for evaluation_id in sorted(grouped):
        values = grouped[evaluation_id]
        reference = values[0]
        by_baseline = {
            baseline: sorted((r for r in values if r["baseline_id"] == baseline), key=lambda r: r["repetition"])
            for baseline in BASELINES
        }
        mind_successes = sum(bool(r["success"]) for r in by_baseline[MIND])
        direct_successes = sum(bool(r["success"]) for r in by_baseline[DIRECT])
        rows.append({
            "case_id": evaluation_id,
            "family": reference["task_family"],
            "difficulty": reference["difficulty"],
            "mind_successes": mind_successes,
            "direct_successes": direct_successes,
            "mind_rate": mind_successes / 5,
            "direct_rate": direct_successes / 5,
            "paired_difference": (mind_successes - direct_successes) / 5,
        })
    return rows


def _percentile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    index = (len(values) - 1) * fraction
    low, high = math.floor(index), math.ceil(index)
    return values[low] + (values[high] - values[low]) * (index - low)


def _bootstrap(rows: list[dict[str, Any]], draws: int, seed: int) -> dict[str, tuple[float, float]]:
    rng = random.Random(seed)
    mind, direct, difference = [], [], []
    count = len(rows)
    for _ in range(draws):
        sample = [rows[rng.randrange(count)] for _ in range(count)]
        m = sum(r["mind_rate"] for r in sample) / count
        d = sum(r["direct_rate"] for r in sample) / count
        mind.append(m); direct.append(d); difference.append(m - d)
    return {
        "mind": (_percentile(mind, .025), _percentile(mind, .975)),
        "direct": (_percentile(direct, .025), _percentile(direct, .975)),
        "difference": (_percentile(difference, .025), _percentile(difference, .975)),
    }


def paired_permutation(rows: list[dict[str, Any]], draws: int = PERMUTATION_DRAWS, seed: int = PERMUTATION_SEED) -> dict[str, Any]:
    """Swap complete paired case vectors, rather than independent rows."""
    observed = sum(r["paired_difference"] for r in rows) / len(rows)
    rng = random.Random(seed)
    extreme = 0
    for _ in range(draws):
        value = sum((r["paired_difference"] if rng.getrandbits(1) else -r["paired_difference"]) for r in rows) / len(rows)
        extreme += abs(value) >= abs(observed)
    return {"observed_difference": observed, "p_value_two_sided": (extreme + 1) / (draws + 1), "draws": draws, "seed": seed, "method": "monte_carlo_paired_case_clustered_label_permutation"}


def stratum_result(label: str, rows: list[dict[str, Any]], bootstrap_seed: int) -> dict[str, Any]:
    if not rows:
        raise ValueError("empty stratum")
    mind = sum(r["mind_rate"] for r in rows) / len(rows)
    direct = sum(r["direct_rate"] for r in rows) / len(rows)
    intervals = _bootstrap(rows, BOOTSTRAP_DRAWS, bootstrap_seed)
    return {
        "stratum": label, "case_count": len(rows), "mind_rate": mind, "direct_rate": direct,
        "paired_difference": mind - direct, "mind_ci_low": intervals["mind"][0], "mind_ci_high": intervals["mind"][1],
        "direct_ci_low": intervals["direct"][0], "direct_ci_high": intervals["direct"][1],
        "difference_ci_low": intervals["difference"][0], "difference_ci_high": intervals["difference"][1],
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _svg_forest(path: Path, rows: list[dict[str, Any]]) -> None:
    width, left, row_height = 900, 260, 34
    height = 90 + len(rows) * row_height
    values = [v for r in rows for v in (r["difference_ci_low"], r["difference_ci_high"], 0.0)]
    bound = max(.1, max(abs(v) for v in values))
    scale = lambda v: left + (v + bound) / (2 * bound) * (width - left - 60)
    items = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<style>text{font-family:Arial,sans-serif;font-size:13px}.primary{font-weight:bold}.explore{fill:#444}.line{stroke:#276fbf;stroke-width:2}.zero{stroke:#777;stroke-dasharray:4 4}.point{fill:#276fbf}</style>', f'<line class="zero" x1="{scale(0):.1f}" y1="50" x2="{scale(0):.1f}" y2="{height-20}"/>']
    for index, row in enumerate(rows):
        y = 70 + index * row_height
        style = "primary" if row["stratum"] == "Overall (PRIMARY)" else "explore"
        items.append(f'<text class="{style}" x="10" y="{y+4}">{row["stratum"]}</text>')
        items.append(f'<line class="line" x1="{scale(row["difference_ci_low"]):.1f}" y1="{y}" x2="{scale(row["difference_ci_high"]):.1f}" y2="{y}"/>')
        items.append(f'<circle class="point" cx="{scale(row["paired_difference"]):.1f}" cy="{y}" r="4"/>')
        items.append(f'<text x="{width-55}" y="{y+4}">{row["paired_difference"]*100:.1f}%</text>')
    items.append('</svg>'); path.write_text("\n".join(items), encoding="utf-8")


def _svg_difference_distribution(path: Path, rows: list[dict[str, Any]]) -> None:
    counts = Counter(r["paired_difference"] for r in rows); keys = [x / 5 for x in range(-5, 6)]
    width, height, base = 800, 360, 300; maximum = max(counts.values(), default=1)
    items = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><style>text{{font-family:Arial,sans-serif;font-size:13px}}.bar{{fill:#276fbf}}</style><text x="30" y="28">Case-level paired five-repetition success differences (N=96)</text><line x1="55" y1="{base}" x2="770" y2="{base}" stroke="#333"/>']
    for i, key in enumerate(keys):
        x, count = 70 + i * 64, counts[key]; h = 210 * count / maximum
        items.append(f'<rect class="bar" x="{x}" y="{base-h:.1f}" width="38" height="{h:.1f}"/><text x="{x}" y="325">{key:+.1f}</text><text x="{x+10}" y="{base-h-6:.1f}">{count}</text>')
    items.append('</svg>'); path.write_text("\n".join(items), encoding="utf-8")


def _svg_repetition(path: Path, rows: list[dict[str, Any]]) -> None:
    width, height, left, bottom = 800, 360, 80, 290
    rates = {b: [] for b in BASELINES}
    for repetition in range(1, 6):
        for baseline in BASELINES:
            subset = [r for r in rows if r["repetition"] == repetition and r["baseline_id"] == baseline]
            rates[baseline].append(sum(bool(r["success"]) for r in subset) / len(subset))
    y = lambda v: bottom - v * 200
    items = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><style>text{{font-family:Arial,sans-serif;font-size:13px}}.mind{{stroke:#b23a48;fill:none;stroke-width:3}}.direct{{stroke:#276fbf;fill:none;stroke-width:3}}</style><text x="30" y="28">SENSITIVITY / DESCRIPTIVE — completion rate by repetition</text><line x1="{left}" y1="{bottom}" x2="740" y2="{bottom}" stroke="#333"/><text x="560" y="50" fill="#b23a48">MIND-Lite</text><text x="665" y="50" fill="#276fbf">Direct</text>']
    for baseline, style in ((MIND, "mind"), (DIRECT, "direct")):
        points = " ".join(f"{140+i*125},{y(rate):.1f}" for i, rate in enumerate(rates[baseline]))
        items.append(f'<polyline class="{style}" points="{points}"/>')
    for i in range(5): items.append(f'<text x="{134+i*125}" y="315">r{i+1}</text>')
    items.append('</svg>'); path.write_text("\n".join(items), encoding="utf-8")


def run_analysis(result_directory: str | Path, output_directory: str | Path) -> dict[str, Any]:
    manifest, records = load_restart1_records(result_directory)
    output = Path(output_directory); output.mkdir(parents=True, exist_ok=True)
    rows = case_rows(records)
    primary = stratum_result("Overall (PRIMARY)", rows, BOOTSTRAP_SEED)
    permutation = paired_permutation(rows)
    primary.update({"permutation_p_value_two_sided": permutation["p_value_two_sided"]})
    family = [stratum_result(name, [r for r in rows if r["family"] == name], BOOTSTRAP_SEED + i + 1) for i, name in enumerate(("calculator", "direct_answer"))]
    difficulty = [stratum_result(name, [r for r in rows if r["difficulty"] == name], BOOTSTRAP_SEED + i + 10) for i, name in enumerate(("easy", "medium", "hard"))]
    cells = [stratum_result(f"{family_name} × {difficulty_name}", [r for r in rows if r["family"] == family_name and r["difficulty"] == difficulty_name], BOOTSTRAP_SEED + i + 20) for i, (family_name, difficulty_name) in enumerate(( (f, d) for f in ("calculator", "direct_answer") for d in ("easy", "medium", "hard")))]
    for collection in (family, difficulty, cells):
        for result in collection: result["analysis_label"] = "EXPLORATORY"
    fields = ["stratum", "analysis_label", "case_count", "mind_rate", "direct_rate", "paired_difference", "mind_ci_low", "mind_ci_high", "direct_ci_low", "direct_ci_high", "difference_ci_low", "difference_ci_high"]
    _write_csv(output / "primary_results.csv", [{**primary, "analysis_label": "PRIMARY"}], fields + ["permutation_p_value_two_sided"])
    _write_csv(output / "case_level_paired_results.csv", rows, ["case_id", "family", "difficulty", "mind_successes", "direct_successes", "mind_rate", "direct_rate", "paired_difference"])
    _write_csv(output / "family_results.csv", family, fields)
    _write_csv(output / "difficulty_results.csv", difficulty, fields)
    _write_csv(output / "family_difficulty_results.csv", cells, fields)
    repetition = []
    for rep in range(1, 6):
        subset = [r for r in records if r["repetition"] == rep]
        mind_rate = sum(bool(r["success"]) for r in subset if r["baseline_id"] == MIND) / 96
        direct_rate = sum(bool(r["success"]) for r in subset if r["baseline_id"] == DIRECT) / 96
        repetition.append({"repetition": rep, "mind_rate": mind_rate, "direct_rate": direct_rate, "paired_difference": mind_rate-direct_rate, "analysis_label": "SENSITIVITY / DESCRIPTIVE"})
    _write_csv(output / "repetition_results.csv", repetition, ["repetition", "mind_rate", "direct_rate", "paired_difference", "analysis_label"])
    taxonomy = []
    for baseline in BASELINES:
        for family_name in ("calculator", "direct_answer"):
            for difficulty_name in ("easy", "medium", "hard"):
                for rep in range(1, 6):
                    subset = [r for r in records if r["baseline_id"] == baseline and r["task_family"] == family_name and r["difficulty"] == difficulty_name and r["repetition"] == rep]
                    for category, count in sorted(Counter(r["failure_category"] for r in subset).items()): taxonomy.append({"baseline_id": baseline, "family": family_name, "difficulty": difficulty_name, "repetition": rep, "failure_category": category, "count": count, "rate": count / len(subset)})
    _write_csv(output / "failure_taxonomy.csv", taxonomy, ["baseline_id", "family", "difficulty", "repetition", "failure_category", "count", "rate"])
    resource = []
    resource_groups = [("baseline", baseline, [r for r in records if r["baseline_id"] == baseline]) for baseline in BASELINES]
    resource_groups += [("baseline_family", f"{baseline}:{family_name}", [r for r in records if r["baseline_id"] == baseline and r["task_family"] == family_name]) for baseline in BASELINES for family_name in ("calculator", "direct_answer")]
    resource_groups += [("baseline_repetition", f"{baseline}:r{rep}", [r for r in records if r["baseline_id"] == baseline and r["repetition"] == rep]) for baseline in BASELINES for rep in range(1, 6)]
    for grouping_level, group_id, subset in resource_groups:
        resource.append({"grouping_level": grouping_level, "group_id": group_id, "runs": len(subset), "provider_request_attempts": sum(r["provider_request_attempts"] for r in subset), "logical_model_calls": sum(r["model_calls"] for r in subset), "requests_per_run": sum(r["provider_request_attempts"] for r in subset)/len(subset), "calls_per_run": sum(r["model_calls"] for r in subset)/len(subset), "token_latency_model_telemetry": "UNAVAILABLE"})
    _write_csv(output / "resource_summary.csv", resource, ["grouping_level", "group_id", "runs", "provider_request_attempts", "logical_model_calls", "requests_per_run", "calls_per_run", "token_latency_model_telemetry"])
    identity = {"execution_attempt_identity": manifest["execution_attempt_identity"], "provider_config_hash": manifest["provider_config_hash"], "manifest_hash": EXPECTED_MANIFEST_HASH, "suite_hash": manifest["suite_hash"], "split_hash": manifest["split_hash"], "records_analyzed": len(records), "cases_analyzed": len(rows), "historical_runs_included": False, "python_version": sys.version.split()[0]}
    (output / "experiment_identity.json").write_text(_canonical(identity) + "\n", encoding="utf-8")
    metadata = {"permutation": permutation, "bootstrap": {"draws": BOOTSTRAP_DRAWS, "seed": BOOTSTRAP_SEED, "method": "paired_nonparametric_case_cluster_bootstrap_percentile"}, "analysis_command": "python -m src.evaluation.m16_statistical_analysis", "output_hashes": {p.name: _hash_file(p) for p in sorted(output.glob("*.csv"))}}
    (output / "statistical_test_metadata.json").write_text(_canonical(metadata) + "\n", encoding="utf-8")
    figure_rows = [{**primary, "stratum": "Overall (PRIMARY)"}] + family + difficulty + cells
    _svg_forest(output / "forest_plot.svg", figure_rows); _svg_difference_distribution(output / "case_level_difference_distribution.svg", rows); _svg_repetition(output / "repetition_sensitivity.svg", list(records))
    return {"primary": primary, "permutation": permutation, "family": family, "difficulty": difficulty, "cells": cells, "repetition": repetition, "resource": resource, "rows": rows}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    result = run_analysis(root / "evaluation/results/m16_deepseek_v4_flash_restart1", root / "evaluation/analysis/m16_deepseek_restart1")
    print(_canonical({"primary": result["primary"], "permutation": result["permutation"]}))
