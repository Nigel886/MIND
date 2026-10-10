"""Fail-closed, local financial accounting for prospective M20 feasibility work.

This module deliberately has no provider client and cannot promise a provider-side
spending cap.  It records conservative exposure before each physical dispatch.
"""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Mapping

from src.evaluation.m20_harness import canonical_hash


M20_FINANCIAL_LEDGER_SCHEMA = "m20_feasibility_financial_ledger_v1"
M20_OWNER_RISK_FINANCIAL_LEDGER_SCHEMA = "m20_feasibility_financial_ledger_v2"
M20_DEEPSEEK_V41_CHAT_TOKENIZER_ID = "deepseek_v41_chat_billing_v1"
M20_OWNER_RISK_ACCEPTED_POLICY_ID = "m20_owner_risk_accepted_execution_v1"
M20_LEGACY_OWNER_RISK_ACCEPTED_POLICY_ID = "m20_owner_risk_accepted_unknown_input_v1"
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


@dataclass(frozen=True)
class M20OwnerRiskAcceptedFinancialPolicy:
    """Prospective owner policy for an explicitly unbounded input-billing risk.

    This is deliberately a different policy family from tokenizer-backed admission.
    It records known output exposure and halts permanently after the first billing
    ambiguity; it is not, and must never be presented as, a provider spending cap.
    """
    policy_identity: str = M20_OWNER_RISK_ACCEPTED_POLICY_ID
    planned_total_cny_nano: int = 50 * _NANO_CNY
    warning_cny_nano: int = 30 * _NANO_CNY
    internal_stop_cny_nano: int = 40 * _NANO_CNY
    cache_hit_input_cny_nano_per_token: int = 40
    cache_miss_input_cny_nano_per_token: int = 2_000
    output_cny_nano_per_token: int = 8_000
    max_output_tokens: int = 512
    pricing_snapshot: str = "deepseek_v4_1_flash_peak_cny_2026_10_09"
    strictly_sequential_physical_dispatch: bool = True
    halt_after_unresolved_billing: bool = True
    input_billing_exposure: str = "owner_accepted_unknown"

    def __post_init__(self) -> None:
        if self.policy_identity != M20_OWNER_RISK_ACCEPTED_POLICY_ID:
            raise ValueError("owner risk policy identity is invalid")
        if not isinstance(self.pricing_snapshot, str) or not self.pricing_snapshot:
            raise ValueError("owner risk pricing snapshot is required")
        if self.input_billing_exposure != "owner_accepted_unknown":
            raise ValueError("owner risk input exposure declaration is invalid")
        if not self.strictly_sequential_physical_dispatch or not self.halt_after_unresolved_billing:
            raise ValueError("owner risk safety controls are mandatory")
        if any(not isinstance(value, int) or value < 1 for value in (
                self.planned_total_cny_nano, self.warning_cny_nano,
                self.internal_stop_cny_nano, self.cache_hit_input_cny_nano_per_token,
                self.cache_miss_input_cny_nano_per_token, self.output_cny_nano_per_token,
                self.max_output_tokens)):
            raise ValueError("owner risk financial values are invalid")
        if not self.warning_cny_nano <= self.internal_stop_cny_nano <= self.planned_total_cny_nano:
            raise ValueError("owner risk financial thresholds are invalid")

    def canonical(self) -> dict[str, Any]:
        return asdict(self)


