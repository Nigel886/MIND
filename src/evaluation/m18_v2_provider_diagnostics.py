"""Safe, deterministic provider diagnostics for M18 v2 pilot operations.

Every provider-derived value is untrusted. Persisted machine categories are
finite internal values; descriptive provider text is sanitized before it can
cross a serialization boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_HEADER_PATTERN = re.compile(r"(?i)\b(?:proxy-)?authorization\s*[:=]\s*(?:(?:bearer|basic)\s+)?[^\s,;]+")
_ASSIGNMENT_PATTERN = re.compile(r"(?i)\b([a-z][a-z0-9_-]*)\s*([=:])\s*(\"[^\"]*\"|'[^']*'|[^\s,;&]+)")
_SECRET_NAMES = frozenset({"key", "apikey", "accesstoken", "token", "auth", "authorization", "credential", "credentials", "secret", "clientsecret", "password", "passwd", "signature", "sig", "xapikey", "reason"})
_COMPARATORS = frozenset({"mind_lite_v11", "direct_tool_calling", "react", "plan_and_execute"})
_STAGES = frozenset({"mind_policy", "direct_decision", "react_decision", "plan_planner", "plan_executor", "plan_replan"})


class M18V2ProviderDiagnosticCategory(str, Enum):
    HTTP_4XX = "http_4xx"
    HTTP_5XX = "http_5xx"
    INVALID_REQUEST = "invalid_request"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    TRANSPORT_ERROR = "transport_error"
    PROVIDER_CONTRACT_ERROR = "provider_contract_error"
    PROVIDER_ERROR = "provider_error"
    UNKNOWN_PROVIDER_ERROR = "unknown_provider_error"


class M18V2SystematicStopCategory(str, Enum):
    SYSTEMATIC_PROVIDER_CONTRACT_FAILURE = "systematic_provider_contract_failure"


class M18V2SystematicStopReason(str, Enum):
    """The sole internal reason for the existing structural stop policy."""

    TWO_INDEPENDENT_CONTRACT_FAILURES = (
        "two_independent_structural_failures_same_comparator_stage_category_v1"
    )


def _normalized_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower()) if isinstance(value, str) else ""


def is_sensitive_diagnostic_name(value: object) -> bool:
    name = _normalized_name(value)
    return (name in _SECRET_NAMES or "secret" in name or "token" in name
            or "credential" in name or "password" in name
            or ("api" in name and "key" in name))


def _sanitize_query(value: str) -> str:
    pairs = parse_qsl(value, keep_blank_values=True)
    if not pairs:
        return value
    return urlencode([(key, "[REDACTED]" if is_sensitive_diagnostic_name(key) else item)
                      for key, item in pairs], doseq=True)


def _sanitize_url(match: re.Match[str]) -> str:
    try:
        parsed = urlsplit(match.group(0))
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                           _sanitize_query(parsed.query), _sanitize_query(parsed.fragment)))
    except ValueError:
        return match.group(0)


def sanitize_provider_message(value: object) -> str:
    """Return bounded provider text with credential assignments redacted."""
    text = value if isinstance(value, str) else type(value).__name__
    text = _URL_PATTERN.sub(_sanitize_url, text)
    text = _HEADER_PATTERN.sub("[REDACTED]", text)

    def replace_assignment(match: re.Match[str]) -> str:
        name, separator, item = match.groups()
        if name.lower() in {"http", "https"} and separator == ":" and item.startswith("//"):
            return match.group(0)
        previous = match.string[match.start() - 1] if match.start() else ""
        if previous in {"?", "&"}:
            return name + separator + "[REDACTED]" if is_sensitive_diagnostic_name(name) else match.group(0)
        # Provider strings cannot introduce structured diagnostic fields.
        # Redacting every assignment protects unknown names such as type/code.
        return name + separator + "[REDACTED]"

    return (text and _ASSIGNMENT_PATTERN.sub(replace_assignment, text).strip() or "provider_failure")[:240]


def sanitize_diagnostic_value(value: Any) -> Any:
    """Recursively sanitize future structured diagnostic evidence."""
    if isinstance(value, Mapping):
        return {str(key): "[REDACTED]" if is_sensitive_diagnostic_name(key) else sanitize_diagnostic_value(item)
                for key, item in value.items()}
    if isinstance(value, list): return [sanitize_diagnostic_value(item) for item in value]
    if isinstance(value, tuple): return tuple(sanitize_diagnostic_value(item) for item in value)
    return sanitize_provider_message(value) if isinstance(value, str) else value


def _http_status(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 599:
        return value
    text = value if isinstance(value, str) else ""
    match = re.search(r"(?i)(?:http[_\s-]*)?([1-5][0-9]{2})\b", text)
    return int(match.group(1)) if match else None


def canonical_provider_category(value: object) -> tuple[M18V2ProviderDiagnosticCategory, int | None]:
    """Map arbitrary provider text to finite internal category and typed status."""
    if isinstance(value, M18V2ProviderDiagnosticCategory):
        return value, None
    if isinstance(value, str):
        try:
            return M18V2ProviderDiagnosticCategory(value), None
        except ValueError:
            pass
    status = _http_status(value)
    text = sanitize_provider_message(value).lower()
    if "invalid_request" in text or "invalid request" in text:
        return M18V2ProviderDiagnosticCategory.INVALID_REQUEST, status or 400
    if any(marker in text for marker in ("model_identity", "malformed_json", "provider_result_contract", "schema_incompatible")):
        return M18V2ProviderDiagnosticCategory.PROVIDER_CONTRACT_ERROR, status
    if status is not None:
        if status == 401: return M18V2ProviderDiagnosticCategory.AUTHENTICATION_ERROR, status
        if status == 403: return M18V2ProviderDiagnosticCategory.AUTHORIZATION_ERROR, status
        if status == 429: return M18V2ProviderDiagnosticCategory.RATE_LIMIT, status
        if 400 <= status < 500: return M18V2ProviderDiagnosticCategory.HTTP_4XX, status
        if 500 <= status < 600: return M18V2ProviderDiagnosticCategory.HTTP_5XX, status
    if "rate" in text or "quota" in text: return M18V2ProviderDiagnosticCategory.RATE_LIMIT, status
    if "timeout" in text: return M18V2ProviderDiagnosticCategory.TIMEOUT, status
    if "connection" in text or "reset" in text or "dns" in text: return M18V2ProviderDiagnosticCategory.CONNECTION_ERROR, status
    if "transport" in text: return M18V2ProviderDiagnosticCategory.TRANSPORT_ERROR, status
    if text.strip() == "provider_error": return M18V2ProviderDiagnosticCategory.PROVIDER_ERROR, status
    return M18V2ProviderDiagnosticCategory.UNKNOWN_PROVIDER_ERROR, status


def _canonical_comparator(value: object) -> str:
    return value if isinstance(value, str) and value in _COMPARATORS else "unknown_comparator"


def _canonical_stage(value: object) -> str:
    return value if isinstance(value, str) and value in _STAGES else "unknown_provider_stage"


@dataclass(frozen=True)
class M18V2ProviderDiagnostic:
    category: M18V2ProviderDiagnosticCategory | str
    comparator: str
    stage: str
    logical_call_index: int
    transport_attempts: int
    retry_exhausted: bool
    message_summary: str
    http_status: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.message_summary, str) or not self.message_summary.strip():
            raise ValueError("provider diagnostic message must be non-empty")
        if (not isinstance(self.logical_call_index, int) or self.logical_call_index < 1
                or not isinstance(self.transport_attempts, int) or self.transport_attempts < 0):
            raise ValueError("provider diagnostic accounting is invalid")
        if not isinstance(self.retry_exhausted, bool): raise TypeError("retry_exhausted must be bool")
        category, inferred_status = canonical_provider_category(self.category)
        status = self.http_status if isinstance(self.http_status, int) and not isinstance(self.http_status, bool) and 100 <= self.http_status <= 599 else inferred_status
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "comparator", _canonical_comparator(self.comparator))
        object.__setattr__(self, "stage", _canonical_stage(self.stage))
        object.__setattr__(self, "http_status", status)
        object.__setattr__(self, "message_summary", sanitize_provider_message(self.message_summary))

    @property
    def is_contract_incompatibility(self) -> bool:
        return self.category in {M18V2ProviderDiagnosticCategory.HTTP_4XX, M18V2ProviderDiagnosticCategory.INVALID_REQUEST, M18V2ProviderDiagnosticCategory.PROVIDER_CONTRACT_ERROR}

    def to_dict(self) -> dict[str, object]:
        return {"category": self.category.value, "comparator": self.comparator, "stage": self.stage,
                "logical_call_index": self.logical_call_index, "transport_attempts": self.transport_attempts,
                "retry_exhausted": self.retry_exhausted, "message_summary": self.message_summary,
                "http_status": self.http_status}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "M18V2ProviderDiagnostic":
        expected = {"category", "comparator", "stage", "logical_call_index", "transport_attempts", "retry_exhausted", "message_summary", "http_status"}
        if not isinstance(value, Mapping) or set(value) != expected: raise ValueError("provider diagnostic schema mismatch")
        return cls(value["category"], value["comparator"], value["stage"], value["logical_call_index"], value["transport_attempts"], value["retry_exhausted"], value["message_summary"], value["http_status"])


class M18V2ProviderExecutionFailure(RuntimeError):
    def __init__(self, diagnostic: M18V2ProviderDiagnostic) -> None:
        super().__init__(diagnostic.category.value)
        self.diagnostic = diagnostic


@dataclass(frozen=True)
class M18V2SystematicProviderStopEvent:
    comparator: str
    stage: str
    provider_category: M18V2ProviderDiagnosticCategory | str
    affected_run_ids: tuple[str, ...]
    evidence_count: int
    category: M18V2SystematicStopCategory = M18V2SystematicStopCategory.SYSTEMATIC_PROVIDER_CONTRACT_FAILURE
    http_status: int | None = None
    stopping_rule: M18V2SystematicStopReason | str = (
        M18V2SystematicStopReason.TWO_INDEPENDENT_CONTRACT_FAILURES
    )

    def __post_init__(self) -> None:
        provider_category, inferred_status = canonical_provider_category(self.provider_category)
        status = self.http_status if isinstance(self.http_status, int) and not isinstance(self.http_status, bool) and 100 <= self.http_status <= 599 else inferred_status
        if (len(self.affected_run_ids) != self.evidence_count or self.evidence_count < 2
                or len(set(self.affected_run_ids)) != len(self.affected_run_ids)):
            raise ValueError("invalid systematic provider stop event")
        object.__setattr__(self, "comparator", _canonical_comparator(self.comparator))
        object.__setattr__(self, "stage", _canonical_stage(self.stage))
        object.__setattr__(self, "provider_category", provider_category)
        object.__setattr__(self, "category", M18V2SystematicStopCategory.SYSTEMATIC_PROVIDER_CONTRACT_FAILURE)
        object.__setattr__(self, "http_status", status)
        object.__setattr__(self, "stopping_rule", M18V2SystematicStopReason.TWO_INDEPENDENT_CONTRACT_FAILURES)

    def to_dict(self) -> dict[str, object]:
        return {"event_schema": "m18_v2_systematic_provider_stop_v1", "comparator": self.comparator,
                "stage": self.stage, "category": self.category.value,
                "provider_category": self.provider_category.value, "http_status": self.http_status,
                "affected_run_ids": list(self.affected_run_ids), "evidence_count": self.evidence_count,
                "stopping_rule": self.stopping_rule.value}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "M18V2SystematicProviderStopEvent":
        expected = {"event_schema", "comparator", "stage", "category", "provider_category", "http_status", "affected_run_ids", "evidence_count", "stopping_rule"}
        if (not isinstance(value, Mapping) or set(value) != expected or value["event_schema"] != "m18_v2_systematic_provider_stop_v1"
                or value["category"] != M18V2SystematicStopCategory.SYSTEMATIC_PROVIDER_CONTRACT_FAILURE.value
                or not isinstance(value["affected_run_ids"], list)):
            raise ValueError("systematic provider stop schema mismatch")
        return cls(value["comparator"], value["stage"], value["provider_category"], tuple(value["affected_run_ids"]), value["evidence_count"], M18V2SystematicStopCategory.SYSTEMATIC_PROVIDER_CONTRACT_FAILURE, value["http_status"], value["stopping_rule"])


class M18V2SystematicProviderStop(RuntimeError):
    def __init__(self, event: M18V2SystematicProviderStopEvent) -> None:
        super().__init__(M18V2SystematicStopCategory.SYSTEMATIC_PROVIDER_CONTRACT_FAILURE.value)
        self.event = event


def normalize_provider_failure(error: BaseException, *, comparator: str, stage: str,
                               logical_call_index: int, fallback_transport_attempts: int,
                               retry_limit: int = 3) -> M18V2ProviderDiagnostic:
    raw_category = getattr(error, "category", None)
    raw_category = raw_category if isinstance(raw_category, str) and raw_category else type(error).__name__.lower()
    logical = getattr(error, "logical_call_id", logical_call_index)
    attempts = getattr(error, "transport_attempts", fallback_transport_attempts)
    if not isinstance(logical, int) or logical < 1: logical = logical_call_index
    if not isinstance(attempts, int) or attempts < 0: attempts = fallback_transport_attempts
    return M18V2ProviderDiagnostic(raw_category, comparator, stage, logical, attempts,
                                   attempts >= retry_limit and attempts > 0,
                                   sanitize_provider_message(str(error)))
