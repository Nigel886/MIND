"""Focused deterministic validation for the M20 harness; no network access."""
from __future__ import annotations

from pathlib import Path
from copy import deepcopy
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m20_harness import (
    M20AdaptiveAdapter, M20Case, M20Condition, M20ConditionRegistry,
    M20EnvironmentResult, M20EvidenceStore, M20ExecutionSpec, M20FixedAdapter,
    M20Harness, M20Manifest, M20Namespace, M20Outcome, M20PrivateCase,
    M20PairingMetadata, M20Proposal, M20ProposalKind, M20ProviderConfiguration, M20PublicCase,
    M20ResourceCeiling, M20ResourceDelta, M20ResourceTelemetry,
    M20ProviderAttemptError,
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
    current = case()
    ceiling = M20ResourceCeiling("m20_ceiling_v1", 8, 8, 8, 8)
    pairing = M20PairingMetadata(current.public.case_id, current.cluster_id, current.payload_digest,
                                 current.environment_id, current.evaluator_id, ceiling.identity)
    return M20Manifest("m20_suite_v1", "m20_environment_v1", "m20_evaluator_v1", (current,),
                       "m20_generation_v1", (pairing,), ceiling)


def provider_hash() -> str:
    return M20ProviderConfiguration("fake", "fake://m20", "fake-model", 0, 1, 64, "json", 1, 0, "disabled").identity_hash


def spec(condition=M20Condition.MIND_FIXED, namespace=M20Namespace.FAKE, replacement_of=None):
    current = manifest()
    item = case()
    return M20ExecutionSpec(current.suite_id, item.public.case_id, 1, condition, namespace, current.digest,
                            provider_hash(), item.cluster_id, item.payload_digest, item.environment_id,
                            item.evaluator_id, current.resource_ceiling.identity, replacement_of)


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
        current = manifest()
        with self.assertRaises(ValueError):
            M20Manifest("m20_suite_v1", "m20_environment_v1", "m20_evaluator_v1", (case(), case()),
                        "g", current.pairing, current.resource_ceiling)
        wrong = M20Case(case().public, case().private, "other_environment", "m20_evaluator_v1")
        with self.assertRaises(ValueError):
            M20Manifest("m20_suite_v1", "m20_environment_v1", "m20_evaluator_v1", (wrong,), "g",
                        current.pairing, current.resource_ceiling)

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
        adapter = M20AdaptiveAdapter(provider)
        record = self.harness().run(spec(M20Condition.MIND_ADAPTIVE), adapter)
        self.assertEqual(record.outcome, M20Outcome.FAILURE_OR_INCORRECT)
        self.assertEqual(record.adapter_id, "m20_m19_adaptive_adapter_v1")
        self.assertEqual(adapter.native_decision_count, 2)
        self.assertEqual(record.resource_pre["allocation_identity"], record.resource_post["allocation_identity"])
        self.assertEqual(provider.proposals, [])

    def test_pair_admission_and_native_bypass_fail_closed(self):
        harness = self.harness()
        fixed, adaptive = spec(), spec(M20Condition.MIND_ADAPTIVE)
        harness.admit_pair(fixed, adaptive)
        with self.assertRaises(Exception):
            harness.admit_pair(fixed, fixed)
        corrupted = M20ExecutionSpec(manifest().suite_id, case().public.case_id, 2, M20Condition.MIND_ADAPTIVE,
                                     M20Namespace.FAKE, manifest().digest, provider_hash(), case().cluster_id,
                                     case().payload_digest, case().environment_id, case().evaluator_id,
                                     manifest().resource_ceiling.identity)
        with self.assertRaises(Exception):
            harness.admit_pair(fixed, corrupted)
        with self.assertRaises(Exception):
            M20AdaptiveAdapter(QueueProvider([])).propose(case().public, {"value": 0})

    def test_resource_state_mismatch_prevents_finalization(self):
        current = manifest()
        initial = current.resource_ceiling.resource_state("audit")
        changed = initial.consume(__import__("src.core.resource_accounting", fromlist=["ResourceDimension"]).ResourceDimension.REASONING_STEP, 1, "audit")
        telemetry = M20ResourceTelemetry()
        with self.assertRaises(Exception):
            telemetry.reconcile(current.resource_ceiling, initial, changed)

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
        item = case(); current = manifest()
        invalid = M20ExecutionSpec("wrong", item.public.case_id, 1, M20Condition.MIND_FIXED,
                                   M20Namespace.FAKE, current.digest, provider_hash(), item.cluster_id,
                                   item.payload_digest, item.environment_id, item.evaluator_id,
                                   current.resource_ceiling.identity)
        with self.assertRaises(Exception):
            self.harness().preflight(invalid)
        wrong_provider = M20ExecutionSpec(current.suite_id, item.public.case_id, 1,
                                           M20Condition.MIND_FIXED, M20Namespace.FAKE,
                                           current.digest, "a" * 64, item.cluster_id, item.payload_digest,
                                           item.environment_id, item.evaluator_id, current.resource_ceiling.identity)
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

    def test_canonical_runner_persists_cohort_lifecycle_and_statistical_input(self):
        with TemporaryDirectory() as directory:
            store = M20EvidenceStore(Path(directory), manifest(), M20Namespace.FAKE)
            record = self.harness().run(spec(), M20FixedAdapter(QueueProvider([
                M20Proposal(M20ProposalKind.ACT, "step"), M20Proposal(M20ProposalKind.ANSWER, payload=7)
            ])), store)
            persisted = store.records()[0]
            self.assertEqual((persisted["cohort"], persisted["lifecycle"]), (case().public.cohort, "completed"))
            evidence = M20EvidenceStore.statistical_input(persisted)
            self.assertEqual(evidence["pair_id"], record.pair_id)
            replay_provider = QueueProvider([])
            replay = self.harness().run(spec(), M20FixedAdapter(replay_provider), store)
            self.assertEqual((replay.digest, replay_provider.seen), (record.digest, []))

    def test_canonical_charged_partial_and_persisted_pair_reconstruction(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); store = M20EvidenceStore(root, manifest(), M20Namespace.FAKE)
            with self.assertRaises(InterruptedError):
                self.harness().run(spec(), M20FixedAdapter(QueueProvider([M20Proposal(M20ProposalKind.ANSWER, payload=7)])), store, interrupt_after_commit=True)
            self.assertEqual(store.lifecycle(spec()).value, "charged_partial")
            reloaded = M20EvidenceStore(root, manifest(), M20Namespace.FAKE)
            with self.assertRaises(Exception):
                self.harness().run(spec(), M20FixedAdapter(QueueProvider([])), reloaded)
        with TemporaryDirectory() as directory:
            store = M20EvidenceStore(Path(directory), manifest(), M20Namespace.FAKE)
            self.harness().run(spec(), M20FixedAdapter(QueueProvider([M20Proposal(M20ProposalKind.ANSWER, payload=0)])), store)
            self.harness().run(spec(M20Condition.MIND_ADAPTIVE), M20AdaptiveAdapter(QueueProvider([M20Proposal(M20ProposalKind.ANSWER, payload=0)])), store)
            pair = M20EvidenceStore.reconstruct_pair(store.records())
            self.assertEqual(pair["adaptive"]["pair_id"], pair["fixed"]["pair_id"])

    def test_provider_attempt_transitions_are_persisted_without_double_charge(self):
        class RetryingProvider:
            retry_ceiling = 1
            def __init__(self): self.calls = 0
            def propose(self, public_case, public_state):
                self.calls += 1
                if self.calls == 1: raise M20ProviderAttemptError("transport", True)
                return M20Proposal(M20ProposalKind.ANSWER, payload=0)
        with TemporaryDirectory() as directory:
            store = M20EvidenceStore(Path(directory), manifest(), M20Namespace.FAKE)
            record = self.harness().run(spec(), M20FixedAdapter(RetryingProvider()), store)
            self.assertEqual((record.telemetry.provider_interactions, record.telemetry.provider_transport_attempts), (1, 2))
            attempts = store.records()[0]["telemetry"]["retries"]
            self.assertEqual([item["retry_index"] for item in attempts], [0, 1])
            self.assertEqual(attempts[0]["reason"], "transport")

    def test_fixed_provider_budget_is_admitted_before_transport(self):
        def limited_harness(provider_budget):
            item = case()
            ceiling = M20ResourceCeiling("m20_limited_ceiling_" + str(provider_budget), 8, 8, provider_budget, 8)
            current = M20Manifest("m20_suite_v1", "m20_environment_v1", "m20_evaluator_v1", (item,),
                                  "m20_generation_v1", (M20PairingMetadata(
                                      item.public.case_id, item.cluster_id, item.payload_digest,
                                      item.environment_id, item.evaluator_id, ceiling.identity,
                                  ),), ceiling)
            execution = M20ExecutionSpec(current.suite_id, item.public.case_id, 1, M20Condition.MIND_FIXED,
                                         M20Namespace.FAKE, current.digest, provider_hash(), item.cluster_id,
                                         item.payload_digest, item.environment_id, item.evaluator_id, ceiling.identity)
            return M20Harness(current, M20ConditionRegistry(provider_hash()), Environment(), Evaluator()), execution, current

        class Steps:
            def __init__(self): self.calls = 0
            def propose(self, public_case, public_state):
                self.calls += 1
                return M20Proposal(M20ProposalKind.ACT, "step")

        for budget in (4, 1):
            harness, execution, current = limited_harness(budget)
            provider = Steps()
            with TemporaryDirectory() as directory:
                store = M20EvidenceStore(Path(directory), current, M20Namespace.FAKE)
                record = harness.run(execution, M20FixedAdapter(provider), store)
                persisted = store.records()[0]
                self.assertEqual(record.outcome, M20Outcome.INCOMPLETE)
                self.assertEqual((provider.calls, record.telemetry.provider_interactions,
                                  record.telemetry.provider_transport_attempts), (budget, budget, budget))
                self.assertEqual(len({item["logical_operation_id"] for item in persisted["telemetry"]["retries"]}), budget)
                M20EvidenceStore.validate_persisted(persisted)

    def test_provider_retry_identity_is_one_logical_chain_per_operation(self):
        class FourOperationsOneRetry:
            retry_ceiling = 2
            def __init__(self): self.calls = 0
            def propose(self, public_case, public_state):
                self.calls += 1
                if self.calls == 2:
                    raise M20ProviderAttemptError("transport", True)
                return (
                    M20Proposal(M20ProposalKind.ACT, "recover") if self.calls in (1, 3) else
                    M20Proposal(M20ProposalKind.ACT, "step") if self.calls == 4 else
                    M20Proposal(M20ProposalKind.ANSWER, payload=7)
                )

        with TemporaryDirectory() as directory:
            store = M20EvidenceStore(Path(directory), manifest(), M20Namespace.FAKE)
            record = self.harness().run(spec(), M20FixedAdapter(FourOperationsOneRetry()), store)
            persisted = store.records()[0]
            attempts = persisted["telemetry"]["retries"]
            self.assertEqual(record.outcome, M20Outcome.SUCCESS)
            self.assertEqual((record.telemetry.provider_interactions, len(attempts)), (4, 5))
            self.assertEqual(len({item["logical_operation_id"] for item in attempts}), 4)
            self.assertEqual([item["retry_index"] for item in attempts].count(1), 1)
            retry = next(item for item in attempts if item["retry_index"] == 1)
            initial = next(item for item in attempts if item["logical_operation_id"] == retry["logical_operation_id"] and item["retry_index"] == 0)
            self.assertNotEqual(initial["physical_attempt_id"], retry["physical_attempt_id"])
            M20EvidenceStore.validate_persisted(persisted)

    def test_two_provider_retries_remain_one_logical_operation(self):
        class ThreeAttempts:
            retry_ceiling = 2
            def __init__(self): self.calls = 0
            def propose(self, public_case, public_state):
                self.calls += 1
                if self.calls < 3:
                    raise M20ProviderAttemptError("transport", True)
                return M20Proposal(M20ProposalKind.ANSWER, payload=0)

        with TemporaryDirectory() as directory:
            store = M20EvidenceStore(Path(directory), manifest(), M20Namespace.FAKE)
            record = self.harness().run(spec(), M20FixedAdapter(ThreeAttempts()), store)
            attempts = store.records()[0]["telemetry"]["retries"]
            self.assertEqual((record.telemetry.provider_interactions, len(attempts)), (1, 3))
            self.assertEqual([item["retry_index"] for item in attempts], [0, 1, 2])
            self.assertEqual(len({item["logical_operation_id"] for item in attempts}), 1)

    def test_retry_identity_negative_matrix_fails_closed(self):
        class Retrying:
            retry_ceiling = 1
            def __init__(self): self.calls = 0
            def propose(self, public_case, public_state):
                self.calls += 1
                if self.calls == 1:
                    raise M20ProviderAttemptError("transport", True)
                return M20Proposal(M20ProposalKind.ANSWER, payload=0)

        with TemporaryDirectory() as directory:
            store = M20EvidenceStore(Path(directory), manifest(), M20Namespace.FAKE)
            self.harness().run(spec(), M20FixedAdapter(Retrying()), store)
            baseline = store.records()[0]

        def changed(change):
            value = deepcopy(baseline)
            change(value)
            with self.assertRaises(Exception):
                M20EvidenceStore.validate_persisted(value)

        changed(lambda value: value["telemetry"]["retries"][1].__setitem__("logical_operation_id", "wrong-parent"))
        changed(lambda value: value["telemetry"]["retries"][1].__setitem__("retry_index", 0))
        changed(lambda value: value["telemetry"].__setitem__("retries", list(reversed(value["telemetry"]["retries"]))))
        changed(lambda value: value["telemetry"]["retries"][1].__setitem__("physical_attempt_id", value["telemetry"]["retries"][0]["physical_attempt_id"]))
        changed(lambda value: (value["telemetry"].__setitem__("retries", value["telemetry"]["retries"][1:]), value["telemetry"].__setitem__("provider_transport_attempts", 1)))
        changed(lambda value: value["telemetry"].__setitem__("provider_interactions", 2))
        changed(lambda value: value["telemetry"].__setitem__("provider_interactions", 0))
        changed(lambda value: value["telemetry"].__setitem__("provider_transport_attempts", 1))
        changed(lambda value: value["telemetry"]["retries"][1].__setitem__("owner", "caller_rerun"))

    def test_adaptive_native_callback_uses_same_retry_boundary(self):
        class RetryingProvider:
            retry_ceiling = 1
            def __init__(self): self.calls = 0
            def propose(self, public_case, public_state):
                self.calls += 1
                if self.calls == 1: raise M20ProviderAttemptError("transport", True)
                return M20Proposal(M20ProposalKind.ANSWER, payload=0)
        with TemporaryDirectory() as directory:
            store = M20EvidenceStore(Path(directory), manifest(), M20Namespace.FAKE)
            record = self.harness().run(spec(M20Condition.MIND_ADAPTIVE), M20AdaptiveAdapter(RetryingProvider()), store)
            self.assertEqual((record.telemetry.provider_interactions, record.telemetry.provider_transport_attempts), (1, 2))
            self.assertEqual([item["retry_index"] for item in store.records()[0]["telemetry"]["retries"]], [0, 1])

    def test_retry_exhaustion_and_malformed_are_terminal_persisted_attempts(self):
        class Exhausted:
            retry_ceiling = 1
            def propose(self, public_case, public_state): raise M20ProviderAttemptError("transport", True)
        class Malformed:
            retry_ceiling = 1
            def propose(self, public_case, public_state): return object()
        for provider, attempts, reason in ((Exhausted(), 2, "transport"), (Malformed(), 1, "malformed_response")):
            with TemporaryDirectory() as directory:
                store = M20EvidenceStore(Path(directory), manifest(), M20Namespace.FAKE)
                record = self.harness().run(spec(), M20FixedAdapter(provider), store)
                self.assertEqual(record.outcome, M20Outcome.PROVIDER_FAILURE)
                chain = store.records()[0]["telemetry"]["retries"]
                self.assertEqual((len(chain), chain[-1]["reason"], chain[-1]["terminal"]), (attempts, reason, True))

    def test_disk_only_pair_retry_and_statistical_corruption_fail_closed(self):
        class Retrying:
            retry_ceiling = 1
            def __init__(self): self.calls = 0
            def propose(self, public_case, public_state):
                self.calls += 1
                if self.calls == 1: raise M20ProviderAttemptError("transport", True)
                return M20Proposal(M20ProposalKind.ANSWER, payload=0)
        with TemporaryDirectory() as directory:
            root = Path(directory); store = M20EvidenceStore(root, manifest(), M20Namespace.FAKE)
            self.harness().run(spec(), M20FixedAdapter(Retrying()), store)
            self.harness().run(spec(M20Condition.MIND_ADAPTIVE), M20AdaptiveAdapter(Retrying()), store)
            reloaded = M20EvidenceStore(root, manifest(), M20Namespace.FAKE).records()
            pair = M20EvidenceStore.reconstruct_pair(reloaded)
            self.assertEqual(set(pair), {"pair_id", "cohort", "adaptive", "fixed"})
            for record in reloaded:
                self.assertIn("protocol", M20EvidenceStore.statistical_input(record)["provenance"])
            for mutate in (
                lambda value: value.pop("cohort"),
                lambda value: value.__setitem__("lifecycle", "invalid"),
                lambda value: value["telemetry"]["retries"][1].__setitem__("retry_index", 3),
                lambda value: value["telemetry"].__setitem__("provider_interactions", 2),
                lambda value: value["provenance"].pop("metrics"),
                lambda value: value["provenance"].pop("protocol"),
            ):
                corrupt = deepcopy(reloaded[0]); mutate(corrupt)
                with self.assertRaises(Exception): M20EvidenceStore.statistical_input(corrupt)
            corrupt_pair = list(deepcopy(reloaded)); corrupt_pair[1]["spec"]["cluster_id"] = "wrong"
            with self.assertRaises(Exception): M20EvidenceStore.reconstruct_pair(tuple(corrupt_pair))

    def test_pairing_delta_retry_and_partial_lifecycle_fail_closed(self):
        current = manifest(); harness = self.harness(); item = case()
        bad = M20ExecutionSpec(current.suite_id, item.public.case_id, 1, M20Condition.MIND_FIXED,
                               M20Namespace.FAKE, current.digest, provider_hash(), "wrong_cluster",
                               item.payload_digest, item.environment_id, item.evaluator_id,
                               current.resource_ceiling.identity)
        with self.assertRaises(Exception):
            harness.preflight(bad)
        with TemporaryDirectory() as directory:
            store = M20EvidenceStore(Path(directory), current, M20Namespace.FAKE)
            zero = M20ResourceTelemetry()
            store.mark_partial(spec(), zero)
            self.assertEqual(store.reconcile((spec(),))["incomplete"], 1)
            store.resume_partial(spec())
            self.assertTrue((Path(directory) / (spec().execution_id + ".partial.resolved.json")).exists())
            self.assertEqual(store.reconcile((spec(),))["missing"], 0)
            charged = M20ResourceTelemetry(reasoning_steps=1, deltas=(M20ResourceDelta("r", reasoning_steps=1),))
            store.mark_partial(spec(), charged)
            with self.assertRaises(Exception):
                store.resume_partial(spec())

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
