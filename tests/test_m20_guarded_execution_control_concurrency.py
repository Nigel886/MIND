"""Deterministic two-session controls regressions over the production Guard."""
from __future__ import annotations

import unittest
import json

from tests.m20_test_scratch import TemporaryDirectory
from tests.test_m20_v2_guarded_fixture import GuardedV2Fixture
from tests.test_m20_prospective_feasibility import owner_risk_policy
from src.evaluation.m20_financial_control import M20FeasibilityFinancialLedger, M20FinancialControlBlocked
from src.evaluation.m20_prospective_feasibility import M20FeasibilityLiveBudget, feasibility_live_authorization_payload
from src.evaluation.m20_harness import M20IntegrityError
from src.evaluation.m20_deepseek_execution import M20DeepSeekProposalAdapter


class GuardedExecutionControlConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(); self.directory = self.tmp.__enter__()
        self.fixture = GuardedV2Fixture(self.directory); self.risk = owner_risk_policy()
        self.auth = feasibility_live_authorization_payload(owner_risk_policy=self.risk)
        self.a = self.fixture.runner._control_session(self.fixture.destination)
        self.b = self.fixture.runner._control_session(self.fixture.destination)
        self.ba = M20FeasibilityLiveBudget(self.fixture.destination, self.auth, self.fixture.destination / "stop", self.a)
        self.bb = M20FeasibilityLiveBudget(self.fixture.destination, self.auth, self.fixture.destination / "stop", self.b)
        self.la = M20FeasibilityFinancialLedger(self.fixture.destination, self.auth, self.risk, None, self.fixture.destination / "stop", self.a)
        self.lb = M20FeasibilityFinancialLedger(self.fixture.destination, self.auth, self.risk, None, self.fixture.destination / "stop", self.b)
    def tearDown(self):
        self.a.close(); self.b.close(); self.tmp.__exit__(None,None,None)
    def test_lease_contention_prevents_mutation(self):
        lease=self.a.acquire_dispatch_lease({"test":"a"}); before=dict(self.fixture.ops.nodes[self.fixture.control_node].children)
        with self.assertRaises(Exception): self.b.acquire_dispatch_lease({"test":"b"})
        self.assertEqual(before, self.fixture.ops.nodes[self.fixture.control_node].children); self.a.release_dispatch_lease(lease)
    def test_stale_budget_cannot_authorize_second_execution(self):
        self.ba.precheck(); self.bb.precheck(); lease=self.a.acquire_dispatch_lease({"test":"a"}); self.ba.admit(); self.a.release_dispatch_lease(lease)
        lease=self.b.acquire_dispatch_lease({"test":"b"})
        # The fresh guarded read sees A's persisted admission; limits are not overwritten.
        self.assertGreaterEqual(self.bb._load()["consumed"]["total"], 1); self.b.release_dispatch_lease(lease)
    def test_non_owner_cannot_mutate_controls(self):
        lease=self.a.acquire_dispatch_lease({"test":"a"})
        with self.assertRaises(M20IntegrityError): self.b.replace_json("live_budget.json", {"foreign":True})
        with self.assertRaises(M20IntegrityError): self.b.replace_json("financial_ledger.json", {"foreign":True})
        self.a.release_dispatch_lease(lease)
    def test_budget_persisted_ledger_failure_is_conservative(self):
        lease=self.a.acquire_dispatch_lease({"test":"a"}); self.ba.admit(); self.a.release_dispatch_lease(lease)
        lease=self.b.acquire_dispatch_lease({"test":"b"}); self.assertGreaterEqual(self.bb._load()["consumed"]["total"],1); self.b.release_dispatch_lease(lease)
    def test_dispatched_unsettled_is_not_redispatched(self):
        lease=self.a.acquire_dispatch_lease({"test":"a"}); self.ba.admit(); key=self.la.reserve("e"*64,"op",0,{"x":1}); self.la.mark_dispatched(key); self.a.release_dispatch_lease(lease)
        lease=self.b.acquire_dispatch_lease({"test":"b"}); self.assertEqual(self.lb._load()["attempts"][key]["status"],"DISPATCHED")
        with self.assertRaises(Exception): self.lb.reserve("e"*64,"op",0,{"x":1})
        self.b.release_dispatch_lease(lease)
    def test_post_transport_commitment_survives_evidence_failure_boundary(self):
        calls=[]; lease=self.a.acquire_dispatch_lease({"test":"a"}); self.ba.admit(); key=self.la.reserve("f"*64,"op",0,{"x":1}); self.la.mark_dispatched(key); calls.append(1); self.la.settle(key,{"usage":{"prompt_cache_hit_tokens":0,"prompt_cache_miss_tokens":0,"completion_tokens":0}},"response_received"); self.a.release_dispatch_lease(lease)
        self.assertEqual(calls,[1]); lease=self.b.acquire_dispatch_lease({"test":"b"}); self.assertEqual(self.lb._load()["attempts"][key]["status"],"SETTLED"); self.b.release_dispatch_lease(lease)

    def test_unsettled_dispatched_attempt_blocks_distinct_later_transport(self):
        case=self.fixture.runner.harness.manifest.case(self.fixture.runner.work_items()[0].spec.case_id).public
        state=self.fixture.runner.harness.environment.initial_public_state(case)
        calls_a=[]; calls_b=[]
        def interrupted_transport(_request,_timeout):
            calls_a.append(1); raise RuntimeError("interrupted after dispatch")
        a=M20DeepSeekProposalAdapter(interrupted_transport,financial_ledger=self.la,execution_id="a"*64,work_id="a",
            admit_logical_operation=lambda:self.ba.precheck(),guarded_budget_admission=lambda:self.ba.admit())
        a.set_attempt_context("a-op",0); a.admit_logical_operation()
        with self.assertRaisesRegex(RuntimeError,"interrupted after dispatch"): a.propose(case,state)
        persisted=self.la._load()["attempts"]
        self.assertEqual((calls_a,len(persisted),next(iter(persisted.values()))["status"]),([1],1,"DISPATCHED"))
        self.a.close(); self.b.close()
        self.a=self.fixture.runner._control_session(self.fixture.destination)
        self.b=self.fixture.runner._control_session(self.fixture.destination)
        budget=M20FeasibilityLiveBudget(self.fixture.destination,self.auth,self.fixture.destination/"stop",self.b)
        ledger=M20FeasibilityFinancialLedger(self.fixture.destination,self.auth,self.risk,None,self.fixture.destination/"stop",self.b)
        def second_transport(_request,_timeout):
            calls_b.append(1); return {"model":"deepseek-flash","choices":[{"message":{"content":json.dumps({"kind":"act","action_id":"advance"})}}]}
        b=M20DeepSeekProposalAdapter(second_transport,financial_ledger=ledger,execution_id="b"*64,work_id="b",
            admit_logical_operation=lambda:budget.precheck(),guarded_budget_admission=lambda:budget.admit())
        b.set_attempt_context("b-op",0); b.admit_logical_operation()
        with self.assertRaises(M20FinancialControlBlocked): b.propose(case,state)
        self.assertEqual(calls_b,[])

    def test_settled_attempt_permits_distinct_later_dispatch(self):
        with self.la.physical_dispatch():
            key=self.la.reserve("a"*64,"a-op",0,{"request":True})
            self.la.mark_dispatched(key)
            self.la.settle(key,{"usage":{"prompt_cache_hit_tokens":0,"prompt_cache_miss_tokens":0,"completion_tokens":0}},"response_received")
        with self.lb.physical_dispatch():
            key=self.lb.reserve("b"*64,"b-op",0,{"request":True})
            self.lb.mark_dispatched(key)
            self.lb.settle(key,{"usage":{"prompt_cache_hit_tokens":0,"prompt_cache_miss_tokens":0,"completion_tokens":0}},"response_received")
        self.assertEqual({item["status"] for item in self.lb._load()["attempts"].values()},{"SETTLED"})

    def test_unsettled_reserved_attempt_blocks_later_dispatch(self):
        with self.la.physical_dispatch(): self.la.reserve("a"*64,"a-op",0,{"request":True})
        with self.assertRaises(M20FinancialControlBlocked):
            with self.lb.physical_dispatch(): self.fail("unsettled reservation admitted another dispatch")

    def test_two_real_adapters_cannot_overspend_or_duplicate_transport(self):
        # Both adapters are constructed before A mutates the guarded state.
        self.auth["original_logical_provider_interaction_limit"] = 1
        self.auth["replacement_logical_provider_interaction_limit"] = 0
        self.auth["maximum_logical_provider_interactions"] = 1
        self.a.close(); self.b.close()
        self.a=self.fixture.runner._control_session(self.fixture.destination); self.b=self.fixture.runner._control_session(self.fixture.destination)
        self.ba=M20FeasibilityLiveBudget(self.fixture.destination,self.auth,self.fixture.destination/"stop",self.a)
        self.bb=M20FeasibilityLiveBudget(self.fixture.destination,self.auth,self.fixture.destination/"stop",self.b)
        self.la=M20FeasibilityFinancialLedger(self.fixture.destination,self.auth,self.risk,None,self.fixture.destination/"stop",self.a)
        self.lb=M20FeasibilityFinancialLedger(self.fixture.destination,self.auth,self.risk,None,self.fixture.destination/"stop",self.b)
        case=self.fixture.runner.harness.manifest.case(self.fixture.runner.work_items()[0].spec.case_id).public
        state=self.fixture.runner.harness.environment.initial_public_state(case)
        calls_a=[]; calls_b=[]; rejected=[]
        def transport_b(_request,_timeout): calls_b.append(1); return {"model":"deepseek-flash","choices":[{"message":{"content":json.dumps({"kind":"act","action_id":"advance"})}}]}
        b=M20DeepSeekProposalAdapter(transport_b,financial_ledger=self.lb,execution_id="b"*64,work_id="b",admit_logical_operation=lambda:self.bb.precheck(),guarded_budget_admission=lambda:self.bb.admit())
        b.set_attempt_context("b-op",0)
        def transport_a(_request,_timeout):
            calls_a.append(1)
            before=dict(self.fixture.ops.nodes[self.fixture.control_node].children)
            try: b.admit_logical_operation(); b.propose(case,state)
            except Exception as error: rejected.append(error)
            self.assertEqual(before,self.fixture.ops.nodes[self.fixture.control_node].children)
            return {"model":"deepseek-flash","choices":[{"message":{"content":json.dumps({"kind":"act","action_id":"advance"})}}]}
        a=M20DeepSeekProposalAdapter(transport_a,financial_ledger=self.la,execution_id="a"*64,work_id="a",admit_logical_operation=lambda:self.ba.precheck(),guarded_budget_admission=lambda:self.ba.admit())
        a.set_attempt_context("a-op",0); a.admit_logical_operation(); a.propose(case,state)
        self.assertEqual((calls_a,calls_b),([1],[])); self.assertTrue(rejected)
        with self.assertRaises(Exception): b.admit_logical_operation(); b.propose(case,state)
        self.assertEqual(calls_b,[])
        self.assertEqual(self.bb._load()["consumed"]["total"],1)
        attempts=self.lb._load()["attempts"]; self.assertEqual(len(attempts),1); self.assertEqual(next(iter(attempts.values()))["status"],"SETTLED")

if __name__ == "__main__": unittest.main()
