"""Development-only tests for frozen M16 Gemini provider boundaries."""

from __future__ import annotations

from hashlib import sha256
import inspect
import json
from pathlib import Path
import unittest
from urllib.error import HTTPError

from src.core.task import Goal, Task
from src.evaluation.contracts import EvaluationFeedback, EvaluationFeedbackType
from src.evaluation.direct_tool_calling import (
    DirectActionProviderFailure,
    DirectActionProviderFailureCategory,
    DirectActionProviderResponse,
    DirectActionRequest,
)
from src.evaluation.execution import EvaluationBudget, EvaluationBudgetState
from src.evaluation.gemini_direct_action_provider import GeminiDirectActionProvider
from src.evaluation.gemini_transport import (
    GEMINI_ENDPOINT,
    GEMINI_MODEL,
    GeminiGenerationConfig,
    GeminiRestTransport,
    GeminiTransportFailure,
    GeminiTransportFailureCategory,
    GeminiTransportSuccess,
)
from src.evaluation.m16_gemini_assets import prompt_hash, schema_hash
from src.integration.gemini_m13_provider import GeminiM13InterpretationProvider
from src.integration.llm_provider import ProviderFailure, ProviderResponse
from src.integration.task_interpreter import TaskInterpreter


ROOT = Path(__file__).resolve().parents[1]


def _response(payload: dict, usage: dict | None = None) -> dict:
    return {
        "candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}],
        "usageMetadata": usage or {
            "promptTokenCount": 11,
            "candidatesTokenCount": 7,
            "totalTokenCount": 23,
            "thoughtsTokenCount": 5,
        },
        "modelVersion": GEMINI_MODEL,
        "responseId": "development-only-id",
    }


class _QueuePost:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls: list[tuple[str, dict[str, str], bytes, int]] = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, dict(headers), body, timeout))
        result = self.outcomes.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _transport(outcomes: list[object], *, environment: dict[str, str] | None = None):
    queue = _QueuePost(outcomes)
    sleeps: list[float] = []
    ticks = iter((0, 9_000_000, 10_000_000, 19_000_000))
    return GeminiRestTransport(
        http_post=queue,
        environment={"GEMINI_API_KEY": "development-key"} if environment is None else environment,
        sleeper=sleeps.append,
        clock_ns=lambda: next(ticks),
    ), queue, sleeps


class GeminiTransportTests(unittest.TestCase):
    def test_frozen_configuration_and_missing_credential_failure(self) -> None:
        config = GeminiGenerationConfig()
        self.assertEqual(config.model, "gemini-2.5-flash")
        self.assertEqual((config.temperature, config.top_p, config.candidate_count), (0, 1, 1))
        self.assertEqual((config.seed, config.max_output_tokens, config.max_attempts), (16001, 512, 3))
        transport, _, _ = _transport([], environment={})
        result = transport.generate("Return status ok.", {"type": "object"})
        self.assertIsInstance(result, GeminiTransportFailure)
        self.assertEqual(result.category, GeminiTransportFailureCategory.CONFIGURATION)
        self.assertEqual(result.observation.to_dict()["request_attempts"], 0)
        self.assertNotIn("development-key", json.dumps(result.to_dict() if hasattr(result, "to_dict") else {"reason": result.reason}))

    def test_success_maps_usage_and_uses_frozen_rest_structured_request(self) -> None:
        transport, queue, _ = _transport([_response({"status": "ok"}, {
            "promptTokenCount": 3, "candidatesTokenCount": 2, "totalTokenCount": 9,
            "thoughtsTokenCount": 4,
        })])
        result = transport.generate("Return status ok.", {"type": "object"})
        self.assertIsInstance(result, GeminiTransportSuccess)
        self.assertEqual(result.payload, {"status": "ok"})
        self.assertEqual(result.observation.to_dict(), {
            "request_attempts": 1, "successful_requests": 1, "model_calls": 1,
            "prompt_tokens": 3, "output_tokens": 2, "total_tokens": 9,
            "thinking_tokens": 4, "cached_tokens": None, "latency_ms": 9,
            "model_version": GEMINI_MODEL, "provider_request_id": "development-only-id",
        })
        url, headers, body, timeout = queue.calls[0]
        self.assertEqual((url, timeout), (GEMINI_ENDPOINT, 30))
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertNotIn(headers["x-goog-api-key"], body.decode("utf-8"))
        request = json.loads(body)
        self.assertEqual(request["generationConfig"], {
            "responseMimeType": "application/json", "responseJsonSchema": {"type": "object"},
            "temperature": 0, "topP": 1, "candidateCount": 1,
            "seed": 16001, "maxOutputTokens": 512,
        })

    def test_transient_503_retries_once_then_success(self) -> None:
        error = HTTPError(GEMINI_ENDPOINT, 503, "unavailable", {}, None)
        transport, queue, sleeps = _transport([error, _response({"status": "ok"})])
        result = transport.generate("Return status ok.", {"type": "object"})
        self.assertIsInstance(result, GeminiTransportSuccess)
        self.assertEqual(result.observation.request_attempts, 2)
        self.assertEqual(result.observation.model_calls, 1)
        self.assertEqual(len(queue.calls), 2)
        self.assertEqual(sleeps, [1.0])

    def test_malformed_completed_output_is_not_retried(self) -> None:
        transport, queue, sleeps = _transport([_response({"unexpected": True})])
        result = transport.generate("Return status ok.", {"type": "object"})
        self.assertIsInstance(result, GeminiTransportSuccess)
        self.assertEqual(len(queue.calls), 1)
        self.assertEqual(sleeps, [])


