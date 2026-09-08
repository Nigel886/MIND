"""Gemini-backed one-action Direct provider with evaluator-owned tool execution."""

from __future__ import annotations

import json
from typing import Callable

from src.evaluation.direct_tool_calling import (
    DirectActionProviderFailure,
    DirectActionProviderFailureCategory,
    DirectActionProviderResponse,
    DirectActionRequest,
    DirectActionResourceMetadata,
)
from src.evaluation.gemini_transport import (
    GeminiRestTransport,
    GeminiTransportFailure,
    GeminiTransportFailureCategory,
    GeminiTransportSuccess,
)
from src.evaluation.m16_gemini_assets import (
    DIRECT_PROMPT_ID,
    load_schema,
    read_prompt,
)
from src.evaluation.provider_observation import ProviderCallObservation
from src.evaluation.contracts import EvaluationActionType


def _reject_private_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"expected_answer", "private_truth", "completion_context"}:
                raise ValueError("provider input must not contain evaluator-private data")
            _reject_private_keys(item)
    elif isinstance(value, list):
        for item in value:
            _reject_private_keys(item)


class GeminiDirectActionProvider:
    """Maps one public Direct request to one action; it never executes a tool."""

    prompt_id = DIRECT_PROMPT_ID

    def __init__(
        self,
        transport: GeminiRestTransport,
        observation_sink: Callable[[ProviderCallObservation], None] | None = None,
    ) -> None:
        if not isinstance(transport, GeminiRestTransport):
            raise TypeError("transport must be a GeminiRestTransport")
        self._transport = transport
        self._observation_sink = observation_sink

    def decide(self, request: DirectActionRequest) -> DirectActionProviderResponse | DirectActionProviderFailure:
        if not isinstance(request, DirectActionRequest):
            raise TypeError("request must be a DirectActionRequest")
        public_request = request.to_dict()
        public_request["task"].pop("id", None)
        _reject_private_keys(public_request)
        encoded = json.dumps(public_request, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        result = self._transport.generate(
            f"{read_prompt('m16_direct_action_v1.txt')}\n{encoded}",
            load_schema("m16_direct_action_v1.json"),
        )
        self._emit(result)
        if not isinstance(result, GeminiTransportSuccess):
            return DirectActionProviderFailure(_failure_category(result.category), {"reason": result.reason})
        try:
            response = DirectActionProviderResponse(
                EvaluationActionType(result.payload["action_type"]),
                result.payload["payload"],
                DirectActionResourceMetadata(
                    model_calls=result.observation.model_calls,
                    input_tokens=result.observation.prompt_tokens,
                    output_tokens=result.observation.output_tokens,
                    latency_ms=result.observation.latency_ms,
                ),
            )
        except (KeyError, TypeError, ValueError):
            return DirectActionProviderFailure(
                DirectActionProviderFailureCategory.MALFORMED_RESPONSE,
                {"reason": "invalid_direct_action"},
            )
        return response

    def _emit(self, result: GeminiTransportSuccess | GeminiTransportFailure) -> None:
        if self._observation_sink is not None:
            self._observation_sink(result.observation)


def _failure_category(category: GeminiTransportFailureCategory) -> DirectActionProviderFailureCategory:
    if category is GeminiTransportFailureCategory.TIMEOUT:
        return DirectActionProviderFailureCategory.PROVIDER_TIMEOUT
    if category is GeminiTransportFailureCategory.MALFORMED_RESPONSE:
        return DirectActionProviderFailureCategory.MALFORMED_RESPONSE
    return DirectActionProviderFailureCategory.PROVIDER_UNAVAILABLE
