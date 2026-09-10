"""Tests for the read-only M16 Diagnostic v1 derived-analysis helper."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m16_mind_failure_diagnostic_v1 import load_frozen_m16_mind_failure_diagnostic_manifest
from src.evaluation.m16_mind_failure_diagnostic_v1_analysis import analyze, write_summaries


class M16MindFailureDiagnosticV1AnalysisTests(unittest.TestCase):
    def _make_results(self, directory: Path) -> None:
        manifest = load_frozen_m16_mind_failure_diagnostic_manifest()
        directory.mkdir()
        (directory / "diagnostic_manifest_v1.json").write_text(json.dumps(manifest.to_dict()), encoding="utf-8")
        attempts, events = [], []
        stages = (
            ("provider_request_started", None),
            ("provider_response_received", None),
            ("provider_decode_failure", "malformed_structured_output"),
            ("admission_failed", "admission_failure"),
        )
        for number in range(96):
            family = "calculator" if number % 2 else "direct_answer"
            difficulty = ("easy", "medium", "hard")[number % 3]
            case_id = f"m16.cohort.{family}.{difficulty}.{number:03d}"
            run_id = f"m16diag:v1:{manifest.manifest_hash}:{number}"
            attempts.append({"manifest_hash": manifest.manifest_hash, "run_id": run_id, "status": "terminal_valid", "public_case_id": case_id, "observed_outcome": "agent_fail"})
            for ordinal, (stage_name, reason) in enumerate(stages, 1):
                events.append({"manifest_hash": manifest.manifest_hash, "run_id": run_id, "event": {"stage_ordinal": ordinal, "stage_name": stage_name, "normalized_reason": reason, "action_type": None, "terminal_category": None}})
        (directory / "diagnostic_attempts_v1.jsonl").write_text("\n".join(json.dumps(item) for item in attempts) + "\n", encoding="utf-8")
        (directory / "diagnostic_stage_events_v1.jsonl").write_text("\n".join(json.dumps(item) for item in events) + "\n", encoding="utf-8")

    def test_analysis_validates_and_writes_deterministic_derived_summaries(self) -> None:
        with TemporaryDirectory() as temporary:
            directory = Path(temporary) / "results"
            output = Path(temporary) / "analysis"
            self._make_results(directory)
            report = analyze(directory)
            integrity = write_summaries(directory, output)
            self.assertEqual(96, integrity["attempts"])
            self.assertEqual(384, integrity["telemetry_events"])
            self.assertEqual(96, report["stage_counts"]["provider_decode_failure"])
            self.assertEqual(96, report["reason_counts"]["malformed_structured_output"])
            for filename in ("run_integrity.json", "event_sequence_signatures.csv", "stage_counts.csv", "reason_counts.csv", "family_breakdown.csv", "difficulty_breakdown.csv", "terminal_event_audit.csv"):
                self.assertTrue((output / filename).is_file())


if __name__ == "__main__":
    unittest.main()
