from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m18_execution_harness import (
    M18_FORMAL_REPETITIONS, M18_SYSTEMS, M18_SYSTEM_ARTIFACTS, M18ExecutionMode, M18FrozenProviderBinding, M18HarnessManifest, M18MINDAdapter, M18ResultStore,
    M18ExecutionIntegrityError, M18RunSpec, M18RuntimeTerminal, M18SharedExecutionHarness, balanced_schedule, direct_adapter,
    formal_manifest, harness_identity, neutral_failure, plan_adapter, react_adapter,
)
from src.evaluation.m18_task_generation import M18Cohort, M18Difficulty, M18EvaluationCategory, M18Namespace, generate_m18_case
from src.evaluation.m18_shared_provider import M18SharedProviderClient, M18SharedProviderConfiguration
from src.evaluation.m18_shared_provider import M18SharedMINDProvider
from urllib.error import HTTPError

HASH = "0f251e14722603e6e39416374467a3598cd72e1d28673e60daf8440dd6115ee2"

class OneActionProvider:
    def __init__(self, output='{"action":"answer","answer":"not-private"}'): self.output = output
    def generate(self, request): return self.output

class QueueActionProvider:
    def __init__(self, outputs): self.outputs = list(outputs); self.requests = []
    def generate(self, request): self.requests.append(request.to_dict()); return self.outputs.pop(0)

class OnePlanProvider:
    def plan(self, request): return '{"steps":[{"step_id":"finish","subgoal":"return answer","capability_id":null}]}'
    def execute(self, request): return '{"action":"answer","answer":"not-private"}'

class ToolThenAnswerPlanProvider:
    def __init__(self, tool): self.tool, self.actions = tool, [f'{{"action":"tool_call","tool_name":"{tool}","parameters":{{}}}}', '{"action":"answer","answer":"x"}']
    def plan(self, request): return '{"steps":[{"step_id":"tool","subgoal":"call","capability_id":"' + self.tool + '"},{"step_id":"answer","subgoal":"answer","capability_id":null}]}'
    def execute(self, request): return self.actions.pop(0)

def synthetic_case():
    # Fresh seed: it is neither read from nor equal to any frozen suite record.
    return generate_m18_case(M18Cohort.B, M18Difficulty.EASY, 990001, M18Namespace.PILOT, 0)

class HarnessIdentityTests(unittest.TestCase):
    def test_run_identity_changes_for_system_repetition_and_provider(self):
        first = M18RunSpec("m18_suite_v1", "synthetic.case", "mind_lite_v11", 1, HASH)
        self.assertEqual(first.run_id, M18RunSpec("m18_suite_v1", "synthetic.case", "mind_lite_v11", 1, HASH).run_id)
        self.assertNotEqual(first.run_id, M18RunSpec("m18_suite_v1", "synthetic.case", "direct_tool_calling", 1, HASH).run_id)
        self.assertNotEqual(first.run_id, M18RunSpec("m18_suite_v1", "synthetic.case", "mind_lite_v11", 2, HASH).run_id)
        self.assertNotEqual(first.run_id, M18RunSpec("m18_suite_v1", "synthetic.case", "mind_lite_v11", 1, "a" * 64).run_id)

    def test_interleaved_schedule_is_deterministic_and_formal_count_is_3240(self):
        ids = tuple(f"formal.synthetic.{i}" for i in range(162))
        first, second = balanced_schedule(ids, HASH), balanced_schedule(ids, HASH)
        self.assertEqual(first, second); self.assertEqual(len(first), 3240)
        self.assertEqual({item.system_condition for item in first[:4]}, set(M18_SYSTEMS))
        self.assertEqual({item.repetition for item in first}, set(range(1, 6)))

    def test_formal_manifest_uses_only_manifest_ids_and_validates_count(self):
        suite = {"manifest_hash":"m", "split_hash":"s"}; split = {"formal_ids":[f"formal.id.{i}" for i in range(162)]}
        manifest, specs = formal_manifest(HASH, suite, split)
        self.assertEqual((manifest.expected_run_count, len(specs), manifest.repetitions), (3240, 3240, 5))

