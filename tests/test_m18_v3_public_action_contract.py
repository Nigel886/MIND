"""Provider-free regression tests for the isolated M18 v3 contract."""
from __future__ import annotations

import json
import unittest

from src.evaluation.m18_task_generation import M18Cohort, M18Difficulty, M18Namespace
from src.evaluation.m18_v2_semantics import generate_m18_v2_case
from src.evaluation.m18_v2_semantics import M18V2Episode
from src.evaluation.m18_v3_runtime import M18V3ProviderCallGate, M18V3SharedExecutionHarness, m18_v3_concrete_adapters
from src.evaluation.contracts import EvaluationFeedback, EvaluationFeedbackType
from src.evaluation.m18_v3_semantics import M18V3Case, M18V3Episode, M18V2OutcomeCategory, M18_V3_PUBLIC_VALIDATION_MAPPING
from src.evaluation.m18_v3_provenance import M18V3RunIdentity
from src.evaluation.m18_v2_pilot_runner import M18V2PilotPlan
from src.evaluation.m18_v2_budget_diagnostic import M18V2BudgetDiagnosticPlan
from pathlib import Path


def case(cohort=M18Cohort.A, difficulty=M18Difficulty.EASY):
    return M18V3Case(generate_m18_v2_case(cohort, difficulty, 31, M18Namespace.PILOT, 1))


class _ActionProvider:
    """A fake that may read only the supplied public v3 context."""
    transport_attempts_per_logical_call = 1
    def __init__(self): self.requests=[]; self.contexts=[]
    @staticmethod
    def _context(request):
        data=request.to_dict()
        if "public_context" in data:
            root=data["public_context"]
            latest=root.get("latest_observation")
            if latest:
                payload=latest["content"]["environment_outcome"]["payload"]
                if "m18_v3_public_action_context" in payload:
                    return payload["m18_v3_public_action_context"]
            task=root["task"]["public_input"]
            return task["m18_v3_public_action_context"]
        return data["public_task"]["public_input"]["m18_v3_public_action_context"]
    def generate(self, request):
        self.requests.append(request.to_dict()); ctx=self._context(request); self.contexts.append(ctx); action=ctx["current_action"]
        # The final public value is provider-visible state, not evaluator truth.
        return json.dumps({"action":"answer","answer":ctx["state"]["current_value"]} if action is None else {"action":"tool_call","tool_name":action["tool_id"],"parameters":action["parameters"]})
    def plan(self, request):
        self.requests.append(request.to_dict()); ctx=self._context(request); self.contexts.append(ctx); action=ctx["current_action"]
        # A bounded generic public plan is intentionally capability-neutral:
        # concrete capability/parameter selection remains current-cycle only.
        return json.dumps({"steps":[{"step_id":f"cycle-{index}","subgoal":"perform one current public action","capability_id":None} for index in range(6)]})
    def execute(self, request): return self.generate(request)


