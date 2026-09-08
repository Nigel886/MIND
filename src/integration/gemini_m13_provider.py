"""Gemini-backed M13 interpretation provider without execution authority."""

from __future__ import annotations

import json
from typing import Callable, Iterable

from src.core.task import Task
from src.evaluation.gemini_transport import (
    GeminiRestTransport,
    GeminiTransportFailure,
    GeminiTransportFailureCategory,
    GeminiTransportSuccess,
)
from src.evaluation.m16_gemini_assets import (
    MIND_PROMPT_ID,
    load_schema,
    read_prompt,
)
from src.evaluation.provider_observation import ProviderCallObservation
from src.integration.llm_provider import ProviderFailure, ProviderFailureCategory, ProviderResponse


def _public_task_view(task: Task) -> dict:
    data = task.to_dict()
    data.pop("id")
    _reject_private_keys(data)
    return data


def _reject_private_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"expected_answer", "private_truth", "completion_context"}:
                raise ValueError("provider input must not contain evaluator-private data")
            _reject_private_keys(item)
    elif isinstance(value, list):
        for item in value:
            _reject_private_keys(item)


class GeminiM13InterpretationProvider:
    """Maps one public Task to raw interpretation JSON, never actions or tools."""

    prompt_id = MIND_PROMPT_ID

    def __init__(
        self,
        transport: GeminiRestTransport,
        capability_vocabulary: Iterable[str] = ("calculator",),
        observation_sink: Callable[[ProviderCallObservation], None] | None = None,
    ) -> None:
        if not isinstance(transport, GeminiRestTransport):
            raise TypeError("transport must be a GeminiRestTransport")
        vocabulary = tuple(capability_vocabulary)
        if not vocabulary or any(not isinstance(value, str) or not value.strip() for value in vocabulary):
            raise ValueError("capability_vocabulary must contain non-empty strings")
        if len(set(vocabulary)) != len(vocabulary):
            raise ValueError("capability_vocabulary must not contain duplicates")
        self._transport = transport
        self._vocabulary = vocabulary
        self._observation_sink = observation_sink

    def interpret(self, task: Task) -> ProviderResponse | ProviderFailure:
        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        request = json.dumps(
            {"public_task": _public_task_view(task), "capability_vocabulary": list(self._vocabulary)},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        )
        result = self._transport.generate(
            f"{read_prompt('m16_mind_interpretation_v1.txt')}\n{request}",
            load_schema("m16_mind_interpretation_v1.json"),
        )
        self._emit(result)
        if isinstance(result, GeminiTransportSuccess):
            return ProviderResponse(result.payload)
        return ProviderFailure(_provider_category(result.category), {"reason": result.reason})

    def _emit(self, result: GeminiTransportSuccess | GeminiTransportFailure) -> None:
        if self._observation_sink is not None:
            self._observation_sink(result.observation)


def _provider_category(category: GeminiTransportFailureCategory) -> ProviderFailureCategory:
    if category is GeminiTransportFailureCategory.TIMEOUT:
        return ProviderFailureCategory.TIMEOUT
    if category is GeminiTransportFailureCategory.MALFORMED_RESPONSE:
        return ProviderFailureCategory.MALFORMED_RESPONSE
    if category is GeminiTransportFailureCategory.CONFIGURATION:
        return ProviderFailureCategory.UNAVAILABLE
    return ProviderFailureCategory.UNAVAILABLE