class M20FeasibilityFinancialLedger:
    """Durable attempt reservations; unknown billing is never converted to zero."""
    def __init__(self, root: Path, authorization: Mapping[str, Any],
                 policy: M20FeasibilityFinancialPolicy | M20OwnerRiskAcceptedFinancialPolicy,
                 token_counter: Callable[[Mapping[str, Any]], int] | None, operator_stop_path: Path) -> None:
        if not isinstance(operator_stop_path, Path):
            raise TypeError("operator stop path is required")
        if isinstance(policy, M20FeasibilityFinancialPolicy):
            if not callable(token_counter):
                raise TypeError("financial token counter is required")
        elif isinstance(policy, M20OwnerRiskAcceptedFinancialPolicy):
            if token_counter is not None:
                raise TypeError("owner risk admission does not accept a tokenizer counter")
        else:
            raise TypeError("financial policy is invalid")
        self.path = root / ".m20_execution_control" / "financial_ledger.json"
        self.dispatch_lock_path = root / ".m20_execution_control" / "physical_dispatch.lock"
        self.authorization_digest = canonical_hash(dict(authorization))
        self.policy, self.token_counter, self.operator_stop_path = policy, token_counter, operator_stop_path
        self.schema = M20_OWNER_RISK_FINANCIAL_LEDGER_SCHEMA if isinstance(policy, M20OwnerRiskAcceptedFinancialPolicy) else M20_FINANCIAL_LEDGER_SCHEMA

    def _expected(self) -> dict[str, Any]:
        return {"schema": self.schema, "authorization_digest": self.authorization_digest,
                "policy": self.policy.canonical()}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {**self._expected(), "attempts": {}, "dispatch_halted": False, "halt_reason": None}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise PermissionError("financial ledger is unreadable") from error
        if (not isinstance(value, Mapping) or {key: value.get(key) for key in self._expected()} != self._expected() or
                not isinstance(value.get("attempts"), Mapping) or
                not isinstance(value.get("dispatch_halted"), bool) or
                (value.get("halt_reason") is not None and not isinstance(value.get("halt_reason"), str))):
            raise PermissionError("financial ledger binding mismatch")
        return dict(value)

    def _persist(self, value: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=self.path.parent, suffix=".tmp") as handle:
            handle.write(json.dumps(dict(value), sort_keys=True, separators=(",", ":")) + "\n")
            temporary = Path(handle.name)
        # Windows security/indexing handles can briefly retain the previous
        # ledger file.  Preserve atomic replacement, but tolerate only a
        # bounded transient lock; failure remains fail-closed.
        for attempt in range(3):
            try:
                os.replace(temporary, self.path)
                return
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.02)

    def _reserve_nano(self, input_tokens: int) -> int:
        return (input_tokens * self.policy.cache_miss_input_cny_nano_per_token +
                self.policy.max_output_tokens * self.policy.output_cny_nano_per_token)

    def _owner_risk_reserve_nano(self) -> int:
        if not isinstance(self.policy, M20OwnerRiskAcceptedFinancialPolicy):
            raise PermissionError("owner risk policy is required")
        return self.policy.max_output_tokens * self.policy.output_cny_nano_per_token

    @contextmanager
    def physical_dispatch(self):
        """Exclusive, crash-fail-closed lease across processes for one dispatch."""
        self.dispatch_lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.dispatch_lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            raise M20FinancialControlBlocked("another physical feasibility dispatch is active or unreconciled") from error
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"authorization_digest": self.authorization_digest,
                                         "pid": os.getpid()}, sort_keys=True, separators=(",", ":")) + "\n")
                handle.flush(); os.fsync(handle.fileno())
            yield
        finally:
            try:
                self.dispatch_lock_path.unlink()
            except FileNotFoundError:
                pass

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
                request: Mapping[str, Any], *, work_id: str | None = None,
                provider: str | None = None, model: str | None = None) -> str:
        if self.operator_stop_path.exists():
            raise M20FinancialControlBlocked("prospective feasibility operator stop requested")
        if isinstance(self.policy, M20FeasibilityFinancialPolicy):
            try:
                input_tokens = self.token_counter(request)
            except Exception as error:
                raise M20FinancialControlBlocked("provider-compatible input token bound unavailable") from error
            if not isinstance(input_tokens, int) or input_tokens < 0:
                raise M20FinancialControlBlocked("provider-compatible input token bound invalid")
            if input_tokens > self.policy.input_token_limit:
                raise M20FinancialControlBlocked("input token limit exceeded")
            reserve, input_bound = self._reserve_nano(input_tokens), input_tokens
        else:
            reserve, input_bound = self._owner_risk_reserve_nano(), None
        key = canonical_hash({"execution_id": execution_id, "logical_operation_id": logical_operation_id,
                              "retry_index": retry_index})
        value = self._load(); attempts = dict(value["attempts"])
        if value["dispatch_halted"]:
            raise M20FinancialControlBlocked("financial ambiguity permanently blocks later dispatch")
        if key in attempts:
            raise M20FinancialControlBlocked("physical attempt is already reserved or accounted")
        exposure = self._exposure(attempts)
        if exposure + reserve > self.policy.internal_stop_cny_nano:
            raise M20FinancialControlBlocked("internal financial stop threshold reached")
        if exposure + reserve > self.policy.planned_total_cny_nano:
            raise M20FinancialControlBlocked("planned financial budget exhausted")
        attempts[key] = {"execution_id": execution_id, "logical_operation_id": logical_operation_id,
                          "retry_index": retry_index, "input_token_upper_bound": input_bound,
                          "reserved_cny_nano": reserve, "status": "RESERVED", "usage": None,
                          "observed_cny_nano": None, "outcome": None, "work_id": work_id,
                          "provider": provider, "model": model,
                          "policy_identity": getattr(self.policy, "policy_identity", None),
                          "physical_attempt_id": key, "transport_outcome": None,
                          "response_validation_outcome": None, "terminal_outcome": None}
        self._persist({**self._expected(), "attempts": attempts,
                       "dispatch_halted": value["dispatch_halted"], "halt_reason": value["halt_reason"]})
        return key

    def mark_dispatched(self, key: str) -> None:
        """Durably distinguish a reservation from a transport invocation.

        A crash in either state is deliberately fail-closed.  In particular,
        ``DISPATCHED`` is evidence only that local code invoked transport; it is
        not evidence that the provider received or billed the request.
        """
        value = self._load(); attempts = dict(value["attempts"]); attempt = attempts.get(key)
        if not isinstance(attempt, Mapping) or attempt.get("status") != "RESERVED":
            raise PermissionError("financial attempt dispatch transition mismatch")
        updated = dict(attempt); updated["status"] = "DISPATCHED"; attempts[key] = updated
        self._persist({**self._expected(), "attempts": attempts,
                       "dispatch_halted": value["dispatch_halted"], "halt_reason": value["halt_reason"]})

    def settle(self, key: str, raw: Mapping[str, Any] | None, outcome: str) -> None:
        value = self._load(); attempts = dict(value["attempts"]); attempt = attempts.get(key)
        if not isinstance(attempt, Mapping) or attempt.get("status") != "DISPATCHED":
            raise PermissionError("financial attempt settlement mismatch")
        usage = self._usage(raw) if isinstance(raw, Mapping) else None
        updated = dict(attempt); updated["outcome"] = outcome
        halted, halt_reason = value["dispatch_halted"], value["halt_reason"]
        if usage is None:
            updated.update({"status": "SETTLED", "billing_status": "UNRESOLVED", "usage": None, "observed_cny_nano": None})
            if isinstance(self.policy, M20OwnerRiskAcceptedFinancialPolicy):
                halted, halt_reason = True, "provider_usage_missing_or_invalid"
        else:
            observed = (usage["prompt_cache_hit_tokens"] * self.policy.cache_hit_input_cny_nano_per_token +
                        usage["prompt_cache_miss_tokens"] * self.policy.cache_miss_input_cny_nano_per_token +
                        usage["completion_tokens"] * self.policy.output_cny_nano_per_token)
            updated.update({"status": "SETTLED", "billing_status": "OBSERVED", "usage": usage, "observed_cny_nano": observed})
        attempts[key] = updated
        self._persist({**self._expected(), "attempts": attempts,
                       "dispatch_halted": halted, "halt_reason": halt_reason})

    def ensure_replacement_allowed(self) -> None:
        self.ensure_dispatch_allowed()

    def ensure_dispatch_allowed(self) -> None:
        """Reject a new work item before it can create a provider attempt."""
        if self.operator_stop_path.exists():
            raise M20FinancialControlBlocked("prospective feasibility operator stop requested")
        value = self._load()
        if value["dispatch_halted"]:
            raise M20FinancialControlBlocked("financial ambiguity permanently blocks later dispatch")

    def reconcile_telemetry(self, execution_id: str, retries: Any) -> None:
        """Require one settled ledger identity for each persisted retry attempt."""
        if not isinstance(execution_id, str) or not execution_id:
            raise TypeError("execution identity is required for financial reconciliation")
        expected: set[tuple[str, int]] = set()
        for retry in retries:
            logical = getattr(retry, "logical_operation_id", None)
            index = getattr(retry, "retry_index", None)
            if not isinstance(logical, str) or not logical or not isinstance(index, int) or index < 0:
                raise PermissionError("telemetry retry identity is invalid")
            if (logical, index) in expected:
                raise PermissionError("duplicate telemetry physical attempt identity")
            expected.add((logical, index))
        value = self._load()
        actual = {(item.get("logical_operation_id"), item.get("retry_index")): item
                  for item in value["attempts"].values() if item.get("execution_id") == execution_id}
        if set(actual) != expected:
            raise M20FinancialControlBlocked("financial and telemetry physical attempt identities do not reconcile")
        if any(item.get("status") != "SETTLED" for item in actual.values()):
            raise M20FinancialControlBlocked("financial attempt is not settled for persisted telemetry")

    def summary(self) -> dict[str, int]:
        value = self._load(); attempts = value["attempts"]
        exposure = self._exposure(attempts)
        observed = sum(int(item["observed_cny_nano"]) for item in attempts.values()
                       if item.get("billing_status") == "OBSERVED")
        unresolved = sum(int(item["reserved_cny_nano"]) for item in attempts.values()
                          if item.get("billing_status") != "OBSERVED")
        return {"physical_attempts": len(attempts), "logical_operations": len({item["logical_operation_id"] for item in attempts.values()}),
                "observed_cny_nano": observed, "reserved_exposure_cny_nano": exposure,
                "unresolved_cny_nano": unresolved,
                "remaining_internal_cny_nano": self.policy.internal_stop_cny_nano - exposure,
                "financial_ambiguity_halted": int(value["dispatch_halted"])}
