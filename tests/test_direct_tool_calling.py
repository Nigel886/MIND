"""Unit tests for the isolated M16 Direct Tool-Calling baseline."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import inspect
import unittest

from src.core.task import Goal, Task
from src.evaluation.contracts import (
    EvaluationActionType,
    EvaluationCase,
    EvaluationFeedback,
    EvaluationFeedbackType,
)
from src.evaluation.direct_tool_calling import (
    CohortAEligibilityDecision,
    DirectActionProvider,
    DirectActionProviderFailure,
    DirectActionProviderFailureCategory,
    DirectActionProviderResponse,
    DirectActionResourceMetadata,
    DirectToolCallingEvaluationAgent,
    FakeDirectActionProvider,
    assess_cohort_a_eligibility,
)
from src.evaluation.execution import AgentStepInput, EvaluationBudget, EvaluationBudgetState


def _case(metadata: dict | None = None) -> EvaluationCase:
    return EvaluationCase(
        "m16.direct.001",
        Task(Goal("return value", ("ready",)), {"value": "ready"}, metadata=metadata or {}),
    )


def _step(case: EvaluationCase, feedback: EvaluationFeedback) -> AgentStepInput:
    return AgentStepInput(case, feedback, EvaluationBudgetState(EvaluationBudget(2, 1)))


class DirectToolCallingTests(unittest.TestCase):
    def test_direct_answer_maps_to_existing_action(self) -> None:
        provider = FakeDirectActionProvider({
            EvaluationFeedbackType.INITIAL_INPUT: DirectActionProviderResponse(
                EvaluationActionType.ANSWER, {"answer": "ready"}
            )
        })
        agent = DirectToolCallingEvaluationAgent(provider, {}, "fake-v1")

        result = agent.step(_step(_case(), EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))

        self.assertIsInstance(provider, DirectActionProvider)
        self.assertEqual(result.action.action_type, EvaluationActionType.ANSWER)
        self.assertEqual(result.action.to_dict()["payload"], {"answer": "ready"})
        self.assertTrue(result.request_termination)

    def test_tool_call_then_latest_feedback_answer_is_stateless(self) -> None:
        provider = FakeDirectActionProvider({
            EvaluationFeedbackType.INITIAL_INPUT: DirectActionProviderResponse(
                EvaluationActionType.TOOL_CALL,
                {"tool_name": "calculator", "parameters": {"operation": "multiply", "operands": [17, 23]}},
            ),
            EvaluationFeedbackType.TOOL_RESPONSE: DirectActionProviderResponse(
                EvaluationActionType.ANSWER, {"answer": 391}
            ),
        })
        agent = DirectToolCallingEvaluationAgent(provider, {"calculator": {"type": "object"}}, "fake-v1")
        case = _case()

        first = agent.step(_step(case, EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
        second = agent.step(_step(case, EvaluationFeedback(
            EvaluationFeedbackType.TOOL_RESPONSE, {"response": {"output": 391}}
        )))

        self.assertEqual(first.action.action_type, EvaluationActionType.TOOL_CALL)
        self.assertFalse(first.request_termination)
        self.assertEqual(second.action.action_type, EvaluationActionType.ANSWER)
        self.assertEqual(second.action.to_dict()["payload"], {"answer": 391})
        self.assertFalse(any(name in vars(agent) for name in ("_history", "_trace", "_actions", "_feedback")))

    def test_repeated_tool_call_is_representable_but_not_executed(self) -> None:
        response = DirectActionProviderResponse(
            EvaluationActionType.TOOL_CALL, {"tool_name": "calculator", "parameters": {}}
        )
        agent = DirectToolCallingEvaluationAgent(
            FakeDirectActionProvider({
                EvaluationFeedbackType.INITIAL_INPUT: response,
                EvaluationFeedbackType.TOOL_RESPONSE: response,
            }),
            {"calculator": {}},
            "fake-v1",
        )
        case = _case()
        self.assertEqual(
            agent.step(_step(case, EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT))).action.action_type,
            EvaluationActionType.TOOL_CALL,
        )
        self.assertEqual(
            agent.step(_step(case, EvaluationFeedback(EvaluationFeedbackType.TOOL_RESPONSE))).action.action_type,
            EvaluationActionType.TOOL_CALL,
        )
        self.assertNotIn("ToolRegistry", inspect.getsource(DirectToolCallingEvaluationAgent))
        self.assertNotIn("ActionExecutor", inspect.getsource(DirectToolCallingEvaluationAgent))

    def test_fail_and_invalid_responses_map_directly(self) -> None:
        for action_type, reason in ((EvaluationActionType.FAIL, "unsupported_task"), (EvaluationActionType.INVALID, "bad_shape")):
            with self.subTest(action_type=action_type):
                agent = DirectToolCallingEvaluationAgent(
                    FakeDirectActionProvider({
                        EvaluationFeedbackType.INITIAL_INPUT: DirectActionProviderResponse(action_type, {"reason": reason})
                    }), {}, "fake-v1"
                )
                result = agent.step(_step(_case(), EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
                self.assertEqual(result.action.action_type, action_type)
                self.assertEqual(result.action.to_dict()["payload"], {"reason": reason})
                self.assertTrue(result.request_termination)

    def test_all_provider_failures_map_deterministically(self) -> None:
        expected = {
            DirectActionProviderFailureCategory.PROVIDER_UNAVAILABLE: EvaluationActionType.FAIL,
            DirectActionProviderFailureCategory.PROVIDER_TIMEOUT: EvaluationActionType.FAIL,
            DirectActionProviderFailureCategory.MALFORMED_RESPONSE: EvaluationActionType.INVALID,
            DirectActionProviderFailureCategory.UNSUPPORTED_ACTION: EvaluationActionType.INVALID,
        }
        for category, action_type in expected.items():
            with self.subTest(category=category):
                agent = DirectToolCallingEvaluationAgent(
                    FakeDirectActionProvider({
                        EvaluationFeedbackType.INITIAL_INPUT: DirectActionProviderFailure(category)
                    }), {}, "fake-v1"
                )
                result = agent.step(_step(_case(), EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
                self.assertEqual(result.action.action_type, action_type)
                self.assertEqual(result.action.to_dict()["payload"]["reason"], category.value)

    def test_models_are_immutable_serializable_and_resources_are_not_fabricated(self) -> None:
        response = DirectActionProviderResponse(EvaluationActionType.ANSWER, {"answer": [1]}, None)
        self.assertEqual(response, DirectActionProviderResponse.from_dict(response.to_dict()))
        self.assertIsNone(response.resource_metadata)
        actual = DirectActionResourceMetadata(model_calls=1, input_tokens=4, output_tokens=2, latency_ms=7)
        observed = DirectActionProviderResponse(EvaluationActionType.ANSWER, {"answer": "x"}, actual)
        self.assertEqual(observed, DirectActionProviderResponse.from_dict(observed.to_dict()))
        failure = DirectActionProviderFailure(DirectActionProviderFailureCategory.PROVIDER_TIMEOUT)
        self.assertEqual(failure, DirectActionProviderFailure.from_dict(failure.to_dict()))
        with self.assertRaises(FrozenInstanceError):
            observed.action_type = EvaluationActionType.FAIL  # type: ignore[misc]
        with self.assertRaises(TypeError):
            observed.payload["answer"] = "changed"  # type: ignore[index]

    def test_invalid_provider_return_maps_to_invalid_without_exception_control_flow(self) -> None:
        class InvalidProvider:
            def decide(self, request):
                return "bad"

        agent = DirectToolCallingEvaluationAgent(InvalidProvider(), {}, "fake-v1")
        result = agent.step(_step(_case(), EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
        self.assertEqual(result.action.action_type, EvaluationActionType.INVALID)
        self.assertEqual(result.action.to_dict()["payload"], {"reason": "malformed_response"})

    def test_eligibility_is_pre_outcome_and_deterministic(self) -> None:
        eligible = _case({"m16_cohort_a": {
            "task_family": "direct_answer", "tool_call_limit": 0,
            "requires_planning": False, "requires_multi_tool": False,
            "requires_dependent_multistep": False, "requires_recovery": False,
        }})
        ineligible = _case({"m16_cohort_a": {
            "task_family": "controlled_single_tool", "tool_call_limit": 1,
            "requires_planning": False, "requires_multi_tool": False,
            "requires_dependent_multistep": False, "requires_recovery": True,
        }})
        decision = assess_cohort_a_eligibility(eligible)
        self.assertEqual(decision, CohortAEligibilityDecision(True, "eligible"))
        self.assertEqual(decision, CohortAEligibilityDecision.from_dict(decision.to_dict()))
        self.assertEqual(assess_cohort_a_eligibility(ineligible).reason, "requires_recovery")
        self.assertFalse(assess_cohort_a_eligibility(_case()).eligible)

    def test_module_isolated_from_mind_cognitive_components(self) -> None:
        source = inspect.getsource(__import__("src.evaluation.direct_tool_calling", fromlist=["*"]))
        for forbidden in (
            "GoalDirectedAgent", "RuntimeController", "RuntimeState", "Belief",
            "InferenceEngine", "MetaInferenceEngine", "CognitiveAgentSession",
            "CognitiveExecutionLoopController", "TaskInterpreter", "LLMProvider",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
