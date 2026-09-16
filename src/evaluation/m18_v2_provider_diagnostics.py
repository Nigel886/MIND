"""Safe, deterministic provider diagnostics for M18 v2 pilot operations.

These operational records are deliberately separate from scientific run
identity and evaluator-owned outcome semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_HEADER_PATTERN = re.compile(
    r"(?i)\b(?:proxy-)?authorization\s*[:=]\s*(?:(?:bearer|basic)\s+)?[^\s,;]+"
)
_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b([a-z][a-z0-9_-]*)\s*([=:])\s*(\"[^\"]*\"|'[^']*'|[^\s,;&]+)"
)
_SECRET_NAMES = frozenset({
    "key", "apikey", "accesstoken", "token", "auth", "authorization",
    "credential", "credentials", "secret", "clientsecret", "password",
    "passwd", "signature", "sig", "xapikey",
})
_CONTRACT_CATEGORIES = frozenset({
    "http_400", "invalid_request_error", "provider_result_contract",
    "malformed_json", "model_identity_mismatch", "schema_incompatible",
})


def _normalized_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower()) if isinstance(value, str) else ""


def is_sensitive_diagnostic_name(value: object) -> bool:
    """Conservative, context-aware predicate for credential-bearing fields."""
    name = _normalized_name(value)
    return (name in _SECRET_NAMES or "secret" in name or "token" in name
            or "credential" in name or "password" in name
            or ("api" in name and "key" in name))


def _sanitize_query(value: str) -> str:
    if not value:
        return value
    pairs = parse_qsl(value, keep_blank_values=True)
    if not pairs:
        return value
    return urlencode([(key, "[REDACTED]" if is_sensitive_diagnostic_name(key) else item)
                      for key, item in pairs], doseq=True)


def _sanitize_url(match: re.Match[str]) -> str:
    raw = match.group(0)
    try:
        parsed = urlsplit(raw)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                           _sanitize_query(parsed.query), _sanitize_query(parsed.fragment)))
    except ValueError:
        return raw


def sanitize_provider_message(value: object) -> str:
    """Return bounded free text with URLs, headers, and credential assignments redacted."""
    text = value if isinstance(value, str) else type(value).__name__
    text = _URL_PATTERN.sub(_sanitize_url, text)
    text = _HEADER_PATTERN.sub("[REDACTED]", text)

    def replace_assignment(match: re.Match[str]) -> str:
        name, separator, item = match.groups()
        return name + separator + "[REDACTED]" if is_sensitive_diagnostic_name(name) else match.group(0)

    text = _ASSIGNMENT_PATTERN.sub(replace_assignment, text).strip()
    return (text or "provider_failure")[:240]


def sanitize_diagnostic_value(value: Any) -> Any:
    """Recursively sanitize structured evidence before any serialization boundary."""
    if isinstance(value, Mapping):
        return {str(key): "[REDACTED]" if is_sensitive_diagnostic_name(key)
                else sanitize_diagnostic_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_diagnostic_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_diagnostic_value(item) for item in value)
    return sanitize_provider_message(value) if isinstance(value, str) else value


@dataclass(frozen=True)
class M18V2ProviderDiagnostic:
    """Public-safe, stable provider-failure evidence for one logical call."""

    category: str
    comparator: str
    stage: str
    logical_call_index: int
    transport_attempts: int
    retry_exhausted: bool
    message_summary: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value.strip() for value in (
            self.category, self.comparator, self.stage, self.message_summary,
        )):
            raise ValueError("provider diagnostic strings must be non-empty")
        if (not isinstance(self.logical_call_index, int)
                or self.logical_call_index < 1
                or not isinstance(self.transport_attempts, int)
                or self.transport_attempts < 0):
            raise ValueError("provider diagnostic accounting is invalid")
        if not isinstance(self.retry_exhausted, bool):
            raise TypeError("retry_exhausted must be bool")
        object.__setattr__(self, "message_summary", sanitize_provider_message(self.message_summary))

    @property
    def is_contract_incompatibility(self) -> bool:
        return self.category in _CONTRACT_CATEGORIES

    def to_dict(self) -> dict[str, object]:
        return {
            "category": self.category,
            "comparator": self.comparator,
            "stage": self.stage,
            "logical_call_index": self.logical_call_index,
            "transport_attempts": self.transport_attempts,
            "retry_exhausted": self.retry_exhausted,
            "message_summary": self.message_summary,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "M18V2ProviderDiagnostic":
        expected = {"category", "comparator", "stage", "logical_call_index",
                    "transport_attempts", "retry_exhausted", "message_summary"}
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ValueError("provider diagnostic schema mismatch")
        return cls(value["category"], value["comparator"], value["stage"],
                   value["logical_call_index"], value["transport_attempts"],
                   value["retry_exhausted"], value["message_summary"])


class M18V2ProviderExecutionFailure(RuntimeError):
    """Typed boundary error; it must not be converted into integrity failure."""

    def __init__(self, diagnostic: M18V2ProviderDiagnostic) -> None:
        super().__init__(diagnostic.category)
        self.diagnostic = diagnostic


@dataclass(frozen=True)
class M18V2SystematicProviderStopEvent:
    """Operational stop evidence, never a benchmark result."""

    comparator: str
    stage: str
    category: str
    affected_run_ids: tuple[str, ...]
    evidence_count: int
    stopping_rule: str = "two_independent_structural_failures_same_comparator_stage_category_v1"

    def __post_init__(self) -> None:
        if (not all(isinstance(value, str) and value for value in (self.comparator, self.stage, self.category, self.stopping_rule))
                or len(self.affected_run_ids) != self.evidence_count
                or self.evidence_count < 2
                or len(set(self.affected_run_ids)) != len(self.affected_run_ids)):
            raise ValueError("invalid systematic provider stop event")

    def to_dict(self) -> dict[str, object]:
        return {"event_schema": "m18_v2_systematic_provider_stop_v1",
                "comparator": self.comparator, "stage": self.stage,
                "category": self.category, "affected_run_ids": list(self.affected_run_ids),
                "evidence_count": self.evidence_count, "stopping_rule": self.stopping_rule}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "M18V2SystematicProviderStopEvent":
        expected = {"event_schema", "comparator", "stage", "category", "affected_run_ids", "evidence_count", "stopping_rule"}
        if not isinstance(value, Mapping) or set(value) != expected or value["event_schema"] != "m18_v2_systematic_provider_stop_v1":
            raise ValueError("systematic provider stop schema mismatch")
        if not isinstance(value["affected_run_ids"], list):
            raise ValueError("systematic provider stop run IDs invalid")
        return cls(value["comparator"], value["stage"], value["category"],
                   tuple(value["affected_run_ids"]), value["evidence_count"], value["stopping_rule"])


class M18V2SystematicProviderStop(RuntimeError):
    def __init__(self, event: M18V2SystematicProviderStopEvent) -> None:
        super().__init__("systematic_provider_contract_incompatibility")
        self.event = event


def normalize_provider_failure(error: BaseException, *, comparator: str, stage: str,
                               logical_call_index: int, fallback_transport_attempts: int,
                               retry_limit: int = 3) -> M18V2ProviderDiagnostic:
    """Project already available error metadata without changing provider behavior."""
    category = getattr(error, "category", None)
    safe_category = category if isinstance(category, str) and category else type(error).__name__.lower()
    logical = getattr(error, "logical_call_id", logical_call_index)
    attempts = getattr(error, "transport_attempts", fallback_transport_attempts)
    if not isinstance(logical, int) or logical < 1:
        logical = logical_call_index
    if not isinstance(attempts, int) or attempts < 0:
        attempts = fallback_transport_attempts
    return M18V2ProviderDiagnostic(
        safe_category, comparator, stage, logical, attempts,
        attempts >= retry_limit and attempts > 0, sanitize_provider_message(str(error)),
    )
