"""Local contract tests for strict DeepSeek M13 schema transmission."""
from __future__ import annotations

import json
from urllib.error import HTTPError
import unittest

from src.core.task import Goal, Task
from src.core.task_interpretation import CapabilitySnapshot, TaskInterpretationProposal
from src.core.task_validation import ValidatedRequirement, validate_proposal
from src.evaluation.deepseek_transport import DeepSeekRestTransport
from src.evaluation.m16_gemini_assets import load_schema, read_prompt
from src.integration.deepseek_m13_provider import DeepSeekM13InterpretationProvider
from src.integration.llm_provider import ProviderFailure, ProviderFailureCategory
from src.integration.task_interpreter import TaskInterpreter


class _Post:
    def __init__(self, response: dict): self.response, self.calls = response, []
    def __call__(self, url, headers, body, timeout):
        self.calls.append(json.loads(body)); return self.response


def _task() -> Task:
    return Task(Goal("synthetic direct task", ("interpret",)), {"text": "invented development-only text"})


_DEFAULT_CONTENT = object()


def _envelope(payload: dict, *, content: object = _DEFAULT_CONTENT, message: object | None = None) -> dict:
    body = {"model": "deepseek-flash", "choices": [{"message": {"content": json.dumps(payload) if content is _DEFAULT_CONTENT else content}}]}
    if message is not None: body["choices"] = [{"message": message}]
    return body


class DeepSeekM13SchemaAdapterTests(unittest.TestCase):
    def _provider(self, response: dict, post: _Post | None = None) -> tuple[DeepSeekM13InterpretationProvider, _Post]:
        post = _Post(response) if post is None else post
        transport = DeepSeekRestTransport(http_post=post, environment={"DEEPSEEK_API_KEY": "development"}, sleeper=lambda _: None)
        return DeepSeekM13InterpretationProvider(transport, ("calculator",)), post

    def test_request_contains_exact_canonical_schema_deterministically(self) -> None:
        payload = {"intent": "direct", "required_capabilities": [], "constraints": {}, "evidence": {"source": "llm_interpretation"}}
        provider, post = self._provider(_envelope(payload))
        provider.interpret(_task()); provider.interpret(_task())
        self.assertEqual(post.calls[0], post.calls[1])
        content = post.calls[0]["messages"][0]["content"]
        request = json.loads(content[len(f"{read_prompt('m16_mind_interpretation_v1.txt')}\n"):])
        self.assertEqual(load_schema("m16_mind_interpretation_v1.json"), request["response_schema"])
        self.assertEqual(["intent", "required_capabilities", "constraints", "evidence"], request["response_schema"]["required"])

    def test_canonical_payload_decodes_and_validates(self) -> None:
        payload = {"intent": "calculate", "required_capabilities": ["calculator"], "constraints": {}, "evidence": {"source": "llm_interpretation"}}
        provider, _ = self._provider(_envelope(payload))
        proposal = TaskInterpreter(provider).interpret(_task())
        self.assertIsInstance(proposal, TaskInterpretationProposal)
        snapshot = CapabilitySnapshot((("calculator_strategy", ("calculator",)),))
        self.assertIsInstance(validate_proposal(proposal, snapshot), ValidatedRequirement)

    def test_noncanonical_and_missing_required_shapes_remain_rejected(self) -> None:
        for payload in (
            {"type": "direct", "capability": "calculator", "constraints": {}, "evidence": {"source": "llm_interpretation"}},
            {"intent": "direct", "constraints": {}, "evidence": {"source": "llm_interpretation"}},
            {"intent": "direct", "required_capabilities": [], "constraints": {}, "evidence": {"source": "llm_interpretation"}, "goal": {}},
        ):
            provider, _ = self._provider(_envelope(payload))
            result = provider.interpret(_task())
            self.assertIsInstance(result, ProviderFailure)
            self.assertEqual(ProviderFailureCategory.INVALID_OUTPUT_FORMAT, result.category)

    def test_transport_malformed_null_empty_and_missing_content_remain_failures(self) -> None:
        cases = (
            _envelope({}, content="not json"),
            _envelope({}, content=None),
            _envelope({}, content=""),
            {"model": "deepseek-flash", "choices": [{}]},
            {"model": "deepseek-flash", "choices": []},
        )
        for response in cases:
            provider, _ = self._provider(response)
            result = provider.interpret(_task())
            self.assertIsInstance(result, ProviderFailure)
            self.assertEqual(ProviderFailureCategory.MALFORMED_RESPONSE, result.category)

    def test_reasoning_field_is_not_structured_content_and_http_error_is_safe(self) -> None:
        payload = {"intent": "direct", "required_capabilities": [], "constraints": {}, "evidence": {"source": "llm_interpretation"}}
        response = _envelope(payload); response["choices"][0]["message"]["reasoning_content"] = "private"
        provider, _ = self._provider(response)
        self.assertIsInstance(TaskInterpreter(provider).interpret(_task()), TaskInterpretationProposal)
        def error_post(*_): raise HTTPError("https://api.deepseek.com", 400, "bad request", None, None)
        failing = DeepSeekM13InterpretationProvider(DeepSeekRestTransport(http_post=error_post, environment={"DEEPSEEK_API_KEY": "development"}), ("calculator",))
        result = failing.interpret(_task())
        self.assertIsInstance(result, ProviderFailure)


if __name__ == "__main__": unittest.main()