class M18V3PublicActionContractTests(unittest.TestCase):
    def test_mind_replaces_active_context_and_preserves_feedback_as_history(self):
        provider=_ActionProvider()
        target=case(M18Cohort.A, M18Difficulty.HARD)
        result=M18V3SharedExecutionHarness().dry_run(target, m18_v3_concrete_adapters({
            "mind_lite_v11": provider, "direct_tool_calling": _ActionProvider(),
            "react": _ActionProvider(), "plan_and_execute": _ActionProvider(),
        })["mind_lite_v11"])
        self.assertEqual(result.evaluator_outcome, "success")
        prior_tool=None
        for request, current in zip(provider.requests, provider.contexts):
            root=request["public_context"]
            active=root["task"]["public_input"]
            self.assertEqual(set(active), {"m18_v3_public_action_context"})
            self.assertEqual(active["m18_v3_public_action_context"], current)
            latest=root["latest_observation"]
            if latest is not None:
                payload=latest["content"]["environment_outcome"]["payload"]
                self.assertEqual(set(payload), {"feedback"})
                self.assertNotIn("m18_v3_public_action_context", payload)
            tool=None if current["current_action"] is None else current["current_action"]["tool_id"]
            if prior_tool is not None and tool is not None:
                self.assertNotEqual(prior_tool, tool)
            prior_tool=tool

    def test_context_is_closed_and_current_only(self):
        episode=M18V3Episode(case()); context=episode.public_context().to_dict()
        self.assertEqual(set(context), {"case_id","task_text","state","current_action","capabilities","latest_feedback","budget"})
        self.assertNotIn("task_config", repr(context)); self.assertNotIn("expected_final_result", repr(context))
        current=context["current_action"]
        self.assertEqual(current["parameters"], {"value":context["state"]["current_value"]})
        self.assertTrue(current["available"])
        self.assertEqual(sum(item["available"] for item in context["capabilities"]), 1)
        self.assertEqual(len(context["capabilities"]), 1)

    def test_current_stable_id_and_exact_parameters_are_admitted(self):
        episode=M18V3Episode(case()); current=episode.public_context().current_action
        result=episode.submit_tool({"action":"tool_call","tool_name":current.tool_id,"parameters":current.parameters})
        self.assertEqual(result.category, M18V2OutcomeCategory.SUCCESS)

    def test_labels_stale_and_bad_parameters_are_rejected_without_future_leakage(self):
        episode=M18V3Episode(case()); current=episode.public_context().current_action
        label=episode.public_context().capabilities[0]["display_name"]
        self.assertEqual(episode.submit_tool({"action":"tool_call","tool_name":label,"parameters":current.parameters}).category, M18V2OutcomeCategory.INVALID_ACTION)
        episode=M18V3Episode(case()); current=episode.public_context().current_action
        self.assertEqual(episode.submit_tool({"action":"tool_call","tool_name":current.tool_id,"parameters":{}}).payload["reason"], "parameter_schema_violation")
        episode=M18V3Episode(case()); current=episode.public_context().current_action
        self.assertEqual(episode.submit_tool({"action":"tool_call","tool_name":current.tool_id,"parameters":{"value":current.parameters["value"],"extra":1}}).payload["reason"], "parameter_schema_violation")
        episode=M18V3Episode(case()); current=episode.public_context().current_action
        self.assertEqual(episode.submit_tool({"action":"tool_call","tool_name":current.tool_id,"parameters":{"value":current.parameters["value"]+1}}).payload["reason"], "parameter_value_not_current_public_state")

    def test_next_context_replaces_old_current_tool(self):
        episode=M18V3Episode(case()); first=episode.public_context().current_action
        self.assertEqual(episode.submit_tool({"action":"tool_call","tool_name":first.tool_id,"parameters":first.parameters}).category, M18V2OutcomeCategory.SUCCESS)
        later=episode.public_context().current_action
        self.assertNotEqual(first.tool_id, later.tool_id)
        self.assertNotIn(first.tool_id, {x["tool_id"] for x in episode.public_context().capabilities})
        stale=episode.submit_tool({"action":"tool_call","tool_name":first.tool_id,"parameters":first.parameters})
        self.assertEqual(stale.payload["reason"], "tool_not_currently_available")

    def test_budget_is_the_frozen_six_action_four_tool_contract(self):
        context=M18V3Episode(case()).public_context().to_dict()["budget"]
        self.assertEqual((context["max_action_cycles"], context["max_tool_attempts"]), (6, 4))

    def test_all_concrete_comparators_receive_the_same_public_context_shape(self):
        providers={key:_ActionProvider() for key in ("mind_lite_v11","direct_tool_calling","react","plan_and_execute")}
        adapters=m18_v3_concrete_adapters(providers); target=case(M18Cohort.B, M18Difficulty.EASY)
        for name, adapter in adapters.items():
            episode=M18V3Episode(target); adapter.initialize(target, episode)
            adapter.next_decision(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT), episode, M18V3ProviderCallGate(episode.budget_state))
            self.assertTrue(providers[name].requests, name)
            blob=repr(providers[name].requests)
            self.assertIn("m18_v3_public_action_context", blob)
            self.assertNotIn("expected_final_result", blob)
            self.assertNotIn("task_config", blob)
        first=[providers[name].contexts[0] for name in ("mind_lite_v11","direct_tool_calling","react","plan_and_execute")]
        self.assertTrue(all(value == first[0] for value in first[1:]))

    def test_provider_visible_contexts_enforce_the_truth_and_future_firewall(self):
        providers={key:_ActionProvider() for key in ("mind_lite_v11","direct_tool_calling","react","plan_and_execute")}
        target=case(M18Cohort.A, M18Difficulty.HARD)
        for adapter in m18_v3_concrete_adapters(providers).values():
            episode=M18V3Episode(target); adapter.initialize(target, episode)
            adapter.next_decision(EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT), episode, M18V3ProviderCallGate(episode.budget_state))
        forbidden=("expected_final_result", "task_config", "transformation_id", "failure_schedule", "ground_truth", "chain_of_thought", "hidden_reasoning", "credentials", "api_key")
        for provider in providers.values():
            blob=repr(provider.requests)
            for token in forbidden: self.assertNotIn(token, blob)

    def test_replay_is_deterministic(self):
        def replay():
            episode=M18V3Episode(case()); values=[]
            while episode.public_context().current_action is not None:
                action=episode.public_context().current_action
                values.append(episode.submit_tool({"action":"tool_call","tool_name":action.tool_id,"parameters":action.parameters}).to_dict())
            return values, episode.public_context().to_dict()
        self.assertEqual(replay(), replay())

    def test_provider_free_real_comparator_paths_reach_public_answer_boundary(self):
        target=case(M18Cohort.B, M18Difficulty.EASY)
        providers={key:_ActionProvider() for key in ("mind_lite_v11","direct_tool_calling","react","plan_and_execute")}
        for name, adapter in m18_v3_concrete_adapters(providers).items():
            result=M18V3SharedExecutionHarness().dry_run(target, adapter)
            self.assertEqual(result.terminal, "answer_submitted", name)
            self.assertEqual(result.evaluator_outcome, "success", name)

    def test_run_identity_is_version_domain_separated(self):
        item=M18V3RunIdentity("pilot.a", "direct_tool_calling", 1)
        self.assertTrue(item.run_id.startswith("m18v3-"))
        self.assertNotEqual(item.run_id, M18V3RunIdentity("pilot.a", "direct_tool_calling", 2).run_id)

    def test_v3_run_universe_is_unique_and_disjoint_from_v2_canonical_and_diagnostic(self):
        pilot=M18V2PilotPlan.from_repository(Path(".")); diagnostic=M18V2BudgetDiagnosticPlan(pilot)
        systems=("mind_lite_v11", "direct_tool_calling", "react", "plan_and_execute")
        ids={M18V3RunIdentity(case.case_id, system, repetition).run_id for case in pilot.cases for system in systems for repetition in range(1, 6)}
        self.assertEqual(len(ids), 360)
        self.assertFalse(ids & {item.run_id for item in pilot.expected})
        self.assertFalse(ids & set(diagnostic.run_ids))

    def test_all_environment_validation_predicates_have_public_context_mapping(self):
        expected={"unsupported_public_action", "interaction_already_complete", "unknown_stable_tool_id", "tool_not_currently_available", "parameter_schema_violation", "parameter_value_not_current_public_state"}
        self.assertEqual(set(M18_V3_PUBLIC_VALIDATION_MAPPING), expected)

    def test_v3_corrects_the_v2_missing_context_rejection_without_mutating_v2(self):
        legacy=generate_m18_v2_case(M18Cohort.A, M18Difficulty.EASY, 31, M18Namespace.PILOT, 1)
        # This is exactly the former task-text-only decision shape: it has no
        # public current value and v2 must continue to reject it.
        self.assertEqual(M18V2Episode(legacy).submit_tool({"action":"tool_call", "tool_name":legacy.public.to_dict()["capabilities"][0]["tool_id"], "parameters":{}}).category, M18V2OutcomeCategory.INVALID_ACTION)
        corrected=M18V3Episode(M18V3Case(legacy)); action=corrected.public_context().current_action
        self.assertEqual(corrected.submit_tool({"action":"tool_call", "tool_name":action.tool_id, "parameters":action.parameters}).category, M18V2OutcomeCategory.SUCCESS)

    def test_representative_four_comparator_matrix_is_provider_free_and_public_only(self):
        # Every required representative structure uses the actual
        # adapter/runtime boundary, but only this local deterministic provider.
        structures=((M18Cohort.A, M18Difficulty.EASY, None),
                    (M18Cohort.A, M18Difficulty.MEDIUM, None),
                    (M18Cohort.A, M18Difficulty.HARD, None),
                    (M18Cohort.B, M18Difficulty.EASY, None),
                    (M18Cohort.C, M18Difficulty.EASY, 2),
                    (M18Cohort.C, M18Difficulty.EASY, 1))
        for cohort, difficulty, seed in structures:
            target=case(cohort, difficulty) if seed is None else M18V3Case(generate_m18_v2_case(cohort, difficulty, seed, M18Namespace.PILOT, 1))
            providers={key:_ActionProvider() for key in ("mind_lite_v11","direct_tool_calling","react","plan_and_execute")}
            for name, adapter in m18_v3_concrete_adapters(providers).items():
                result=M18V3SharedExecutionHarness().dry_run(target, adapter)
                self.assertEqual(result.terminal, "answer_submitted", name)
                self.assertEqual(result.evaluator_outcome, "success", name)
                self.assertNotIn("expected_final_result", repr(providers[name].requests))