class HarnessAdapterTests(unittest.TestCase):
    def _run(self, system, adapter):
        case = synthetic_case(); spec = M18RunSpec("m18_suite_v1", case.case_id, system, 1, HASH)
        return M18SharedExecutionHarness(HASH).run_synthetic(spec, case, adapter)

    def test_all_four_bindings_cross_one_shared_harness_and_keep_evaluator_separate(self):
        records = [
            self._run("mind_lite_v11", M18MINDAdapter(OneActionProvider())),
            self._run("direct_tool_calling", direct_adapter(OneActionProvider())),
            self._run("react", react_adapter(OneActionProvider())),
            self._run("plan_and_execute", plan_adapter(OnePlanProvider())),
        ]
        self.assertEqual({record.runtime_terminal_outcome for record in records}, {"answer_submitted"})
        self.assertEqual({record.evaluator_outcome for record in records}, {"wrong_answer"})
        self.assertEqual({record.neutral_failure_category for record in records}, {"wrong_answer"})
        self.assertTrue(all(record.provider_config_hash == HASH for record in records))

    def test_private_case_fields_never_reach_fake_provider_requests(self):
        class Capture:
            def __init__(self): self.requests=[]
            def generate(self, request): self.requests.append(request.to_dict()); return '{"action":"answer","answer":"x"}'
        provider = Capture(); self._run("direct_tool_calling", direct_adapter(provider))
        payload = json.dumps(provider.requests)
        for forbidden in ("target_answer", "failure_schedule", "difficulty", "evaluator_rule", "generation_seed"):
            self.assertNotIn(forbidden, payload)

    def test_neutral_failure_mapping(self):
        self.assertEqual(neutral_failure(M18RuntimeTerminal.BUDGET_EXHAUSTED, None), M18EvaluationCategory.BUDGET_EXHAUSTED)
        self.assertEqual(neutral_failure(M18RuntimeTerminal.PROVIDER_FAILURE, None), M18EvaluationCategory.PROVIDER_FAILURE)
        self.assertEqual(neutral_failure(M18RuntimeTerminal.ANSWER_SUBMITTED, M18EvaluationCategory.WRONG_ANSWER), M18EvaluationCategory.WRONG_ANSWER)

    def test_public_tool_observation_continues_to_a_second_decision(self):
        case = synthetic_case(); tool = case.public.tools[0]["tool_id"]
        for system, adapter in (
            ("mind_lite_v11", M18MINDAdapter(QueueActionProvider([f'{{"action":"tool_call","tool_name":"{tool}","parameters":{{}}}}', '{"action":"answer","answer":"x"}']))),
            ("direct_tool_calling", direct_adapter(QueueActionProvider([f'{{"action":"tool_call","tool_name":"{tool}","parameters":{{}}}}', '{"action":"answer","answer":"x"}']))),
            ("react", react_adapter(QueueActionProvider([f'{{"action":"tool_call","tool_name":"{tool}","parameters":{{}}}}', '{"action":"answer","answer":"x"}']))),
        ):
            with self.subTest(system=system):
                record = M18SharedExecutionHarness(HASH).run_synthetic(M18RunSpec("m18_suite_v1", case.case_id, system, 1, HASH), case, adapter)
                self.assertEqual(record.runtime_terminal_outcome, "answer_submitted")
                self.assertEqual(record.budget.logical_provider_calls, 2)
                self.assertGreaterEqual(record.budget.tool_calls, 1)

    def test_execution_manifest_freezes_provider_and_suite_identities(self):
        root = Path(__file__).resolve().parents[1]
        value = json.loads((root / "evaluation/m18/manifests/execution_harness_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(value["provider_config_hash"], HASH)
        self.assertEqual(value["expected_formal_run_count"], 3240)
        self.assertEqual(value["suite_manifest_hash"], "4eb3c8a1a4da0a17297bf26937db28b7d9fb33b9174e2f2128d14fd6fc6aec04")

    def test_plan_binding_preserves_planner_executor_and_observation_continuation(self):
        case = synthetic_case(); adapter = plan_adapter(ToolThenAnswerPlanProvider(case.public.tools[0]["tool_id"]))
        record = M18SharedExecutionHarness(HASH).run_synthetic(M18RunSpec("m18_suite_v1", case.case_id, "plan_and_execute", 1, HASH), case, adapter)
        self.assertEqual(record.runtime_terminal_outcome, "answer_submitted")
        self.assertEqual((record.budget.decision_cycles, record.budget.logical_provider_calls, record.budget.tool_calls), (2, 3, 1))

    def test_mind_uses_one_continuous_session_per_run_and_fresh_session_per_repetition(self):
        case = synthetic_case(); tool = case.public.tools[0]["tool_id"]
        first = M18MINDAdapter(QueueActionProvider([f'{{"action":"tool_call","tool_name":"{tool}","parameters":{{}}}}', '{"action":"answer","answer":"x"}']))
        harness = M18SharedExecutionHarness(HASH)
        harness.run_synthetic(M18RunSpec("m18_suite_v1", case.case_id, "mind_lite_v11", 1, HASH), case, first)
        first_session = first._session
        self.assertEqual(first_session.cycles_completed, 2)
        second = M18MINDAdapter(OneActionProvider())
        harness.run_synthetic(M18RunSpec("m18_suite_v1", case.case_id, "mind_lite_v11", 2, HASH), case, second)
        self.assertIsNot(first_session, second._session)

class FrozenProviderBindingTests(unittest.TestCase):
    def _client(self):
        return M18SharedProviderClient(http_post=lambda *args: {}, environment={"DEEPSEEK_API_KEY": "test-only"})
    def test_canonical_client_is_admitted_and_all_bindings_share_it(self):
        binding = M18FrozenProviderBinding(self._client())
        adapters = binding.adapters()
        self.assertEqual(set(adapters), set(M18_SYSTEMS))
        self.assertIs(adapters["mind_lite_v11"]._condition._provider.client, binding.client)
        self.assertTrue(all(adapters[key].provider_identity is binding.client for key in ("direct_tool_calling", "react", "plan_and_execute")))
        harness = M18SharedExecutionHarness(HASH, mode=M18ExecutionMode.FROZEN, frozen_binding=binding)
        self.assertIs(harness.frozen_binding, binding)
    def test_arbitrary_provider_and_every_semantic_configuration_drift_are_rejected(self):
        with self.assertRaises(TypeError): M18FrozenProviderBinding(OneActionProvider())
        for field, value in (("requested_model", "other"), ("temperature", 1), ("top_p", 0), ("thinking", {"type":"enabled"}), ("max_output_tokens", 513), ("response_format", {"type":"text"}), ("timeout_seconds_per_transport_attempt", 1), ("application_response_cache", "enabled"), ("base_url", "https://other")):
            with self.subTest(field=field), self.assertRaises(ValueError): M18SharedProviderConfiguration(**{field:value})
        with self.assertRaises(ValueError): M18SharedExecutionHarness(HASH, mode=M18ExecutionMode.FROZEN)
    def test_synthetic_mode_rejects_live_binding_and_keeps_fake_injection_explicit(self):
        binding = M18FrozenProviderBinding(self._client())
        with self.assertRaises(ValueError): M18SharedExecutionHarness(HASH, frozen_binding=binding)
        self.assertEqual(M18SharedExecutionHarness(HASH).mode, M18ExecutionMode.SYNTHETIC)

    def test_scripted_failure_paths_have_neutral_categories(self):
        case = generate_m18_case(M18Cohort.C, M18Difficulty.EASY, 990003, M18Namespace.PILOT, 0)
        tool = case.public.tools[0]["tool_id"]
        spec = M18RunSpec("m18_suite_v1", case.case_id, "direct_tool_calling", 1, HASH)
        invalid = M18SharedExecutionHarness(HASH).run_synthetic(spec, case, direct_adapter(OneActionProvider(f'{{"action":"tool_call","tool_name":"{tool}","parameters":{{}}}}')))
        self.assertEqual(invalid.neutral_failure_category, "invalid_action_exhausted")
        recovery_case = generate_m18_case(M18Cohort.C, M18Difficulty.EASY, 990004, M18Namespace.PILOT, 0)
        recovery_spec = M18RunSpec("m18_suite_v1", recovery_case.case_id, "direct_tool_calling", 1, HASH)
        recovering = M18SharedExecutionHarness(HASH).run_synthetic(recovery_spec, recovery_case, direct_adapter(QueueActionProvider([f'{{"action":"tool_call","tool_name":"{tool}","parameters":{{}}}}', '{"action":"answer","answer":"x"}'])))
        self.assertEqual(recovering.runtime_terminal_outcome, "answer_submitted")
        self.assertGreaterEqual(recovering.budget.recoverable_failures, 1)

    def test_provider_and_environment_invariant_failures_stay_distinct(self):
        case = synthetic_case(); spec = M18RunSpec("m18_suite_v1", case.case_id, "direct_tool_calling", 1, HASH)
        class BrokenProvider:
            def generate(self, request): raise RuntimeError("provider unavailable")
        provider_failure = M18SharedExecutionHarness(HASH).run_synthetic(spec, case, direct_adapter(BrokenProvider()))
        self.assertEqual(provider_failure.neutral_failure_category, "provider_failure")
        harness = M18SharedExecutionHarness(HASH); harness.environment.apply = lambda *args: (_ for _ in ()).throw(RuntimeError("environment invariant"))
        tool = case.public.tools[0]["tool_id"]
        infrastructure = harness.run_synthetic(spec, case, direct_adapter(OneActionProvider(f'{{"action":"tool_call","tool_name":"{tool}","parameters":{{}}}}')))
        self.assertEqual(infrastructure.neutral_failure_category, "infrastructure_invalid")

    def test_mind_shared_client_transport_accounting_reaches_record(self):
        response = {"model":"deepseek-flash","choices":[{"message":{"content":'{"action":"answer","answer":"x"}'}}],"usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}}
        client = M18SharedProviderClient(http_post=lambda *args: response, environment={"DEEPSEEK_API_KEY":"test"})
        case = synthetic_case(); spec = M18RunSpec("m18_suite_v1", case.case_id, "mind_lite_v11", 1, HASH)
        result = M18SharedExecutionHarness(HASH).run_synthetic(spec, case, M18MINDAdapter(M18SharedMINDProvider(client)))
        self.assertEqual((result.budget.logical_provider_calls, result.budget.transport_attempts), (1, 1))
        self.assertEqual(result.provider_model, "deepseek-flash")

    def test_frozen_environment_and_evaluator_invariant_breaches_are_typed_stops(self):
        answer = {"model":"deepseek-flash","choices":[{"message":{"content":'{"action":"answer","answer":"x"}'}}]}
        case = synthetic_case(); spec = M18RunSpec("m18_suite_v1", case.case_id, "mind_lite_v11", 1, HASH)
        client = M18SharedProviderClient(http_post=lambda *args: answer, environment={"DEEPSEEK_API_KEY":"test"})
        harness = M18SharedExecutionHarness(HASH, mode=M18ExecutionMode.FROZEN, frozen_binding=M18FrozenProviderBinding(client))
        harness.evaluator.evaluate = lambda *args: (_ for _ in ()).throw(RuntimeError("evaluator invariant"))
        with self.assertRaises(M18ExecutionIntegrityError) as raised:
            harness.run_frozen_pilot(spec, case)
        self.assertEqual(raised.exception.category, "evaluator_invariant_failure")
        tool = case.public.tools[0]["tool_id"]
        action = {"model":"deepseek-flash","choices":[{"message":{"content":f'{{"action":"tool_call","tool_name":"{tool}","parameters":{{}}}}'}}]}
        client = M18SharedProviderClient(http_post=lambda *args: action, environment={"DEEPSEEK_API_KEY":"test"})
        harness = M18SharedExecutionHarness(HASH, mode=M18ExecutionMode.FROZEN, frozen_binding=M18FrozenProviderBinding(client))
        harness.environment.apply = lambda *args: (_ for _ in ()).throw(RuntimeError("environment invariant"))
        with self.assertRaises(M18ExecutionIntegrityError) as raised:
            harness.run_frozen_pilot(spec, case)
        self.assertEqual(raised.exception.category, "environment_invariant_failure")

class PersistenceTests(unittest.TestCase):
    def manifest(self, hash=HASH): return M18HarnessManifest("m18_suite_v1", "suite", "split", hash, 5, "seed", 2, M18_SYSTEMS, harness_identity())
    def record(self, i=1):
        case = synthetic_case(); return M18SharedExecutionHarness(HASH).run_synthetic(M18RunSpec("m18_suite_v1", case.case_id, "direct_tool_calling", i, HASH), case, direct_adapter(OneActionProvider()))
    def test_atomic_duplicate_rejection_and_resume_missing_only(self):
        with TemporaryDirectory() as directory:
            store = M18ResultStore(Path(directory), self.manifest()); first, second = self.record(1), self.record(2)
            store.persist(first)
            with self.assertRaises(FileExistsError): store.persist(first)
            self.assertEqual(store.missing((M18RunSpec("m18_suite_v1", first.case_id, "direct_tool_calling", 1, HASH), M18RunSpec("m18_suite_v1", second.case_id, "direct_tool_calling", 2, HASH))), (M18RunSpec("m18_suite_v1", second.case_id, "direct_tool_calling", 2, HASH),))
            self.assertFalse(list(Path(directory).glob("*.tmp")))
    def test_configuration_drift_is_rejected(self):
        with TemporaryDirectory() as directory:
            M18ResultStore(Path(directory), self.manifest())
            with self.assertRaises(ValueError): M18ResultStore(Path(directory), self.manifest("b" * 64))

    def test_record_level_manifest_rejects_all_tampered_identity_fields_before_write(self):
        with TemporaryDirectory() as directory:
            record = self.record(); spec = M18RunSpec("m18_suite_v1", record.case_id, record.system_condition, record.repetition, HASH)
            manifest = M18HarnessManifest("m18_suite_v1", "suite", "split", HASH, 5, "seed", 1, M18_SYSTEMS, harness_identity(), experiment_namespace="m18_synthetic_v1", system_artifact_identities=M18_SYSTEM_ARTIFACTS)
            store = M18ResultStore(Path(directory), manifest, (spec,))
            store.persist(record)
            for changed in (replace(record, provider_config_hash="a" * 64), replace(record, system_artifact_identity="wrong"), replace(record, repetition=2), replace(record, run_id="wrong"), replace(record, harness_identity="wrong"), replace(record, result_schema_version="wrong")):
                with self.subTest(changed=changed), self.assertRaises(ValueError): store.persist(changed)
            foreign = replace(record, run_id="b" * 64, case_id="synthetic.nonmanifest")
            with self.assertRaises(ValueError): store.persist(foreign)
            self.assertEqual(store.completed_ids(), frozenset({record.run_id}))


if __name__ == "__main__": unittest.main()
