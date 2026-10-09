"""Fail-closed, local financial accounting for prospective M20 feasibility work.

This module deliberately has no provider client and cannot promise a provider-side
spending cap.  It records conservative exposure before each physical dispatch.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Mapping

from src.evaluation.m20_harness import canonical_hash


M20_FINANCIAL_LEDGER_SCHEMA = "m20_feasibility_financial_ledger_v1"
M20_DEEPSEEK_V41_CHAT_TOKENIZER_ID = "deepseek_v41_chat_billing_v1"
_NANO_CNY = 1_000_000_000


class M20FinancialControlBlocked(InterruptedError):
    """A pre-dispatch financial or token-bound stop; never a provider failure."""


def require_verified_production_tokenizer(policy: "M20FeasibilityFinancialPolicy", token_counter: Any) -> None:
    """Default deny until an audited chat-envelope tokenizer is implemented.

    The official V4.1 tokenizer artifact alone does not define the provider's
    complete Chat Completions serialization or billable-token semantics.
    """
    if policy.tokenizer_identity != M20_DEEPSEEK_V41_CHAT_TOKENIZER_ID:
        raise PermissionError("unsupported production tokenizer identity")
    raise PermissionError("verified DeepSeek chat tokenizer adapter is unavailable")


@dataclass(frozen=True)
class M20FeasibilityFinancialPolicy:
    """A future signed policy; no default token bound is safe to invent."""
    tokenizer_identity: str
    input_token_limit: int
    planned_total_cny_nano: int = 50 * _NANO_CNY
    warning_cny_nano: int = 30 * _NANO_CNY
    internal_stop_cny_nano: int = 40 * _NANO_CNY
    cache_hit_input_cny_nano_per_token: int = 40
    cache_miss_input_cny_nano_per_token: int = 2_000
    output_cny_nano_per_token: int = 8_000
    max_output_tokens: int = 512
    pricing_snapshot: str = "deepseek_v4_1_flash_peak_cny_2026_10_09"

    def __post_init__(self) -> None:
        if not isinstance(self.tokenizer_identity, str) or not self.tokenizer_identity:
            raise ValueError("provider-compatible tokenizer identity is required")
        if not isinstance(self.pricing_snapshot, str) or not self.pricing_snapshot:
            raise ValueError("pricing snapshot identity is required")
        if any(not isinstance(value, int) or value < 1 for value in (
                self.input_token_limit, self.planned_total_cny_nano, self.warning_cny_nano,
                self.internal_stop_cny_nano, self.cache_hit_input_cny_nano_per_token,
                self.cache_miss_input_cny_nano_per_token, self.output_cny_nano_per_token,
                self.max_output_tokens)):
            raise ValueError("financial policy values are invalid")
        if not self.warning_cny_nano <= self.internal_stop_cny_nano <= self.planned_total_cny_nano:
            raise ValueError("financial thresholds are invalid")

    def canonical(self) -> dict[str, Any]:
        return asdict(self)


class M20FeasibilityFinancialLedger:
    """Durable attempt reservations; unknown billing is never converted to zero."""
    def __init__(self, root: Path, authorization: Mapping[str, Any], policy: M20FeasibilityFinancialPolicy,
                 token_counter: Callable[[Mapping[str, Any]], int], operator_stop_path: Path) -> None:
        if not callable(token_counter) or not isinstance(operator_stop_path, Path):
            raise TypeError("financial token counter and operator stop path are required")
        self.path = root / ".m20_execution_control" / "financial_ledger.json"
        self.authorization_digest = canonical_hash(dict(authorization))
        self.policy, self.token_counter, self.operator_stop_path = policy, token_counter, operator_stop_path

    def _expected(self) -> dict[str, Any]:
        return {"schema": M20_FINANCIAL_LEDGER_SCHEMA, "authorization_digest": self.authorization_digest,
                "policy": self.policy.canonical()}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {**self._expected(), "attempts": {}}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise PermissionError("financial ledger is unreadable") from error
        if (not isinstance(value, Mapping) or {key: value.get(key) for key in self._expected()} != self._expected() or
                not isinstance(value.get("attempts"), Mapping)):
            raise PermissionError("financial ledger binding mismatch")
        return dict(value)

    def _persist(self, value: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=self.path.parent, suffix=".tmp") as handle:
            handle.write(json.dumps(dict(value), sort_keys=True, separators=(",", ":")) + "\n")
            temporary = Path(handle.name)
        os.replace(temporary, self.path)

    def _reserve_nano(self, input_tokens: int) -> int:
        return (input_tokens * self.policy.cache_miss_input_cny_nano_per_token +
                self.policy.max_output_tokens * self.policy.output_cny_nano_per_token)

    @staticmethod
    def _usage(raw: Mapping[str, Any]) -> dict[str, int] | None:
        usage = raw.get("usage")
        if not isinstance(usage, Mapping):
            return None
        names = ("prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens")
        if any(not isinstance(usage.get(name), int) or usage[name] < 0 for name in names):
            return None
        return {name: int(usage[name]) for name in names}

    def _exposure(self, attempts: Mapping[str, Any]) -> int:
        total = 0
        for value in attempts.values():
            if not isinstance(value, Mapping) or not isinstance(value.get("reserved_cny_nano"), int):
                raise PermissionError("financial attempt state is invalid")
            observed = value.get("observed_cny_nano")
            total += int(value["reserved_cny_nano"] if observed is None else observed)
        return total

    def reserve(self, execution_id: str, logical_operation_id: str, retry_index: int,
                request: Mapping[str, Any]) -> str:
        if self.operator_stop_path.exists():
            raise M20FinancialControlBlocked("prospective feasibility operator stop requested")
        try:
            input_tokens = self.token_counter(request)
        except Exception as error:
            raise M20FinancialControlBlocked("provider-compatible input token bound unavailable") from error
        if not isinstance(input_tokens, int) or input_tokens < 0:
            raise M20FinancialControlBlocked("provider-compatible input token bound invalid")
        if input_tokens > self.policy.input_token_limit:
            raise M20FinancialControlBlocked("input token limit exceeded")
        key = canonical_hash({"execution_id": execution_id, "logical_operation_id": logical_operation_id,
                              "retry_index": retry_index})
        value = self._load(); attempts = dict(value["attempts"])
        if key in attempts:
            raise M20FinancialControlBlocked("physical attempt is already reserved or accounted")
        reserve = self._reserve_nano(input_tokens)
        exposure = self._exposure(attempts)
        if exposure + reserve > self.policy.internal_stop_cny_nano:
            raise M20FinancialControlBlocked("internal financial stop threshold reached")
        if exposure + reserve > self.policy.planned_total_cny_nano:
            raise M20FinancialControlBlocked("planned financial budget exhausted")
        attempts[key] = {"execution_id": execution_id, "logical_operation_id": logical_operation_id,
                         "retry_index": retry_index, "input_token_upper_bound": input_tokens,
                         "reserved_cny_nano": reserve, "status": "RESERVED", "usage": None,
                         "observed_cny_nano": None, "outcome": None}
        self._persist({**self._expected(), "attempts": attempts})
        return key

    def settle(self, key: str, raw: Mapping[str, Any] | None, outcome: str) -> None:
        value = self._load(); attempts = dict(value["attempts"]); attempt = attempts.get(key)
        if not isinstance(attempt, Mapping) or attempt.get("status") != "RESERVED":
            raise PermissionError("financial attempt settlement mismatch")
        usage = self._usage(raw) if isinstance(raw, Mapping) else None
        updated = dict(attempt); updated["outcome"] = outcome
        if usage is None:
            updated.update({"status": "UNRESOLVED", "usage": None, "observed_cny_nano": None})
        else:
            observed = (usage["prompt_cache_hit_tokens"] * self.policy.cache_hit_input_cny_nano_per_token +
                        usage["prompt_cache_miss_tokens"] * self.policy.cache_miss_input_cny_nano_per_token +
                        usage["completion_tokens"] * self.policy.output_cny_nano_per_token)
            updated.update({"status": "OBSERVED", "usage": usage, "observed_cny_nano": observed})
        attempts[key] = updated
        self._persist({**self._expected(), "attempts": attempts})

    def summary(self) -> dict[str, int]:
        attempts = self._load()["attempts"]
        exposure = self._exposure(attempts)
        observed = sum(int(item["observed_cny_nano"]) for item in attempts.values()
                       if item.get("status") == "OBSERVED")
        unresolved = sum(int(item["reserved_cny_nano"]) for item in attempts.values()
                         if item.get("status") != "OBSERVED")
        return {"physical_attempts": len(attempts), "logical_operations": len({item["logical_operation_id"] for item in attempts.values()}),
                "observed_cny_nano": observed, "reserved_exposure_cny_nano": exposure,
                "unresolved_cny_nano": unresolved,
                "remaining_internal_cny_nano": self.policy.internal_stop_cny_nano - exposure}
