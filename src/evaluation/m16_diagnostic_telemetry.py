"""Opt-in, non-behavioral telemetry contracts for M16 diagnostic v1."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping


DIAGNOSTIC_SCHEMA_VERSION = "m16-mind-diagnostic-stage-v1"
DIAGNOSTIC_REASON_TAXONOMY_VERSION = "m16-mind-diagnostic-reason-v1"
DIAGNOSTIC_RESULT_DIRECTORY = Path("evaluation/results/m16_mind_failure_diagnostic_v1")
_HISTORICAL = frozenset(Path(item) for item in (
    "evaluation/results/m16", "evaluation/results/m16_flash_lite",
    "evaluation/results/m16_deepseek_v4_flash", "evaluation/results/m16_deepseek_v4_flash_restart1",
))
_ALLOWED_EVENT_METADATA_KEYS = frozenset({"attempt_number", "diagnostic_run_id", "resume_attempt"})


def _safe_event_metadata(value: object) -> Mapping[str, str | int | bool | None]:
    """Accept only a compact, non-sensitive event metadata allow-list.

    Raw provider text, prompts, credentials, private truth, and runtime state
    cannot be represented by this telemetry contract.
    """
    if not isinstance(value, dict) or set(value) - _ALLOWED_EVENT_METADATA_KEYS:
        raise ValueError("diagnostic metadata is not permitted")
    if any(not isinstance(item, (str, int, bool, type(None))) for item in value.values()):
        raise TypeError("diagnostic metadata must be scalar")
    return MappingProxyType(dict(value))


class M16DiagnosticStage(str, Enum):
    PROVIDER_REQUEST_STARTED = "provider_request_started"; PROVIDER_RESPONSE_RECEIVED = "provider_response_received"
    PROVIDER_DECODE_SUCCESS = "provider_decode_success"; PROVIDER_DECODE_FAILURE = "provider_decode_failure"
    PROPOSAL_CONSTRUCTED = "proposal_constructed"; PROPOSAL_VALIDATION_SUCCESS = "proposal_validation_success"
    PROPOSAL_VALIDATION_FAILURE = "proposal_validation_failure"; VALIDATED_REQUIREMENT_CREATED = "validated_requirement_created"
    META_INFERENCE_STARTED = "meta_inference_started"; META_INFERENCE_SELECTED = "meta_inference_selected"
    META_INFERENCE_NOT_SELECTED = "meta_inference_not_selected"; INTEGRATION_SELECTED = "integration_selected"
    ADMISSION_FAILED = "admission_failed"; PRIVATE_TASK_PROJECTED = "private_task_projected"
    PRIVATE_SESSION_CREATED = "private_session_created"; POLICY_INVOKED = "policy_invoked"
    POLICY_ACTION_CREATED = "policy_action_created"; PROJECTED_ANSWER_ACTION = "projected_answer_action"
    PROJECTED_TOOL_ACTION = "projected_tool_action"; PRIVATE_SESSION_TERMINATED = "private_session_terminated"
    EVALUATOR_INVOKED = "evaluator_invoked"; TOOL_INVOKED = "tool_invoked"
    TERMINAL_ADAPTER_ACTION = "terminal_adapter_action"; TERMINAL_REASON = "terminal_reason"


class M16DiagnosticReason(str, Enum):
    PROVIDER_TRANSPORT_FAILURE = "provider_transport_failure"; PROVIDER_DECODE_FAILURE = "provider_decode_failure"
    MALFORMED_STRUCTURED_OUTPUT = "malformed_structured_output"; PROPOSAL_VALIDATION_FAILURE = "proposal_validation_failure"
    META_INFERENCE_NON_SELECTION = "meta_inference_non_selection"; ADMISSION_FAILURE = "admission_failure"
    PRIVATE_SESSION_FAILURE = "private_session_failure"; POLICY_FAILURE = "policy_failure"
    UNSUPPORTED_PROJECTED_ACTION = "unsupported_projected_action"; COMPLETION_CONTRACT_FAILURE = "completion_contract_failure"
    EVALUATOR_FAILURE = "evaluator_failure"; TOOL_FAILURE = "tool_failure"; UNKNOWN = "unknown"


@dataclass(frozen=True)
class M16DiagnosticEvent:
    stage_name: M16DiagnosticStage
    stage_ordinal: int
    success: bool | None = None
    normalized_reason: M16DiagnosticReason | None = None
    selected_capability: str | None = None
    selected_strategy: str | None = None
    action_type: str | None = None
    tool_name: str | None = None
    provider_request_count: int | None = None
    model_call_count: int | None = None
    session_phase: str | None = None
    terminal_category: str | None = None
    schema_version: str = DIAGNOSTIC_SCHEMA_VERSION
    metadata: Mapping[str, str | int | bool | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.stage_name, M16DiagnosticStage) or not isinstance(self.stage_ordinal, int) or self.stage_ordinal < 1:
            raise ValueError("invalid diagnostic event identity")
        if self.normalized_reason is not None and not isinstance(self.normalized_reason, M16DiagnosticReason):
            raise TypeError("normalized_reason must be a diagnostic reason")
        if self.schema_version != DIAGNOSTIC_SCHEMA_VERSION:
            raise ValueError("unexpected diagnostic schema version")
        object.__setattr__(self, "metadata", _safe_event_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "stage_name": self.stage_name.value, "stage_ordinal": self.stage_ordinal, "success": self.success, "normalized_reason": self.normalized_reason.value if self.normalized_reason else None, "selected_capability": self.selected_capability, "selected_strategy": self.selected_strategy, "action_type": self.action_type, "tool_name": self.tool_name, "provider_request_count": self.provider_request_count, "model_call_count": self.model_call_count, "session_phase": self.session_phase, "terminal_category": self.terminal_category, "metadata": dict(self.metadata)}


class M16DiagnosticTelemetry:
    """Optional callback wrapper; callback failures are deliberately ignored.

    Telemetry delivery is observational. A failed observer must never alter an
    Agent decision, provider request, budget, evaluator, or terminal category.
    """
    def __init__(self, sink: Callable[[M16DiagnosticEvent], object] | None = None) -> None:
        if sink is not None and not callable(sink): raise TypeError("sink must be callable or None")
        self._sink, self._ordinal = sink, 0

    def emit(self, stage: M16DiagnosticStage, **data: Any) -> None:
        if self._sink is None: return
        self._ordinal += 1
        event = M16DiagnosticEvent(stage, self._ordinal, **data)
        try: self._sink(event)
        except Exception: pass


def diagnostic_run_id(manifest_hash: str, public_case_id: str, repetition: int) -> str:
    if not all(isinstance(value, str) and value for value in (manifest_hash, public_case_id)) or not isinstance(repetition, int) or repetition < 1:
        raise ValueError("invalid diagnostic identity")
    return f"m16diag:v1:{manifest_hash}:{public_case_id}:mind_lite_v1:r{repetition}"


def validate_diagnostic_result_directory(directory: str | Path) -> Path:
    path = Path(directory)
    if path in _HISTORICAL or path != DIAGNOSTIC_RESULT_DIRECTORY:
        raise ValueError("diagnostic telemetry must use its isolated namespace")
    return path
