"""Immutable evaluation-side observations of one external provider call."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _optional_non_negative_int(value: Any, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int or None")
    if value < 0:
        raise ValueError(f"{name} must not be negative")


@dataclass(frozen=True)
class ProviderCallObservation:
    """Measured provider resource data, separate from Agent and provider payloads."""

    request_attempts: int
    successful_requests: int
    model_calls: int
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    thinking_tokens: int | None = None
    cached_tokens: int | None = None
    latency_ms: int | None = None
    model_version: str | None = None
    provider_request_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("request_attempts", "successful_requests", "model_calls"):
            _optional_non_negative_int(getattr(self, name), name)
        if self.successful_requests > self.request_attempts:
            raise ValueError("successful_requests must not exceed request_attempts")
        if self.model_calls > self.successful_requests:
            raise ValueError("model_calls must not exceed successful_requests")
        for name in (
            "prompt_tokens", "output_tokens", "total_tokens", "thinking_tokens",
            "cached_tokens", "latency_ms",
        ):
            _optional_non_negative_int(getattr(self, name), name)
        for name in ("model_version", "provider_request_id"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a non-empty str or None")

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_attempts": self.request_attempts,
            "successful_requests": self.successful_requests,
            "model_calls": self.model_calls,
            "prompt_tokens": self.prompt_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "thinking_tokens": self.thinking_tokens,
            "cached_tokens": self.cached_tokens,
            "latency_ms": self.latency_ms,
            "model_version": self.model_version,
            "provider_request_id": self.provider_request_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderCallObservation":
        if not isinstance(data, dict):
            raise TypeError("ProviderCallObservation data must be a dict")
        return cls(**{name: data.get(name) for name in cls.__dataclass_fields__})
