"""Read-only, case-clustered analysis of repaired M16 post-hoc records."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from src.evaluation.m16_deepseek_repaired_posthoc_v1 import (
    DIRECT_REQUEST_HASH, MIND_REQUEST_HASH, MIND_SCHEMA_HASH,
    PROVIDER_CONFIG_HASH, SPLIT_HASH, SUITE_HASH,
)
from src.evaluation.m16_statistical_analysis import _bootstrap, _canonical, _hash_file, _svg_difference_distribution, _svg_forest, _svg_repetition, _write_csv, paired_permutation, stratum_result

MIND = "mind_lite_v1"
DIRECT = "direct_tool_calling"
BASELINES = (MIND, DIRECT)
EXPECTED_MANIFEST_HASH = "7fb0013b2c93f23b6288604e374c9374477c427a14babbb7556454641f4304bb"
PERMUTATION_SEED = 970000001
BOOTSTRAP_SEED = 970000002
PERMUTATION_DRAWS = 100_000
BOOTSTRAP_DRAWS = 10_000


def load_repaired_records(directory: str | Path) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    root = Path(directory)
    manifest = json.loads((root / "repaired_posthoc_manifest_v1.json").read_text(encoding="utf-8"))
    records = tuple(json.loads(line) for line in (root / "repaired_posthoc_attempts_v1.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())
    validate_dataset(manifest, records)
    return manifest, records


def validate_dataset(manifest: dict[str, Any], records: Iterable[dict[str, Any]]) -> None:
    records = tuple(records)
    if hashlib.sha256(_canonical(manifest).encode()).hexdigest() != EXPECTED_MANIFEST_HASH:
        raise ValueError("unexpected repaired manifest")
    identities = (manifest.get("provider_config_hash"), manifest.get("mind_request_template_hash"), manifest.get("canonical_schema_hash"), manifest.get("direct_request_hash"), manifest.get("suite_hash"), manifest.get("split_hash"))
    if identities != (PROVIDER_CONFIG_HASH, MIND_REQUEST_HASH, MIND_SCHEMA_HASH, DIRECT_REQUEST_HASH, SUITE_HASH, SPLIT_HASH):
        raise ValueError("repaired identity drift")
    if len(records) != 960 or len({r.get("run_id") for r in records}) != 960 or len({r.get("attempt_id") for r in records}) != 960:
        raise ValueError("expected 960 unique repaired terminal records")
    if {r.get("manifest_hash") for r in records} != {EXPECTED_MANIFEST_HASH}:
        raise ValueError("foreign repaired records")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        if r.get("baseline_id") not in BASELINES or r.get("repetition") not in range(1, 6):
            raise ValueError("invalid repaired baseline or repetition")
        grouped[r["evaluation_id"]].append(r)
    if len(grouped) != 96:
        raise ValueError("expected 96 paired clusters")
    for values in grouped.values():
        if len(values) != 10 or any(sorted(r["repetition"] for r in values if r["baseline_id"] == b) != [1, 2, 3, 4, 5] for b in BASELINES):
            raise ValueError("incomplete baseline vector")


def case_rows(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records: grouped[r["evaluation_id"]].append(r)
    rows = []
    for case_id, values in sorted(grouped.items()):
        ref = values[0]; vectors = {b: sorted((r for r in values if r["baseline_id"] == b), key=lambda r: r["repetition"]) for b in BASELINES}
        ms, ds = sum(bool(r["success"]) for r in vectors[MIND]), sum(bool(r["success"]) for r in vectors[DIRECT])
        rows.append({"case_id": case_id, "family": ref["task_family"], "difficulty": ref["difficulty"], "mind_successes": ms, "direct_successes": ds, "mind_rate": ms / 5, "direct_rate": ds / 5, "paired_difference": (ms - ds) / 5})
    return rows


def _results(label: str, rows: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    value = stratum_result(label, rows, seed)
    value["analysis_label"] = "PRIMARY" if label == "Overall" else "EXPLORATORY"
    return value


def _taxonomy(records: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    out = []
    for baseline in BASELINES:
        for family in ("calculator", "direct_answer"):
            for difficulty in ("easy", "medium", "hard"):
                for repetition in range(1, 6):
                    subset = [r for r in records if (r["baseline_id"], r["task_family"], r["difficulty"], r["repetition"]) == (baseline, family, difficulty, repetition)]
                    for category, count in sorted(Counter(r["failure_category"] for r in subset).items()):
                        out.append({"baseline_id": baseline, "family": family, "difficulty": difficulty, "repetition": repetition, "failure_category": category, "count": count, "rate": count / len(subset)})
    return out


def _svg_direct_errors(path: Path, errors: list[dict[str, Any]]) -> None:
    counts = Counter(item["case_id"] for item in errors); width, height, base = 920, 380, 315; maximum = max(counts.values(), default=1)
    items = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><style>text{{font-family:Arial,sans-serif;font-size:11px}}.bar{{fill:#b23a48}}</style><text x="25" y="25">Direct wrong_answer concentration by formal case (exploratory)</text><line x1="45" y1="{base}" x2="895" y2="{base}" stroke="#333"/>']
    for index, (case_id, count) in enumerate(sorted(counts.items())):
        x, h = 60 + index * 74, 220 * count / maximum
        items.append(f'<rect class="bar" x="{x}" y="{base-h:.1f}" width="42" height="{h:.1f}"/><text x="{x+13}" y="{base-h-5:.1f}">{count}</text><text x="{x}" y="338">{case_id.rsplit(".",1)[-1]}</text>')
    items.append('</svg>'); path.write_text("\n".join(items), encoding="utf-8")


def run_analysis(result_directory: str | Path, output_directory: str | Path) -> dict[str, Any]:
    manifest, records = load_repaired_records(result_directory)
    output = Path(output_directory); output.mkdir(parents=True, exist_ok=True)
    rows = case_rows(records); primary = _results("Overall", rows, BOOTSTRAP_SEED)
    permutation = paired_permutation(rows, PERMUTATION_DRAWS, PERMUTATION_SEED)
    primary["permutation_p_value_two_sided"] = permutation["p_value_two_sided"]
    families = [_results(f, [r for r in rows if r["family"] == f], BOOTSTRAP_SEED + i + 1) for i, f in enumerate(("calculator", "direct_answer"))]
    difficulties = [_results(x, [r for r in rows if r["difficulty"] == x], BOOTSTRAP_SEED + i + 10) for i, x in enumerate(("easy", "medium", "hard"))]
    cells = [_results(f"{f} × {d}", [r for r in rows if r["family"] == f and r["difficulty"] == d], BOOTSTRAP_SEED + i + 20) for i, (f, d) in enumerate(( (f, d) for f in ("calculator", "direct_answer") for d in ("easy", "medium", "hard")))]
    fields = ["stratum", "analysis_label", "case_count", "mind_rate", "direct_rate", "paired_difference", "mind_ci_low", "mind_ci_high", "direct_ci_low", "direct_ci_high", "difference_ci_low", "difference_ci_high"]
    _write_csv(output / "primary_results.csv", [primary], fields + ["permutation_p_value_two_sided"])
    _write_csv(output / "case_level_paired_results.csv", rows, ["case_id", "family", "difficulty", "mind_successes", "direct_successes", "mind_rate", "direct_rate", "paired_difference"])
    _write_csv(output / "family_results.csv", families, fields); _write_csv(output / "difficulty_results.csv", difficulties, fields); _write_csv(output / "family_difficulty_results.csv", cells, fields)
    repetitions = []
    for rep in range(1, 6):
        subset = [r for r in records if r["repetition"] == rep]; mr = sum(r["success"] for r in subset if r["baseline_id"] == MIND) / 96; dr = sum(r["success"] for r in subset if r["baseline_id"] == DIRECT) / 96
        repetitions.append({"repetition": rep, "mind_rate": mr, "direct_rate": dr, "paired_difference": mr - dr, "analysis_label": "SENSITIVITY / DESCRIPTIVE ONLY"})
    _write_csv(output / "repetition_results.csv", repetitions, ["repetition", "mind_rate", "direct_rate", "paired_difference", "analysis_label"])
    _write_csv(output / "failure_taxonomy.csv", _taxonomy(records), ["baseline_id", "family", "difficulty", "repetition", "failure_category", "count", "rate"])
    errors = []
    for r in records:
        if r["baseline_id"] == DIRECT and r["failure_category"] == "wrong_answer": errors.append({"case_id": r["evaluation_id"], "family": r["task_family"], "difficulty": r["difficulty"], "repetition": r["repetition"], "failure_category": r["failure_category"]})
    _write_csv(output / "direct_error_concentration.csv", errors, ["case_id", "family", "difficulty", "repetition", "failure_category"])
    _svg_direct_errors(output / "direct_error_concentration.svg", errors)
    resource = []
    groups = [("baseline", b, [r for r in records if r["baseline_id"] == b]) for b in BASELINES] + [("baseline_family", f"{b}:{f}", [r for r in records if r["baseline_id"] == b and r["task_family"] == f]) for b in BASELINES for f in ("calculator", "direct_answer")] + [("baseline_repetition", f"{b}:r{x}", [r for r in records if r["baseline_id"] == b and r["repetition"] == x]) for b in BASELINES for x in range(1, 6)]
    for level, name, subset in groups:
        req, calls = sum(r["provider_request_attempts"] for r in subset), sum(r["model_calls"] for r in subset)
        resource.append({"grouping_level": level, "group_id": name, "runs": len(subset), "provider_request_attempts": req, "logical_model_calls": calls, "requests_per_run": req / len(subset), "calls_per_run": calls / len(subset), "token_latency_cache_model_telemetry": "UNAVAILABLE"})
    _write_csv(output / "resource_summary.csv", resource, ["grouping_level", "group_id", "runs", "provider_request_attempts", "logical_model_calls", "requests_per_run", "calls_per_run", "token_latency_cache_model_telemetry"])
    historical = [{"context": "DESCRIPTIVE CROSS-EXPERIMENT CONTEXT ONLY", "experiment": "original_formal", "mind_rate": 0.0, "direct_rate": 0.892}, {"context": "DESCRIPTIVE CROSS-EXPERIMENT CONTEXT ONLY", "experiment": "repaired_posthoc", "mind_rate": primary["mind_rate"], "direct_rate": primary["direct_rate"]}]
    _write_csv(output / "historical_context.csv", historical, ["context", "experiment", "mind_rate", "direct_rate"])
    identity = {"manifest_hash": EXPECTED_MANIFEST_HASH, "provider_config_hash": PROVIDER_CONFIG_HASH, "mind_request_hash": MIND_REQUEST_HASH, "schema_hash": MIND_SCHEMA_HASH, "direct_request_hash": DIRECT_REQUEST_HASH, "suite_hash": SUITE_HASH, "split_hash": SPLIT_HASH, "records_analyzed": len(records), "case_clusters": len(rows), "historical_runs_included": False, "diagnostic_v1_runs_included": False, "python_version": sys.version.split()[0]}
    (output / "experiment_identity.json").write_text(_canonical(identity) + "\n", encoding="utf-8")
    metadata = {"permutation": permutation, "bootstrap": {"draws": BOOTSTRAP_DRAWS, "seed": BOOTSTRAP_SEED, "method": "paired_nonparametric_case_cluster_bootstrap_percentile"}, "analysis_command": "python -m src.evaluation.m16_repaired_posthoc_statistical_analysis", "output_hashes": {p.name: _hash_file(p) for p in sorted(output.glob("*.csv"))}}
    (output / "statistical_test_metadata.json").write_text(_canonical(metadata) + "\n", encoding="utf-8")
    _svg_forest(output / "forest_plot.svg", [primary] + families + difficulties + cells); _svg_difference_distribution(output / "case_level_difference_distribution.svg", rows); _svg_repetition(output / "repetition_sensitivity.svg", list(records))
    return {"primary": primary, "permutation": permutation, "family": families, "difficulty": difficulties, "cells": cells, "repetition": repetitions, "errors": errors, "resource": resource, "rows": rows}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    print(_canonical(run_analysis(root / "evaluation/results/m16_deepseek_repaired_posthoc_v1", root / "evaluation/analysis/m16_deepseek_repaired_posthoc_v1")["primary"]))
