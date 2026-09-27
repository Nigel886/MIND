"""Focused deterministic validation for the M20 harness; no network access."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m20_harness import (
    M20AdaptiveAdapter, M20Case, M20Condition, M20ConditionRegistry,
    M20EnvironmentResult, M20EvidenceStore, M20ExecutionSpec, M20FixedAdapter,
    M20Harness, M20Manifest, M20Namespace, M20Outcome, M20PrivateCase,
    M20Proposal, M20ProposalKind, M20ProviderConfiguration, M20PublicCase,
    M20_FIXED_SCHEDULE_ID, canonical_hash,
)


class Environment:
    environment_id = "m20_environment_v1"
    def initial_public_state(self, case):
        return dict(case.initial_state)
    def apply(self, case, state, proposal):
        if proposal.action_id == "infra":
            return M20EnvironmentResult(dict(state), "infra", infrastructure_failure=True)
        if proposal.action_id == "recover":
            return M20EnvironmentResult(dict(state), "recover", recoverable=True)
        if proposal.action_id == "step":
            return M20EnvironmentResult({"value": state["value"] + 1}, "stepped")
        return M20EnvironmentResult(dict(state), "invalid", terminal=True)


class Evaluator:
    evaluator_id = "m20_evaluator_v1"
    def evaluate(self, case, state, answer):
        return M20Outcome.SUCCESS if answer == case.private.target and state["value"] == 1 else M20Outcome.FAILURE_OR_INCORRECT


class QueueProvider:
    def __init__(self, proposals):
        self.proposals = list(proposals)
        self.seen = []
    def propose(self, public_case, public_state):
        self.seen.append((public_case.to_dict(), dict(public_state)))
        return self.proposals.pop(0)


def case() -> M20Case:
    public = M20PublicCase("m20.fake.case.1", "multi_step_stateful", "advance publicly", {"value": 0},
                           {"step": {"schema": {}}, "recover": {"schema": {}}, "infra": {"schema": {}}})
    private = M20PrivateCase(7, ({"kind": "act", "action_id": "step"}, {"kind": "answer", "payload": 7}))
    return M20Case(public, private)


def manifest() -> M20Manifest:
    return M20Manifest("m20_suite_v1", "m20_environment_v1", "m20_evaluator_v1", (case(),), "m20_generation_v1")


def provider_hash() -> str:
    return M20ProviderConfiguration("fake", "fake://m20", "fake-model", 0, 1, 64, "json", 1, 0, "disabled").identity_hash


def spec(condition=M20Condition.MIND_FIXED, namespace=M20Namespace.FAKE, replacement_of=None):
    current = manifest()
    return M20ExecutionSpec(current.suite_id, case().public.case_id, 1, condition, namespace, current.digest, provider_hash(), replacement_of)


class M20HarnessTest(unittest.TestCase):
    def harness(self):
        current = manifest()
        return M20Harness(current, M20ConditionRegistry(provider_hash()), Environment(), Evaluator())

    def test_registry_is_closed_and_provider_bound(self):
        registry = M20ConditionRegistry(provider_hash())
        self.assertEqual(registry.binding(M20Condition.MIND_FIXED).adapter_id, "m20_fixed_cycle_adapter_v1")
        with self.assertRaises(ValueError):
            registry.binding("arbitrary")

    def test_fixed_schedule_is_exact_and_nonadaptive(self):
        adapter = M20FixedAdapter(QueueProvider([]))
        self.assertEqual(adapter.schedule(), ("continue_reasoning", "commit"))
        self.assertEqual(adapter.schedule(True), ("replan", "continue_reasoning", "commit"))
        self.assertEqual((adapter.schedule_id, adapter.reasoning_transitions_per_state,
                          adapter.commit_slots_per_state, adapter.proposal_attempts_per_slot,
                          adapter.replans_per_recoverable_feedback),
                         (M20_FIXED_SCHEDULE_ID, 1, 1, 1, 1))
        for forbidden in ("uncertainty", "expected_information_gain", "value", "confidence", "stop_when"):
            self.assertFalse(hasattr(adapter, forbidden))

    def test_manifest_duplicate_and_identity_mismatch_fail_closed(self):
        with self.assertRaises(ValueError):
            M20Manifest("m20_suite_v1", "m20_environment_v1", "m20_evaluator_v1", (case(), case()), "g")
        wrong = M20Case(case().public, case().private, "other_environment", "m20_evaluator_v1")
        with self.assertRaises(ValueError):
            M20Manifest("m20_suite_v1", "m20_environment_v1", "m20_evaluator_v1", (wrong,), "g")

    def test_reachability_is_private_and_public_contract_only(self):
        harness = self.harness()
        self.assertTrue(harness.validate_reachability(case()))
        provider = QueueProvider([M20Proposal(M20ProposalKind.ACT, "step"), M20Proposal(M20ProposalKind.ANSWER, payload=7)])
        record = harness.run(spec(), M20FixedAdapter(provider))
        self.assertEqual(record.outcome, M20Outcome.SUCCESS)
        self.assertEqual(record.telemetry.reasoning_steps, 2)
        self.assertEqual(record.telemetry.provider_interactions, 2)
        self.assertEqual(record.telemetry.tool_attempts, 1)
        serialized = str(provider.seen)
        self.assertNotIn("reference_witness", serialized)
        self.assertNotIn("target", serialized)

    def test_adaptive_binding_uses_same_official_evaluator(self):
        provider = QueueProvider([M20Proposal(M20ProposalKind.ACT, "step"), M20Proposal(M20ProposalKind.ANSWER, payload=0)])
        record = self.harness().run(spec(M20Condition.MIND_ADAPTIVE), M20AdaptiveAdapter(provider))
        self.assertEqual(record.outcome, M20Outcome.FAILURE_OR_INCORRECT)
        self.assertEqual(record.adapter_id, "m20_m19_adaptive_adapter_v1")

    def test_invalid_and_infrastructure_outcomes_remain_typed(self):
        invalid = self.harness().run(spec(), M20FixedAdapter(QueueProvider([M20Proposal(M20ProposalKind.ACT, "missing")])))
        self.assertEqual(invalid.outcome, M20Outcome.INVALID_INTERACTION)
        failed = self.harness().run(spec(), M20FixedAdapter(QueueProvider([M20Proposal(M20ProposalKind.ACT, "infra")])))
        self.assertEqual(failed.outcome, M20Outcome.INFRASTRUCTURE_FAILURE)
        replacement = self.harness().replacement(failed)
        self.assertNotEqual(replacement.execution_id, failed.execution_id)
        self.assertEqual(replacement.replacement_of, failed.execution_id)
        with self.assertRaises(PermissionError):
            self.harness().replacement(invalid)

    def test_provider_failure_and_fixed_recovery_schedule_are_typed(self):
        class BrokenProvider:
            def propose(self, public_case, public_state):
                raise RuntimeError("fake provider failure")
        failed = self.harness().run(spec(), M20FixedAdapter(BrokenProvider()))
        self.assertEqual(failed.outcome, M20Outcome.PROVIDER_FAILURE)
        recovered = self.harness().run(spec(), M20FixedAdapter(QueueProvider([
            M20Proposal(M20ProposalKind.ACT, "recover"),
            M20Proposal(M20ProposalKind.ACT, "step"),
            M20Proposal(M20ProposalKind.ANSWER, payload=7),
        ])))
        self.assertEqual(recovered.outcome, M20Outcome.SUCCESS)
        self.assertEqual(recovered.telemetry.reasoning_steps, 4)

    def test_formal_namespace_and_manifest_mismatch_are_guarded(self):
        with self.assertRaises(PermissionError):
            self.harness().preflight(spec(namespace=M20Namespace.FORMAL))
        invalid = M20ExecutionSpec("wrong", case().public.case_id, 1, M20Condition.MIND_FIXED,
                                   M20Namespace.FAKE, manifest().digest, provider_hash())
        with self.assertRaises(Exception):
            self.harness().preflight(invalid)
        wrong_provider = M20ExecutionSpec(manifest().suite_id, case().public.case_id, 1,
                                           M20Condition.MIND_FIXED, M20Namespace.FAKE,
                                           manifest().digest, "a" * 64)
        with self.assertRaises(Exception):
            self.harness().preflight(wrong_provider)

    def test_evidence_is_append_only_digest_bound_and_resume_idempotent(self):
        harness = self.harness()
        completed = harness.run(spec(), M20FixedAdapter(QueueProvider([M20Proposal(M20ProposalKind.ACT, "step"), M20Proposal(M20ProposalKind.ANSWER, payload=7)])))
        with TemporaryDirectory() as directory:
            store = M20EvidenceStore(Path(directory), manifest(), M20Namespace.FAKE)
            store.persist(completed)
            self.assertEqual(store.completed_ids(), frozenset({completed.execution_id}))
            with self.assertRaises(FileExistsError):
                store.persist(completed)
            reconciliation = store.reconcile((spec(),))
            self.assertEqual((reconciliation["expected"], reconciliation["completed"], reconciliation["missing"]),
                             (1, 1, 0))
            self.assertEqual(len(store.records()), 1)
            with self.assertRaises(PermissionError):
                M20EvidenceStore(Path(directory) / "formal", manifest(), M20Namespace.FORMAL)

    def test_pair_identity_condition_uniqueness_and_provenance(self):
        fixed = spec(M20Condition.MIND_FIXED)
        adaptive = spec(M20Condition.MIND_ADAPTIVE)
        self.assertEqual(fixed.pair_id, adaptive.pair_id)
        self.assertNotEqual(fixed.execution_id, adaptive.execution_id)
        record = self.harness().run(fixed, M20FixedAdapter(QueueProvider([M20Proposal(M20ProposalKind.ANSWER, payload=0)])))
        self.assertEqual(record.digest, canonical_hash(record.canonical()))
        self.assertEqual(set(("harness", "provenance_schema", "suite", "environment", "evaluator", "condition", "provider_hash", "metrics", "protocol", "manifest", "adapter")), set(record.provenance))


if __name__ == "__main__":
    unittest.main()
