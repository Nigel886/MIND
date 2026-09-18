"""Provider-free regression tests for the M18 Plan JSON-contract repair."""
from __future__ import annotations

import json
import unittest

from src.core.task import Goal, Task
from src.core.tool import CapabilityDescriptor
from src.evaluation.contracts import EvaluationCase, EvaluationFeedback, EvaluationFeedbackType
from src.evaluation.execution import AgentStepInput, EvaluationBudget, EvaluationBudgetState
from src.evaluation.m18_direct_tool_calling import M18_DIRECT_PROMPT
from src.evaluation.m18_execution_harness import M18RunSpec, M18SharedExecutionHarness, M18_SYSTEM_ARTIFACTS, plan_adapter
from src.evaluation.m18_mind_policy_condition import M18_POLICY_PROMPT
from src.evaluation.m18_plan_and_execute import (
    M18_EXECUTOR_PROMPT,
    M18_PLAN_EXECUTE_ID,
    M18_PLAN_SCHEMA,
    M18_PLANNER_PROMPT,
    M18PlanAndExecuteBaseline,
    m18_plan_artifacts,
)
from src.evaluation.m18_react import M18_REACT_PROMPT
from src.evaluation.m18_shared_provider import M18ProviderTransportError, M18SharedPlanProvider, M18SharedProviderClient, M18SharedProviderConfiguration
from src.evaluation.m18_task_generation import M18Cohort, M18Difficulty, M18Namespace, generate_m18_case


HASH = "0f251e14722603e6e39416374467a3598cd72e1d28673e60daf8440dd6115ee2"


class CapturePlanProvider:
    def __init__(self) -> None:
        self.requests = []

    def plan(self, request):
        self.requests.append(request)
        return '{"steps":[{"step_id":"finish","subgoal":"return","capability_id":null}]}'

    def execute(self, request):
        return '{"action":"answer","answer":7}'


class FailingPlanProvider:
    def __init__(self, category: str) -> None:
        self.category = category

    def plan(self, request):
        raise M18ProviderTransportError(self.category, 1, 1)

    def execute(self, request):
        raise AssertionError("executor must not be reached")


class InvalidPlanProvider:
    def plan(self, request):
        return "not-json"

    def execute(self, request):
        raise AssertionError("executor must not be reached")


def step_input() -> tuple[tuple[CapabilityDescriptor, ...], AgentStepInput]:
    capabilities = (CapabilityDescriptor("synthetic_tool", "Synthetic tool", "Synthetic public tool.", {"type": "object"}),)
    task = Task(Goal("complete synthetic task", ("return a synthetic value",)), {"synthetic_marker": "plan_contract_repair"})
    step = AgentStepInput(EvaluationCase("m18.plan.contract-repair.synthetic", task), EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT), EvaluationBudgetState(EvaluationBudget(3, 1)))
    return capabilities, step


