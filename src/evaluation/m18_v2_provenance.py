"""Deterministic, provider-free future-result provenance for M18 v2.

This module deliberately does not create a result directory or execute a case.
It defines only the logical identity and fail-closed admission contract that a
later, separately frozen v2 result store must use.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from src.evaluation.m18_direct_tool_calling import M18_DIRECT_ID
from src.evaluation.m18_mind_policy_condition import M18_POLICY_CONDITION_ID
from src.evaluation.m18_plan_and_execute import M18_PLAN_EXECUTE_ID
from src.evaluation.m18_react import M18_REACT_ID
from src.evaluation.m18_task_generation import canonical_hash
from src.evaluation.m18_v2_semantics import (
    M18_V2_BUDGET_ID,
    M18_V2_ENVIRONMENT_ID,
    M18_V2_EVALUATOR_ID,
    M18_V2_SUITE_VERSION,
)
from src.evaluation.m18_v2_provider_diagnostics import M18V2ProviderDiagnostic


M18_V2_RUNTIME_ID = "m18_shared_execution_runtime_v2"
M18_V2_RUN_ID_SCHEMA = "m18_v2_logical_run_id_v1"
M18_V2_RESULT_SCHEMA_VERSION = "m18_v2_result_record_v1"
M18_V2_REPETITIONS = 5
M18_V2_COMPARATOR_CONDITIONS = {
    "mind_lite_v11": M18_POLICY_CONDITION_ID,
    "direct_tool_calling": M18_DIRECT_ID,
    "react": M18_REACT_ID,
    "plan_and_execute": M18_PLAN_EXECUTE_ID,
}


def _nonempty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{name} must be a trimmed non-empty string")


def _sha256(name: str, value: str) -> None:
    _nonempty(name, value)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex string")


def derive_m18_v2_run_id(
    suite_identity: str,
    case_id: str,
    comparator_condition_id: str,
    repetition: int,
) -> str:
    """Hash a typed canonical object, never concatenated field text."""
    _nonempty("suite_identity", suite_identity)
    _nonempty("case_id", case_id)
    _nonempty("comparator_condition_id", comparator_condition_id)
    if not isinstance(repetition, int) or isinstance(repetition, bool) or repetition < 1:
        raise ValueError("repetition must be a positive integer")
    return canonical_hash({
        "run_id_schema": M18_V2_RUN_ID_SCHEMA,
        "suite_identity": suite_identity,
        "case_id": case_id,
        "comparator_condition_id": comparator_condition_id,
        "repetition": repetition,
    })


def comparator_condition_for_system(system_condition: str) -> str:
    try:
        return M18_V2_COMPARATOR_CONDITIONS[system_condition]
    except KeyError as error:
        raise ValueError("unknown M18 v2 comparator system") from error


@dataclass(frozen=True)
class M18V2RunIdentity:
    """The smallest collision-safe scientific identity of a future v2 run."""

    suite_identity: str
    case_id: str
    comparator_condition_id: str
    repetition: int

    def __post_init__(self) -> None:
        if self.suite_identity != M18_V2_SUITE_VERSION:
            raise ValueError("M18 v2 run identity requires the v2 suite identity")
        _nonempty("case_id", self.case_id)
        if self.comparator_condition_id not in set(M18_V2_COMPARATOR_CONDITIONS.values()):
            raise ValueError("unknown M18 v2 comparator condition")
        if not isinstance(self.repetition, int) or isinstance(self.repetition, bool) or not 1 <= self.repetition <= M18_V2_REPETITIONS:
            raise ValueError("M18 v2 repetition must be 1..5")

    @property
    def run_id(self) -> str:
        return derive_m18_v2_run_id(
            self.suite_identity,
            self.case_id,
            self.comparator_condition_id,
            self.repetition,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_identity": self.suite_identity,
            "case_id": self.case_id,
            "comparator_condition_id": self.comparator_condition_id,
            "repetition": self.repetition,
            "run_id": self.run_id,
        }


@dataclass(frozen=True)
class M18V2RunProvenance:
    """Complete typed provenance required to admit one future v2 record."""

    identity: M18V2RunIdentity
    environment_id: str
    evaluator_id: str
    budget_id: str
    runtime_id: str
    provider_config_hash: str
    execution_baseline: str
    result_schema_version: str = M18_V2_RESULT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.identity, M18V2RunIdentity):
            raise TypeError("identity must be an M18V2RunIdentity")
        if (self.environment_id, self.evaluator_id, self.budget_id, self.runtime_id) != (
            M18_V2_ENVIRONMENT_ID,
            M18_V2_EVALUATOR_ID,
            M18_V2_BUDGET_ID,
            M18_V2_RUNTIME_ID,
        ):
            raise ValueError("M18 v2 semantic provenance identity mismatch")
        _sha256("provider_config_hash", self.provider_config_hash)
        _nonempty("execution_baseline", self.execution_baseline)
        if self.result_schema_version != M18_V2_RESULT_SCHEMA_VERSION:
            raise ValueError("unknown M18 v2 result schema version")

    @property
    def run_id(self) -> str:
        return self.identity.run_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "repetition": self.identity.repetition,
            "case_id": self.identity.case_id,
            "suite_identity": self.identity.suite_identity,
            "comparator_condition_id": self.identity.comparator_condition_id,
            "environment_id": self.environment_id,
            "evaluator_id": self.evaluator_id,
            "budget_id": self.budget_id,
            "runtime_id": self.runtime_id,
            "provider_config_hash": self.provider_config_hash,
            "execution_baseline": self.execution_baseline,
            "result_schema_version": self.result_schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "M18V2RunProvenance":
        expected = {
            "run_id", "repetition", "case_id", "suite_identity",
            "comparator_condition_id", "environment_id", "evaluator_id",
            "budget_id", "runtime_id", "provider_config_hash",
            "execution_baseline", "result_schema_version",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ValueError("M18 v2 provenance schema mismatch")
        identity = M18V2RunIdentity(
            value["suite_identity"], value["case_id"],
            value["comparator_condition_id"], value["repetition"],
        )
        result = cls(
            identity, value["environment_id"], value["evaluator_id"],
            value["budget_id"], value["runtime_id"],
            value["provider_config_hash"], value["execution_baseline"],
            value["result_schema_version"],
        )
        if value["run_id"] != result.run_id:
            raise ValueError("M18 v2 run id does not match canonical provenance")
        return result


@dataclass(frozen=True)
class M18V2ResultRecord:
    """Future record contract; it stores no hidden reasoning or raw prompts."""

    provenance: M18V2RunProvenance
    evaluator_outcome: str | None
    failure_taxonomy: str | None
    provider_accounting: Mapping[str, int | None]
    token_latency_telemetry: Mapping[str, int | float | None] | None = None
    provider_diagnostic: M18V2ProviderDiagnostic | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, M18V2RunProvenance):
            raise TypeError("provenance must be an M18V2RunProvenance")
        for name, value in (("evaluator_outcome", self.evaluator_outcome), ("failure_taxonomy", self.failure_taxonomy)):
            if value is not None:
                _nonempty(name, value)
        if not isinstance(self.provider_accounting, Mapping):
            raise TypeError("provider_accounting must be a mapping")
        required = {"logical_provider_calls", "transport_attempts"}
        if set(self.provider_accounting) != required:
            raise ValueError("provider accounting schema mismatch")
        for value in self.provider_accounting.values():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError("provider accounting must contain non-negative integers")
        if self.token_latency_telemetry is not None and not isinstance(self.token_latency_telemetry, Mapping):
            raise TypeError("token_latency_telemetry must be a mapping or null")
        if self.provider_diagnostic is not None and not isinstance(self.provider_diagnostic, M18V2ProviderDiagnostic):
            raise TypeError("provider_diagnostic must be an M18V2ProviderDiagnostic or null")
        if self.provider_diagnostic is not None and self.failure_taxonomy != "provider_failure":
            raise ValueError("provider diagnostics require provider_failure taxonomy")

    @property
    def run_id(self) -> str:
        return self.provenance.run_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "repetition": self.provenance.identity.repetition,
            "provenance": self.provenance.to_dict(),
            "evaluator_outcome": self.evaluator_outcome,
            "failure_taxonomy": self.failure_taxonomy,
            "provider_accounting": dict(self.provider_accounting),
            "token_latency_telemetry": (
                dict(self.token_latency_telemetry)
                if self.token_latency_telemetry is not None else None
            ),
            "provider_diagnostic": (
                self.provider_diagnostic.to_dict()
                if self.provider_diagnostic is not None else None
            ),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "M18V2ResultRecord":
        expected = {
            "run_id", "repetition", "provenance", "evaluator_outcome", "failure_taxonomy",
            "provider_accounting", "token_latency_telemetry", "provider_diagnostic",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ValueError("M18 v2 result record schema mismatch")
        result = cls(
            M18V2RunProvenance.from_dict(value["provenance"]),
            value["evaluator_outcome"], value["failure_taxonomy"],
            dict(value["provider_accounting"]),
            dict(value["token_latency_telemetry"])
            if value["token_latency_telemetry"] is not None else None,
            M18V2ProviderDiagnostic.from_dict(value["provider_diagnostic"])
            if value["provider_diagnostic"] is not None else None,
        )
        if value["run_id"] != result.run_id or value["repetition"] != result.provenance.identity.repetition:
            raise ValueError("M18 v2 record identity projection mismatch")
        return result


def _integrity_stop(reason: str, detail: str, run_id: str | None) -> RuntimeError:
    """Map a future v2 provenance breach to the existing typed M18 stop."""
    from src.evaluation.m18_pilot_execution import (
        M18OperationalStopCategory,
        M18OperationalStopCondition,
        M18OperationalStopEvent,
    )
    return M18OperationalStopCondition(M18OperationalStopEvent(
        M18OperationalStopCategory.PROVENANCE_INTEGRITY_FAILURE,
        "v2_result_admission", reason, detail, run_id,
    ))


class M18V2ResultAdmission:
    """In-memory fail-closed admission/resume projection; no filesystem access."""

    def __init__(self, expected: Iterable[M18V2RunProvenance]) -> None:
        self._expected: dict[str, M18V2RunProvenance] = {}
        for item in expected:
            if not isinstance(item, M18V2RunProvenance):
                raise TypeError("expected runs must be M18V2RunProvenance values")
            if item.run_id in self._expected:
                raise ValueError("duplicate expected M18 v2 run id")
            self._expected[item.run_id] = item
        if len(self._expected) == 0:
            raise ValueError("at least one expected M18 v2 run is required")
        self._records: dict[str, M18V2ResultRecord] = {}

    def admit(self, record: M18V2ResultRecord) -> None:
        try:
            if not isinstance(record, M18V2ResultRecord):
                raise ValueError("invalid record type")
            parsed = M18V2ResultRecord.from_dict(record.to_dict())
            expected = self._expected.get(parsed.run_id)
            if expected is None or parsed.provenance != expected:
                raise ValueError("record provenance is not an expected v2 run")
            if parsed.run_id in self._records:
                raise ValueError("duplicate completed v2 run id")
        except (TypeError, ValueError) as error:
            run_id = record.run_id if isinstance(record, M18V2ResultRecord) else None
            raise _integrity_stop("v2_run_provenance_invalid", type(error).__name__, run_id) from error
        self._records[parsed.run_id] = parsed

    def completed_ids(self) -> frozenset[str]:
        return frozenset(self._records)

    def missing(self) -> tuple[M18V2RunProvenance, ...]:
        return tuple(item for run_id, item in self._expected.items() if run_id not in self._records)


def project_m18_v2_run_provenances(
    case_ids: Iterable[str],
    comparator_conditions: Iterable[str],
    provider_config_hash: str,
    execution_baseline: str,
    repetitions: Iterable[int] = range(1, M18_V2_REPETITIONS + 1),
) -> tuple[M18V2RunProvenance, ...]:
    """Provider-free projection used for identity validation, never execution."""
    output = []
    for case_id in case_ids:
        for comparator_condition_id in comparator_conditions:
            for repetition in repetitions:
                output.append(M18V2RunProvenance(
                    M18V2RunIdentity(M18_V2_SUITE_VERSION, case_id, comparator_condition_id, repetition),
                    M18_V2_ENVIRONMENT_ID, M18_V2_EVALUATOR_ID, M18_V2_BUDGET_ID,
                    M18_V2_RUNTIME_ID, provider_config_hash, execution_baseline,
                ))
    identities = [item.run_id for item in output]
    if len(identities) != len(set(identities)):
        raise ValueError("projected M18 v2 run identity collision")
    return tuple(output)
