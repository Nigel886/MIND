"""Provider-free acceptance tests for Issue #184's corrected contract."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.core.task import Goal, Task
from src.core.tool import CapabilityDescriptor
from src.evaluation.contracts import EvaluationCase, EvaluationFeedback, EvaluationFeedbackType
from src.evaluation.execution import AgentStepInput, EvaluationBudget, EvaluationBudgetState
from src.evaluation.m18_corrected_comparator_contract import (
    M18_CORRECTED_COMPARATOR_CONTRACT_ID, M18CorrectedRunIdentity,
    M18CorrectedProvenance, M18CorrectedRecord, M18CorrectedResultStore,
    M18CorrectedRunnerPlan, corrected_namespace_counts, select_corrected_condition,
)
from src.evaluation.m18_direct_tool_calling import M18_DIRECT_RESPONSE_SCHEMA, M18DirectConditionError, decode_m18_direct_response
from src.evaluation.m18_mind_policy_condition import M18_POLICY_RESPONSE_SCHEMA, M18PolicyConditionError, decode_m18_policy_response
from src.evaluation.m18_plan_and_execute import M18PlanAndExecuteBaseline, M18PlanTerminationReason
from src.evaluation.m18_v3_pilot_runner import validate_m18_v3_namespace_integrity


class _PlanProvider:
    def __init__(self, plan: str, actions: list[str]): self.plan_output, self.actions, self.requests = plan, list(actions), []
    def plan(self, request): return self.plan_output
    def execute(self, request): self.requests.append(request); return self.actions.pop(0)


class CorrectedComparatorContractTests(unittest.TestCase):
    def setUp(self):
        self.case = EvaluationCase("corrected.contract", Task(Goal("complete", ("answer",)), {"value": 1}))
        self.tools = (CapabilityDescriptor("tool", "Tool", "public", {"type": "object"}),)

    def step(self, feedback, used=0):
        return AgentStepInput(self.case, feedback, EvaluationBudgetState(EvaluationBudget(6, 4), used, 0))

    def test_exact_length_plan_reaches_answer_pending_then_answers(self):
        provider = _PlanProvider('{"steps":[{"step_id":"one","subgoal":"tool","capability_id":"tool"}]}', [
            '{"action":"tool_call","tool_name":"tool","parameters":{}}', '{"action":"answer","answer":7}',
        ])
        plan = M18PlanAndExecuteBaseline(provider, self.tools)
        plan.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
        answer = plan.step(self.step(EvaluationFeedback(EvaluationFeedbackType.TOOL_RESPONSE, {"output": 7}), 1))
        self.assertEqual(provider.requests[-1].to_dict()["phase"], "answer_pending")
        self.assertEqual(answer.action.to_dict()["payload"], {"answer": 7})

    def test_plan_exhaustion_requires_a_prior_answer_opportunity(self):
        provider = _PlanProvider('{"steps":[{"step_id":"one","subgoal":"tool","capability_id":"tool"}]}', [
            '{"action":"tool_call","tool_name":"tool","parameters":{}}', '{"action":"tool_call","tool_name":"tool","parameters":{}}',
        ])
        plan = M18PlanAndExecuteBaseline(provider, self.tools)
        plan.step(self.step(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT)))
        pending = plan.step(self.step(EvaluationFeedback(EvaluationFeedbackType.TOOL_RESPONSE), 1))
        self.assertFalse(pending.request_termination)
        exhausted = plan.step(self.step(EvaluationFeedback(EvaluationFeedbackType.TOOL_RESPONSE), 2))
        self.assertEqual(exhausted.action.to_dict()["payload"]["reason"], M18PlanTerminationReason.PLAN_EXHAUSTED.value)

    def test_all_answer_decoders_reject_nonintegers_and_accept_integer(self):
        invalid = ('"7"', '7.0', '{}', '[]', 'null', 'true')
        self.assertEqual(decode_m18_direct_response('{"action":"answer","answer":7}').to_dict()["payload"], {"answer": 7})
        self.assertEqual(decode_m18_policy_response('{"action":"answer","answer":7}').to_dict()["parameters"], {"answer": 7})
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(M18DirectConditionError): decode_m18_direct_response('{"action":"answer","answer":' + value + '}')
                with self.assertRaises(M18PolicyConditionError): decode_m18_policy_response('{"action":"answer","answer":' + value + '}')
        for decoder, error in ((decode_m18_direct_response, M18DirectConditionError), (decode_m18_policy_response, M18PolicyConditionError)):
            with self.subTest(decoder=decoder.__name__), self.assertRaises(error): decoder('{"action":"answer"}')
        self.assertEqual(M18_DIRECT_RESPONSE_SCHEMA["oneOf"][0]["properties"]["answer"], {"type": "integer"})
        self.assertEqual(M18_POLICY_RESPONSE_SCHEMA["oneOf"][0]["properties"]["answer"], {"type": "integer"})

    def test_corrected_ids_and_empty_namespaces_are_isolated(self):
        corrected = M18CorrectedRunIdentity("pilot.case", "plan_and_execute", 1)
        from src.evaluation.m18_v3_provenance import M18V3RunIdentity
        self.assertNotEqual(corrected.run_id, M18V3RunIdentity("pilot.case", "plan_and_execute", 1).run_id)
        self.assertEqual(select_corrected_condition(M18_CORRECTED_COMPARATOR_CONTRACT_ID), M18_CORRECTED_COMPARATOR_CONTRACT_ID)
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(corrected_namespace_counts(Path(directory)), (0, 0))

    def test_v3_tree_rejects_nested_or_rogue_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ("v3/rogue.json", "v3/diagnostic/x.json", "v3/formal/nested/x.json"):
                path = root / "evaluation/m18/results" / relative
                path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps({}))
                with self.assertRaises(Exception): validate_m18_v3_namespace_integrity(root)
                path.unlink()

    def test_corrected_store_admits_only_closed_corrected_provenance(self):
        from src.evaluation.m18_v3_pilot_runner import M18V3PilotPlan
        from src.evaluation.m18_v3_provenance import M18V3RunIdentity
        runner=M18CorrectedRunnerPlan.from_v3_plan(M18V3PilotPlan.from_repository(Path('.')))
        with tempfile.TemporaryDirectory() as directory:
            store=M18CorrectedResultStore(Path(directory)/"pilot",runner.expected,runner.expected[0].manifest_hash)
            record=M18CorrectedRecord(runner.expected[0],"answer_submitted","success")
            self.assertEqual(store.persist(record),record); self.assertEqual(len(store.missing()),359)
            with self.assertRaises(Exception): store.persist(record)
            old=M18V3RunIdentity(runner.expected[0].identity.case_id,"plan_and_execute",1)
            self.assertNotIn(old.run_id,{item.run_id for item in runner.expected})
            payload=record.to_dict(); payload["provenance"]["comparator_contract_id"]="m18_v3"
            with self.assertRaises(Exception): M18CorrectedRecord.from_dict(payload)


if __name__ == "__main__": unittest.main()
