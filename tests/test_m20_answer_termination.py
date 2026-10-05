"""Focused offline coverage for the shared M20 answer-termination phase."""
from __future__ import annotations

import json
import unittest

from src.evaluation.m20_ceilingv2_calibration_execution import M20CeilingV2CalibrationRunner
from src.evaluation.m20_deepseek_execution import M20DeepSeekProposalAdapter
from src.evaluation.m20_harness import (
    M20AdaptiveAdapter, M20Condition, M20FixedAdapter, M20Outcome, M20Proposal,
    M20ProposalKind, M20ProviderAttemptError, M20Harness, m20_answer_ready,
)
from src.evaluation.m20_real_case_source import M20RealEnvironment, M20RealEvaluator, real_case_definitions


class QueueProvider:
    def __init__(self, proposals):
        self.proposals = list(proposals)
        self.calls = 0

    def propose(self, _case, _state):
        self.calls += 1
        return self.proposals.pop(0)


def response(value):
    return {"model": "deepseek-flash", "choices": [{"message": {"content": json.dumps(value)}}]}


class M20AnswerTerminationTest(unittest.TestCase):
    def test_public_readiness_reaches_all_frozen_witness_states_without_private_projection(self):
        environment = M20RealEnvironment()
        for definition in real_case_definitions():
            case = definition.to_case()
            state = environment.initial_public_state(case.public)
            action_count = 0
            for step in case.private.reference_witness:
                if step["kind"] == "answer":
                    break
                self.assertFalse(m20_answer_ready(state, case.public))
                state = environment.apply(case.public, state,
                                          M20Proposal(M20ProposalKind.ACT, step["action_id"])).state
                action_count += 1
            self.assertTrue(m20_answer_ready(state, case.public))
            self.assertLessEqual(action_count + 1, 3)
        self.assertFalse(m20_answer_ready({"progress": 0}, real_case_definitions()[0].to_case().public))

    def _run(self, condition, terminal):
        runner = M20CeilingV2CalibrationRunner()
        item = next(item for item in runner.work_items()
                    if item.spec.case_id == "m20.real.multi_step_stateful.01" and item.spec.condition is condition)
        provider = QueueProvider([
            M20Proposal(M20ProposalKind.ACT, "advance"),
            M20Proposal(M20ProposalKind.ACT, "advance"),
            terminal,
        ])
        adapter = M20AdaptiveAdapter(provider) if condition is M20Condition.MIND_ADAPTIVE else M20FixedAdapter(provider)
        harness = M20Harness(runner.harness.manifest, runner.harness.registry, M20RealEnvironment(), M20RealEvaluator(),
                             answer_termination_enabled=True)
        return harness.run(item.spec, adapter), provider

    def test_answer_phase_has_adaptive_fixed_parity_and_evaluator_handoff(self):
        for condition in (M20Condition.MIND_ADAPTIVE, M20Condition.MIND_FIXED):
            record, provider = self._run(condition, M20Proposal(M20ProposalKind.ANSWER,
                                                                  payload="answer:m20.real.multi_step_stateful.01"))
            self.assertEqual(record.outcome, M20Outcome.SUCCESS)
            self.assertEqual(provider.calls, 3)
            self.assertEqual(record.telemetry.tool_attempts, 2)
            self.assertEqual(record.telemetry.answer_ready_first_cycle, 3)
            self.assertTrue(record.telemetry.answer_phase_entered)
            self.assertTrue(record.telemetry.answer_proposed)
            self.assertTrue(record.telemetry.evaluator_handoff)

    def test_stop_and_illegal_action_terminate_before_a_third_tool(self):
        for condition in (M20Condition.MIND_ADAPTIVE, M20Condition.MIND_FIXED):
            stopped, _ = self._run(condition, M20Proposal(M20ProposalKind.STOP))
            self.assertEqual(stopped.outcome, M20Outcome.INCOMPLETE)
            self.assertTrue(stopped.telemetry.stop_proposed)
            self.assertEqual(stopped.telemetry.tool_attempts, 2)
            illegal, _ = self._run(condition, M20Proposal(M20ProposalKind.ACT, "advance"))
            self.assertEqual(illegal.outcome, M20Outcome.INVALID_INTERACTION)
            self.assertTrue(illegal.telemetry.illegal_act_in_answer_phase)
            self.assertEqual(illegal.telemetry.tool_attempts, 2)

    def test_answer_phase_request_is_public_and_act_is_rejected_by_parser(self):
        definition = next(item for item in real_case_definitions() if item.case_id == "m20.real.multi_step_stateful.01")
        case, environment = definition.to_case(), M20RealEnvironment()
        state = environment.initial_public_state(case.public)
        for step in definition.witness[:2]:
            state = environment.apply(case.public, state, M20Proposal(M20ProposalKind.ACT, step["action_id"])).state
        seen = []
        adapter = M20DeepSeekProposalAdapter(lambda request, _timeout: seen.append(request) or response({"kind": "stop"}),
                                             answer_termination_enabled=True)
        self.assertIs(adapter.propose(case.public, state).kind, M20ProposalKind.STOP)
        public = json.loads(seen[0]["messages"][1]["content"].split("Public input: ", 1)[1])
        self.assertEqual((public["actions"], public["legal_decision_kinds"]), ([], ["answer", "stop"]))
        wire = json.dumps(seen[0], sort_keys=True)
        for secret in (case.private.target, "reference_witness", "required_progress", "requires_observation", "requires_recovery"):
            self.assertNotIn(secret, wire)
        rejected = M20DeepSeekProposalAdapter(lambda *_: response({"kind": "act", "action_id": "advance"}),
                                              answer_termination_enabled=True)
        with self.assertRaises(M20ProviderAttemptError):
            rejected.propose(case.public, state)
        self.assertTrue(rejected.last_diagnostic["illegal_act_in_answer_phase"])


if __name__ == "__main__":
    unittest.main()
