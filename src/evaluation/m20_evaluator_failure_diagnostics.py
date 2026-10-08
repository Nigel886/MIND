"""Opt-in, evaluator-private prospective diagnostics; never provider-facing."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping

from src.evaluation.m20_harness import M20Case, M20IntegrityError, M20Outcome, canonical_hash, canonical_json


M20_EVALUATOR_FAILURE_DIAGNOSTIC_SCHEMA = "m20_evaluator_failure_diagnostic_v1"
_CLASSIFICATIONS = frozenset({"success", "answer_payload_failure", "prerequisite_failure", "combined_failure", "unknown_other"})
_VALIDATION = frozenset({"complete", "malformed", "conflicting", "missing"})


@dataclass(frozen=True)
class M20EvaluatorFailureDiagnostic:
    execution_id: str
    evaluator_id: str
    schema: str
    answer_matches_private_target: bool | None
    prerequisite_status: str | None
    witness_status: str | None
    classification: str
    validation_status: str
    provenance: Mapping[str, str]

    def __post_init__(self) -> None:
        if (not self.execution_id or not self.evaluator_id or self.schema != M20_EVALUATOR_FAILURE_DIAGNOSTIC_SCHEMA or
                self.classification not in _CLASSIFICATIONS or self.validation_status not in _VALIDATION or
                self.prerequisite_status not in {"pass", "fail", None} or
                self.witness_status not in {"present", "missing", None} or
                not self.provenance or any(not isinstance(k, str) or not isinstance(v, str) or not k or not v
                                             for k, v in self.provenance.items())):
            raise M20IntegrityError("evaluator diagnostic contract is invalid")
        if self.validation_status == "complete":
            if self.witness_status != "present" or not isinstance(self.answer_matches_private_target, bool) or self.prerequisite_status not in {"pass", "fail"}:
                raise M20IntegrityError("complete evaluator diagnostic lacks checks")
            expected = ("success" if self.answer_matches_private_target and self.prerequisite_status == "pass" else
                        "answer_payload_failure" if not self.answer_matches_private_target and self.prerequisite_status == "pass" else
                        "prerequisite_failure" if self.answer_matches_private_target else "combined_failure")
            if self.classification != expected:
                raise M20IntegrityError("evaluator diagnostic classification conflicts with checks")
        elif self.classification != "unknown_other":
            raise M20IntegrityError("incomplete evaluator diagnostic must be unknown")

    def canonical(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def digest(self) -> str:
        return canonical_hash(self.canonical())


def diagnose_after_evaluator_handoff(execution_id: str, case: M20Case, state: Mapping[str, Any], answer: Any,
                                     evaluator_id: str, outcome: M20Outcome) -> M20EvaluatorFailureDiagnostic:
    """Derive private metadata after the authoritative evaluator outcome only."""
    if not execution_id or not isinstance(state, Mapping):
        raise M20IntegrityError("diagnostic handoff inputs are invalid")
    if answer is None:
        return M20EvaluatorFailureDiagnostic(execution_id, evaluator_id, M20_EVALUATOR_FAILURE_DIAGNOSTIC_SCHEMA,
            None, None, "present", "unknown_other", "missing", {"authority": "evaluator_private", "version": M20_EVALUATOR_FAILURE_DIAGNOSTIC_SCHEMA})
    witness = case.private.reference_witness
    if not witness:
        return M20EvaluatorFailureDiagnostic(execution_id, evaluator_id, M20_EVALUATOR_FAILURE_DIAGNOSTIC_SCHEMA,
            None, None, "missing", "unknown_other", "missing", {"authority": "evaluator_private", "version": M20_EVALUATOR_FAILURE_DIAGNOSTIC_SCHEMA})
    target_match = answer == case.private.target
    prerequisites = (state.get("progress", 0) >= state.get("required_progress", 0) and
                     (not state.get("requires_observation") or bool(state.get("observed"))) and
                     (not state.get("requires_recovery") or bool(state.get("recovered"))))
    expected_outcome = M20Outcome.SUCCESS if target_match and prerequisites else M20Outcome.FAILURE_OR_INCORRECT
    if outcome is not expected_outcome:
        return M20EvaluatorFailureDiagnostic(execution_id, evaluator_id, M20_EVALUATOR_FAILURE_DIAGNOSTIC_SCHEMA,
            None, None, "present", "unknown_other", "conflicting", {"authority": "evaluator_private", "version": M20_EVALUATOR_FAILURE_DIAGNOSTIC_SCHEMA})
    return M20EvaluatorFailureDiagnostic(execution_id, evaluator_id, M20_EVALUATOR_FAILURE_DIAGNOSTIC_SCHEMA,
        target_match, "pass" if prerequisites else "fail", "present", "success" if expected_outcome is M20Outcome.SUCCESS else
        "answer_payload_failure" if not target_match and prerequisites else "prerequisite_failure" if target_match else "combined_failure",
        "complete", {"authority": "evaluator_private", "version": M20_EVALUATOR_FAILURE_DIAGNOSTIC_SCHEMA})


class M20EvaluatorDiagnosticStore:
    """Dedicated private sidecar store. Historical canonical evidence is never read or migrated."""
    def __init__(self, root: Path) -> None:
        self.root = root; root.mkdir(parents=True, exist_ok=True)

    def persist(self, diagnostic: M20EvaluatorFailureDiagnostic) -> None:
        path = self.root / (diagnostic.execution_id + ".json")
        value = {**diagnostic.canonical(), "digest": diagnostic.digest}
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing == value: return
            raise M20IntegrityError("conflicting duplicate evaluator diagnostic")
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=self.root, suffix=".tmp") as handle:
            handle.write(canonical_json(value) + "\n"); temporary = Path(handle.name)
        temporary.replace(path)

    def load(self, execution_id: str) -> M20EvaluatorFailureDiagnostic:
        value = json.loads((self.root / (execution_id + ".json")).read_text(encoding="utf-8"))
        digest = value.pop("digest", None)
        if digest != canonical_hash(value): raise M20IntegrityError("evaluator diagnostic digest mismatch")
        return M20EvaluatorFailureDiagnostic(**value)
