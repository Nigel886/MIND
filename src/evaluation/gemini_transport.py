"""Narrow Gemini REST transport for evaluation-side structured provider calls."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import os
import time
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.evaluation.provider_observation import ProviderCallObservation


GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)


class GeminiTransportFailureCategory(str, Enum):
    """Bounded infrastructure and response failures owned by the transport."""

    CONFIGURATION = "configuration"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    MALFORMED_RESPONSE = "malformed_response"


@dataclass(frozen=True)
class GeminiGenerationConfig:
    """Frozen common M16 Gemini generation configuration."""

    model: str = GEMINI_MODEL
    temperature: int = 0
    top_p: int = 1
    candidate_count: int = 1
    seed: int = 16001
    max_output_tokens: int = 512
    response_mime_type: str = "application/json"
    max_attempts: int = 3
    timeout_seconds: int = 30

    def __post_init__(self) -> None:
        if self.model != GEMINI_MODEL:
            raise ValueError("model must be gemini-2.5-flash")
        if self.temperature != 0 or self.top_p != 1 or self.candidate_count != 1:
            raise ValueError("M16 Gemini generation settings are frozen")
        if self.seed != 16001 or self.max_output_tokens != 512:
            raise ValueError("M16 Gemini seed and output cap are frozen")
        if self.response_mime_type != "application/json":
            raise ValueError("response_mime_type must be application/json")
        if self.max_attempts != 3 or self.timeout_seconds <= 0:
            raise ValueError("retry and timeout configuration is invalid")


@dataclass(frozen=True)
class GeminiTransportSuccess:
    """Parsed structured output and measured provider observation."""

    payload: dict[str, Any]
    observation: ProviderCallObservation


@dataclass(frozen=True)
class GeminiTransportFailure:
    """Bounded failed transport result without request or credential disclosure."""

    category: GeminiTransportFailureCategory
    observation: ProviderCallObservation
    reason: str


GeminiTransportResult = GeminiTransportSuccess | GeminiTransportFailure
HttpPost = Callable[[str, Mapping[str, str], bytes, int], dict[str, Any]]


def _post_json(url: str, headers: Mapping[str, str], body: bytes, timeout: int) -> dict[str, Any]:
    request = Request(url, data=body, headers=dict(headers), method="POST")
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - frozen HTTPS endpoint
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Gemini response must be an object")
    return data


def _optional_count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


class GeminiRestTransport:
    """Reusable non-Agent Gemini `generateContent` transport with bounded retries."""

    def __init__(
        self,
        configuration: GeminiGenerationConfig = GeminiGenerationConfig(),
        *,
        http_post: HttpPost = _post_json,
        environment: Mapping[str, str] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        if not isinstance(configuration, GeminiGenerationConfig):
            raise TypeError("configuration must be GeminiGenerationConfig")
        self._configuration = configuration
        self._http_post = http_post
        self._environment = os.environ if environment is None else environment
        self._sleeper = sleeper
        self._clock_ns = clock_ns

    @property
    def configuration(self) -> GeminiGenerationConfig:
        return self._configuration

    def generate(self, instruction: str, response_schema: dict[str, Any]) -> GeminiTransportResult:
        """Submit one structured request, retrying infrastructure failures only."""

        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError("instruction must be a non-empty str")
        if not isinstance(response_schema, dict):
            raise TypeError("response_schema must be a dict")
        key = self._environment.get("GEMINI_API_KEY")
        if not isinstance(key, str) or not key:
            return GeminiTransportFailure(
                GeminiTransportFailureCategory.CONFIGURATION,
                ProviderCallObservation(0, 0, 0),
                "missing_gemini_api_key",
            )
        body = {
            "contents": [{"role": "user", "parts": [{"text": instruction}]}],
            "generationConfig": {
                "responseMimeType": self._configuration.response_mime_type,
                "responseJsonSchema": response_schema,
                "temperature": self._configuration.temperature,
                "topP": self._configuration.top_p,
                "candidateCount": self._configuration.candidate_count,
                "seed": self._configuration.seed,
                "maxOutputTokens": self._configuration.max_output_tokens,
            },
        }
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        started = self._clock_ns()
        attempts = 0
        for attempt in range(1, self._configuration.max_attempts + 1):
            attempts += 1
            try:
                response = self._http_post(
                    GEMINI_ENDPOINT,
                    {"Content-Type": "application/json", "x-goog-api-key": key},
                    encoded,
                    self._configuration.timeout_seconds,
                )
                return self._decode_success(response, attempts, started)
            except HTTPError as error:
                status = error.code
            except TimeoutError:
                return self._failure(GeminiTransportFailureCategory.TIMEOUT, attempts, started, "timeout")
            except URLError:
                status = None
            except (OSError, ValueError, json.JSONDecodeError):
                status = None
            if status not in {None, 429, 500, 502, 503, 504}:
                return self._failure(GeminiTransportFailureCategory.UNAVAILABLE, attempts, started, "http_error")
            if attempt < self._configuration.max_attempts:
                self._sleeper(float(2 ** (attempt - 1)))
        return self._failure(GeminiTransportFailureCategory.UNAVAILABLE, attempts, started, "retry_exhausted")

    def _decode_success(
        self, response: dict[str, Any], attempts: int, started: int
    ) -> GeminiTransportResult:
        observation = self._observation(response, attempts, started, 1, 1)
        try:
            candidates = response["candidates"]
            parts = candidates[0]["content"]["parts"]
            visible = [part["text"] for part in parts if isinstance(part, dict) and "text" in part and part.get("thought") is not True]
            if not visible:
                raise ValueError("missing_visible_text")
            payload = json.loads(visible[-1])
            if not isinstance(payload, dict):
                raise ValueError("structured_output_not_object")
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
            return GeminiTransportFailure(
                GeminiTransportFailureCategory.MALFORMED_RESPONSE,
                observation,
                "invalid_structured_response",
            )
        return GeminiTransportSuccess(payload, observation)

    def _failure(
        self, category: GeminiTransportFailureCategory, attempts: int, started: int, reason: str
    ) -> GeminiTransportFailure:
        return GeminiTransportFailure(category, self._observation({}, attempts, started, 0, 0), reason)

    def _observation(
        self, response: Mapping[str, Any], attempts: int, started: int, successes: int, calls: int
    ) -> ProviderCallObservation:
        usage = response.get("usageMetadata")
        usage = usage if isinstance(usage, Mapping) else {}
        elapsed = max(0, (self._clock_ns() - started) // 1_000_000)
        return ProviderCallObservation(
            attempts, successes, calls,
            prompt_tokens=_optional_count(usage.get("promptTokenCount")),
            output_tokens=_optional_count(usage.get("candidatesTokenCount")),
            total_tokens=_optional_count(usage.get("totalTokenCount")),
            thinking_tokens=_optional_count(usage.get("thoughtsTokenCount")),
            cached_tokens=_optional_count(usage.get("cachedContentTokenCount")),
            latency_ms=elapsed,
            model_version=response.get("modelVersion") if isinstance(response.get("modelVersion"), str) else None,
            provider_request_id=response.get("responseId") if isinstance(response.get("responseId"), str) else None,
        )