class GeminiAdapterTests(unittest.TestCase):
    def test_mind_provider_returns_raw_interpretation_only_and_preserves_m13_parser_boundary(self) -> None:
        interpretation = _response({
            "intent": "classify", "required_capabilities": [], "constraints": {},
            "evidence": {"source": "llm_interpretation"},
        })
        transport, _, _ = _transport([interpretation, interpretation])
        observations = []
        provider = GeminiM13InterpretationProvider(transport, observation_sink=observations.append)
        task = Task(Goal("return", ("done",)), {"value": "development"})
        result = provider.interpret(task)
        self.assertIsInstance(result, ProviderResponse)
        proposal = TaskInterpreter(provider).interpret(task)
        self.assertEqual(proposal.to_dict()["intent"], "classify")
        self.assertEqual(len(observations), 2)
        source = inspect.getsource(GeminiM13InterpretationProvider)
        self.assertNotIn("EvaluationAction", source)
        self.assertNotIn("ToolRegistry", source)

    def test_mind_provider_rejects_private_truth_before_transport(self) -> None:
        transport, queue, _ = _transport([])
        provider = GeminiM13InterpretationProvider(transport)
        task = Task(Goal("return", ("done",)), {"value": "development", "expected_answer": "private"})
        with self.assertRaises(ValueError):
            provider.interpret(task)
        self.assertEqual(queue.calls, [])

    def test_direct_provider_maps_answer_and_tool_call_without_execution(self) -> None:
        response = _response({"action_type": "answer", "payload": {"answer": "development"}})
        transport, _, _ = _transport([response])
        provider = GeminiDirectActionProvider(transport)
        request = DirectActionRequest(
            task=Task(Goal("return", ("done",)), {"value": "development"}).to_dict(),
            latest_feedback=EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT),
            budget_state=EvaluationBudgetState(EvaluationBudget(2, 1)),
            tool_schemas={"calculator": {"type": "object"}},
            provider_configuration_id="m16.gemini.flash.v1",
        )
        result = provider.decide(request)
        self.assertIsInstance(result, DirectActionProviderResponse)
        self.assertEqual(result.to_dict()["action_type"], "answer")
        self.assertEqual(result.to_dict()["resource_metadata"]["model_calls"], 1)
        tool_transport, _, _ = _transport([_response({"action_type": "tool_call", "payload": {
            "tool_name": "calculator", "parameters": {"operation": "add", "operands": [1, 2]},
        }})])
        tool_result = GeminiDirectActionProvider(tool_transport).decide(request)
        self.assertIsInstance(tool_result, DirectActionProviderResponse)
        self.assertEqual(tool_result.to_dict()["action_type"], "tool_call")
        source = inspect.getsource(GeminiDirectActionProvider)
        self.assertNotIn("ToolRegistry", source)
        self.assertNotIn("ActionExecutor", source)

    def test_direct_provider_maps_invalid_output_without_retry(self) -> None:
        transport, _, _ = _transport([_response({"action_type": "unknown", "payload": {}})])
        request = DirectActionRequest(
            task=Task(Goal("return", ("done",)), {"value": "development"}).to_dict(),
            latest_feedback=EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT),
            budget_state=EvaluationBudgetState(EvaluationBudget(2, 1)), tool_schemas={},
            provider_configuration_id="m16.gemini.flash.v1",
        )
        result = GeminiDirectActionProvider(transport).decide(request)
        self.assertIsInstance(result, DirectActionProviderFailure)
        self.assertEqual(result.category, DirectActionProviderFailureCategory.MALFORMED_RESPONSE)


class GeminiArtifactTests(unittest.TestCase):
    def test_frozen_artifact_hashes_match_manifest_and_prompts_are_lf_stable(self) -> None:
        manifest = json.loads((ROOT / "evaluation/config/m16_gemini_flash_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(prompt_hash("m16_mind_interpretation_v1.txt"), manifest["MIND"]["prompt_hash"])
        self.assertEqual(prompt_hash("m16_direct_action_v1.txt"), manifest["Direct"]["prompt_hash"])
        self.assertEqual(schema_hash("m16_mind_interpretation_v1.json"), manifest["MIND"]["schema_hash"])
        self.assertEqual(schema_hash("m16_direct_action_v1.json"), manifest["Direct"]["schema_hash"])
        self.assertEqual(schema_hash("m16_calculator_tool_v1.json"), manifest["tool"]["tool_schema_hash"])
        for name in ("m16_mind_interpretation_v1.txt", "m16_direct_action_v1.txt"):
            data = (ROOT / "evaluation/prompts" / name).read_bytes()
            self.assertNotIn(b"\r", data)
            self.assertTrue(data.endswith(b"\n"))
        self.assertEqual(manifest["suite"]["hash"], "a450c6fa2955136da5d4db08b892af442ab7be66034412739d91e7cbf076445c")
        self.assertEqual(manifest["split_hash"], "a41ca5a326da4f722de1fcca4c7a4b85fcf860767ba1bb0311aa6cc4176aefe3")

    def test_provider_test_source_never_imports_formal_held_out_module(self) -> None:
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertNotIn("m16_cohort_a_held" + "_out", source)


if __name__ == "__main__":
    unittest.main()