class PlanProviderContractRepairTests(unittest.TestCase):
    def test_repaired_planner_prompt_explicitly_requires_json_without_schema_change(self):
        self.assertIn("JSON object", M18_PLANNER_PROMPT)
        self.assertEqual(set(M18_PLAN_SCHEMA), {"type", "additionalProperties", "required", "properties"})
        self.assertEqual(M18_PLAN_SCHEMA["required"], ["steps"])
        self.assertEqual(M18_PLAN_SCHEMA["properties"]["steps"]["items"]["required"], ["step_id", "subgoal", "capability_id"])

    def test_real_plan_request_builder_uses_repaired_prompt_and_existing_executor_contract(self):
        capabilities, step = step_input()
        provider = CapturePlanProvider()
        M18PlanAndExecuteBaseline(provider, capabilities).step(step)
        self.assertEqual(provider.requests[0].prompt, M18_PLANNER_PROMPT)
        self.assertEqual(provider.requests[0].to_dict()["response_schema"], M18_PLAN_SCHEMA)
        self.assertEqual(M18_EXECUTOR_PROMPT, "Select exactly one next action using the supplied public task, explicit plan, cursor, current public feedback, tools, and budget. Return only strict action JSON; no reasoning, rationale, plan, confidence, or extra fields.")

    def test_shared_client_keeps_frozen_configuration_and_json_object_response_format(self):
        bodies, responses = [], [
            {"model": "deepseek-flash", "choices": [{"message": {"content": '{"steps":[{"step_id":"finish","subgoal":"return","capability_id":null}]}'}}]},
            {"model": "deepseek-flash", "choices": [{"message": {"content": '{"action":"answer","answer":7}'}}]},
        ]
        def post(url, headers, body, timeout):
            bodies.append(json.loads(body)); return responses.pop(0)
        capabilities, step = step_input()
        client = M18SharedProviderClient(http_post=post, environment={"DEEPSEEK_API_KEY": "test-only"})
        M18PlanAndExecuteBaseline(M18SharedPlanProvider(client), capabilities).step(step)
        self.assertEqual(client.configuration.config_hash, HASH)
        self.assertTrue(all(body["response_format"] == {"type": "json_object"} for body in bodies))
        self.assertTrue(all(body["model"] == "deepseek-flash" for body in bodies))
        self.assertIn("JSON object", bodies[0]["messages"][0]["content"])

    def test_other_system_prompts_and_plan_executor_remain_unchanged(self):
        self.assertIn("JSON", M18_POLICY_PROMPT)
        self.assertIn("JSON", M18_DIRECT_PROMPT)
        self.assertIn("JSON", M18_REACT_PROMPT)
        self.assertEqual(M18_EXECUTOR_PROMPT, "Select exactly one next action using the supplied public task, explicit plan, cursor, current public feedback, tools, and budget. Return only strict action JSON; no reasoning, rationale, plan, confidence, or extra fields.")

    def test_transport_categories_survive_plan_wrapper_and_harness_record(self):
        case = generate_m18_case(M18Cohort.B, M18Difficulty.EASY, 990125, M18Namespace.PILOT, 0)
        for category in ("http_400", "read_timeout", "connection_reset_or_eof", "malformed_json"):
            with self.subTest(category=category):
                record = M18SharedExecutionHarness(HASH).run_synthetic(M18RunSpec("m18_suite_v1", case.case_id, "plan_and_execute", 1, HASH), case, plan_adapter(FailingPlanProvider(category)))
                self.assertEqual(record.runtime_terminal_outcome, "provider_failure")
                self.assertEqual(record.raw_artifact_references, ("m18_plan_provider:" + category,))

    def test_planner_decoder_rejection_is_bounded_and_secret_free(self):
        case = generate_m18_case(M18Cohort.B, M18Difficulty.EASY, 990126, M18Namespace.PILOT, 0)
        record = M18SharedExecutionHarness(HASH).run_synthetic(M18RunSpec("m18_suite_v1", case.case_id, "plan_and_execute", 1, HASH), case, plan_adapter(InvalidPlanProvider()))
        self.assertEqual(record.runtime_terminal_outcome, "agent_internal_failure")
        self.assertEqual(record.raw_artifact_references, ("m18_plan_decoder:planner_decoder_rejection",))
        self.assertNotIn("test-only", json.dumps(record.to_dict()))

    def test_repaired_condition_identity_is_distinct_from_historical_plan_identity(self):
        self.assertEqual(M18_PLAN_EXECUTE_ID, "m18_plan_provider_contract_repair_v1")
        self.assertEqual(M18_SYSTEM_ARTIFACTS["plan_and_execute"], m18_plan_artifacts().implementation_hash)
        self.assertNotEqual(M18_SYSTEM_ARTIFACTS["plan_and_execute"], "0c0decad89793d2b8b1b9d943febd23b9b377759")


if __name__ == "__main__":
    unittest.main()
