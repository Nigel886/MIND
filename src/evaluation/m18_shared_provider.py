"""Frozen, shared M18 DeepSeek provider condition.

This module is evaluation infrastructure only.  It has no task-suite imports,
does not execute actions, and provides no parsing fallback or semantic cache.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
import time
from types import MappingProxyType
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


M18_SHARED_PROVIDER_CONFIG_VERSION = "m18_shared_provider_config_v1"
M18_DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _freeze_mapping(value: Mapping[str, Any]) -> MappingProxyType:
    return MappingProxyType(json.loads(_canonical(dict(value))))


@dataclass(frozen=True)
class M18TransportRetryPolicy:
    """Transport-only retry policy; semantic responses are never retried."""

    max_retries: int = 2
    backoff_seconds: tuple[float, float] = (0.5, 1.0)
    retryable: tuple[str, ...] = (
        "connect_timeout", "read_timeout", "connection_reset_or_eof",
        "dns_temporary_failure", "http_500", "http_502", "http_503", "http_504",
    )
    non_retryable: tuple[str, ...] = (
        "http_4xx", "certificate_validation_failure", "malformed_json",
        "schema_invalid", "finish_reason_length", "unsupported_output",
    )

    def __post_init__(self) -> None:
        if self.max_retries != 2 or self.backoff_seconds != (0.5, 1.0):
            raise ValueError("M18 transport retry policy is frozen")
        if len(self.retryable) != len(set(self.retryable)) or len(self.non_retryable) != len(set(self.non_retryable)):
            raise ValueError("retry policy categories must be unique")

    @property
    def max_attempts(self) -> int:
        return self.max_retries + 1

    def to_dict(self) -> dict[str, Any]:
        return {"max_retries": self.max_retries, "backoff_seconds": list(self.backoff_seconds),
                "retryable": list(self.retryable), "non_retryable": list(self.non_retryable)}


@dataclass(frozen=True)
class M18SharedProviderConfiguration:
    """Canonical public identity of the single M18 real-provider condition."""

    provider: str = "deepseek_api"
    api_surface: str = "openai_chat_completions"
    base_url: str = "https://api.deepseek.com"
    requested_model: str = "deepseek-flash"
    documented_model_identity: str = "DeepSeek-V4.1-Flash"
    thinking: Mapping[str, str] = None  # type: ignore[assignment]
    temperature: int = 0
    top_p: int = 1
    max_output_tokens: int = 512
    response_format: Mapping[str, str] = None  # type: ignore[assignment]
    stream: bool = False
    timeout_seconds_per_transport_attempt: int = 60
    transport_retry: M18TransportRetryPolicy = M18TransportRetryPolicy()
    application_response_cache: str = "disabled"
    provider_native_cache: str = "not_configured_telemetry_only_if_exposed"

    def __post_init__(self) -> None:
        thinking = {"type": "disabled"} if self.thinking is None else dict(self.thinking)
        response_format = {"type": "json_object"} if self.response_format is None else dict(self.response_format)
        frozen = (self.provider, self.api_surface, self.base_url, self.requested_model,
                  self.documented_model_identity, self.temperature, self.top_p,
                  self.max_output_tokens, self.stream, self.timeout_seconds_per_transport_attempt,
                  self.application_response_cache, self.provider_native_cache)
        expected = ("deepseek_api", "openai_chat_completions", "https://api.deepseek.com", "deepseek-flash",
                    "DeepSeek-V4.1-Flash", 0, 1, 512, False, 60, "disabled",
                    "not_configured_telemetry_only_if_exposed")
        if frozen != expected or thinking != {"type": "disabled"} or response_format != {"type": "json_object"}:
            raise ValueError("M18 shared provider configuration is frozen")
        if not isinstance(self.transport_retry, M18TransportRetryPolicy):
            raise TypeError("transport_retry must be M18TransportRetryPolicy")
        object.__setattr__(self, "thinking", _freeze_mapping(thinking))
        object.__setattr__(self, "response_format", _freeze_mapping(response_format))

    def to_dict(self) -> dict[str, Any]:
        return {"config_version": M18_SHARED_PROVIDER_CONFIG_VERSION, "provider": self.provider,
                "api_surface": self.api_surface, "base_url": self.base_url,
                "requested_model": self.requested_model,
                "documented_model_identity": self.documented_model_identity,
                "thinking": dict(self.thinking), "temperature": self.temperature, "top_p": self.top_p,
                "max_output_tokens": self.max_output_tokens, "response_format": dict(self.response_format),
                "stream": self.stream, "timeout_seconds_per_transport_attempt": self.timeout_seconds_per_transport_attempt,
                "transport_retry": self.transport_retry.to_dict(),
                "application_response_cache": self.application_response_cache,
                "provider_native_cache": self.provider_native_cache}

    @property
    def config_hash(self) -> str:
        return sha256(_canonical(self.to_dict()).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class M18ProviderResponse:
    """Architecture-neutral completed provider envelope; reasoning is omitted."""

    requested_model: str
    returned_model: str | None
    content: str
    finish_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cached_tokens: int | None
    transport_attempts: int
    logical_call_id: int
    infrastructure_status: str
    latency_ms: int

    def __post_init__(self) -> None:
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("provider content must be a non-empty string")
        if self.transport_attempts < 1 or self.logical_call_id < 1 or self.latency_ms < 0:
            raise ValueError("provider accounting must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {"requested_model": self.requested_model, "returned_model": self.returned_model,
                "content": self.content, "finish_reason": self.finish_reason,
                "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens, "cached_tokens": self.cached_tokens,
                "transport_attempts": self.transport_attempts, "logical_call_id": self.logical_call_id,
                "infrastructure_status": self.infrastructure_status, "latency_ms": self.latency_ms}


class M18ProviderTransportError(RuntimeError):
    def __init__(self, category: str, transport_attempts: int, logical_call_id: int) -> None:
        super().__init__(category)
        self.category, self.transport_attempts, self.logical_call_id = category, transport_attempts, logical_call_id


HttpPost = Callable[[str, Mapping[str, str], bytes, int], dict[str, Any]]


def _post_json(url: str, headers: Mapping[str, str], body: bytes, timeout: int) -> dict[str, Any]:
    with urlopen(Request(url, data=body, headers=dict(headers), method="POST"), timeout=timeout) as response:  # nosec B310
        decoded = json.loads(response.read().decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("provider response must be an object")
    return decoded


class M18SharedProviderClient:
    """One logical call with at most three approved transport attempts."""

    def __init__(self, configuration: M18SharedProviderConfiguration = M18SharedProviderConfiguration(), *,
                 http_post: HttpPost = _post_json, environment: Mapping[str, str] | None = None,
                 sleeper: Callable[[float], None] = time.sleep, clock_ns: Callable[[], int] = time.monotonic_ns) -> None:
        self.configuration = configuration
        self._post, self._environment, self._sleeper, self._clock = http_post, (os.environ if environment is None else environment), sleeper, clock_ns
        self.logical_provider_calls = 0
        self.transport_attempts = 0
        self.responses: list[M18ProviderResponse] = []

    def generate(self, prompt: str, public_request: Mapping[str, Any]) -> M18ProviderResponse:
        if not isinstance(prompt, str) or not prompt.strip() or not isinstance(public_request, Mapping):
            raise TypeError("prompt and public_request are required")
        key = self._environment.get("DEEPSEEK_API_KEY")
        self.logical_provider_calls += 1
        logical_id = self.logical_provider_calls
        if not isinstance(key, str) or not key:
            raise M18ProviderTransportError("missing_deepseek_api_key", 0, logical_id)
        body = {"model": self.configuration.requested_model,
                "messages": [{"role": "user", "content": prompt + "\n\nPublic request:\n" + _canonical(dict(public_request))}],
                "temperature": self.configuration.temperature, "top_p": self.configuration.top_p,
                "max_tokens": self.configuration.max_output_tokens, "stream": self.configuration.stream,
                "response_format": dict(self.configuration.response_format), "thinking": dict(self.configuration.thinking)}
        encoded = _canonical(body).encode("utf-8")
        started = self._clock()
        attempts = 0
        for attempt in range(1, self.configuration.transport_retry.max_attempts + 1):
            attempts = attempt
            self.transport_attempts += 1
            try:
                response = self._post(M18_DEEPSEEK_ENDPOINT, {"Content-Type": "application/json", "Authorization": "Bearer " + key}, encoded, self.configuration.timeout_seconds_per_transport_attempt)
                result = self._decode(response, attempt, logical_id, started)
                self.responses.append(result)
                return result
            except HTTPError as error:
                category = "http_" + str(error.code)
            except TimeoutError:
                category = "read_timeout"
            except URLError as error:
                category = "dns_temporary_failure" if "name" in str(error.reason).lower() else "connection_reset_or_eof"
            except (ConnectionError, OSError):
                category = "connection_reset_or_eof"
            except (ValueError, json.JSONDecodeError):
                category = "malformed_json"
            if category not in self.configuration.transport_retry.retryable or attempt == self.configuration.transport_retry.max_attempts:
                raise M18ProviderTransportError(category, attempts, logical_id)
            self._sleeper(self.configuration.transport_retry.backoff_seconds[attempt - 1])
        raise M18ProviderTransportError("retry_exhausted", attempts, logical_id)

    def _decode(self, response: Mapping[str, Any], attempts: int, logical_id: int, started: int) -> M18ProviderResponse:
        try:
            choice = response["choices"][0]
            message = choice["message"]
            content = message["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("completed response lacks content") from error
        if not isinstance(content, str) or not content.strip():
            raise ValueError("completed response has empty content")
        usage = response.get("usage") if isinstance(response.get("usage"), Mapping) else {}
        details = usage.get("prompt_tokens_details") if isinstance(usage.get("prompt_tokens_details"), Mapping) else {}
        returned = response.get("model") if isinstance(response.get("model"), str) else None
        if returned is not None and returned != self.configuration.requested_model:
            raise M18ProviderTransportError("model_identity_mismatch", attempts, logical_id)
        return M18ProviderResponse(self.configuration.requested_model, returned, content,
            choice.get("finish_reason") if isinstance(choice.get("finish_reason"), str) else None,
            _count(usage.get("prompt_tokens")), _count(usage.get("completion_tokens")), _count(usage.get("total_tokens")),
            _count(details.get("cached_tokens")), attempts, logical_id, "success",
            max(0, (self._clock() - started) // 1_000_000))


class M18SharedMINDProvider:
    def __init__(self, client: M18SharedProviderClient) -> None: self.client = client
    def generate(self, request: Any) -> str: return self.client.generate(request.prompt, request.to_dict()).content


class M18SharedDirectProvider:
    def __init__(self, client: M18SharedProviderClient) -> None: self.client = client
    def generate(self, request: Any) -> str: return self.client.generate(request.prompt, request.to_dict()).content


class M18SharedReActProvider:
    def __init__(self, client: M18SharedProviderClient) -> None: self.client = client
    def generate(self, request: Any) -> str: return self.client.generate(request.prompt, request.to_dict()).content


class M18SharedPlanProvider:
    def __init__(self, client: M18SharedProviderClient) -> None: self.client = client
    def plan(self, request: Any) -> str: return self.client.generate(request.prompt, request.to_dict()).content
    def execute(self, request: Any) -> str: return self.client.generate(request.prompt, request.to_dict()).content
