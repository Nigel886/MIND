"""Provider-free validation for the prospective M20 real case source."""
import unittest
from src.evaluation.m20_real_case_source import (
    M20_REAL_COHORTS, M20_REAL_CASE_REPETITIONS, M20RealEnvironment, M20RealEvaluator,
    M20RealCaseDefinition, M20RealProviderConfiguration, M20RealResourceCeiling, real_case_definitions,
    real_case_source_digest, validate_real_case_definitions,
)
from src.evaluation.m20_harness import M20Outcome, M20Proposal, M20ProposalKind


class M20RealCaseSourceTest(unittest.TestCase):
    def test_complete_deterministic_diverse_universe(self):
        first, second = real_case_definitions(), real_case_definitions()
        self.assertEqual(first, second); self.assertEqual(len(first), 12)
        self.assertEqual({item.cohort for item in first}, set(M20_REAL_COHORTS))
        self.assertEqual(len({item.case_id for item in first}), len(first))
        self.assertEqual(len({item.payload_digest for item in first}), len(first))
        self.assertEqual((M20_REAL_CASE_REPETITIONS, real_case_source_digest()), (5, real_case_source_digest()))

    def test_private_witness_is_reachable_but_not_public(self):
        environment, evaluator = M20RealEnvironment(), M20RealEvaluator()
        for definition in real_case_definitions():
            case, state = definition.to_case(), environment.initial_public_state(definition.to_case().public)
            self.assertNotIn(definition.target, str(case.public.to_dict()))
            for raw in definition.witness:
                if raw["kind"] == "answer": outcome = evaluator.evaluate(case, state, raw["payload"])
                else: state = environment.apply(case.public, state, M20Proposal(M20ProposalKind(raw["kind"]), raw["action_id"])).state
            self.assertEqual(outcome, M20Outcome.SUCCESS)

    def test_provider_and_ceiling_identity_are_canonical_and_secret_free(self):
        config = M20RealProviderConfiguration("provider", "model", "api", "deterministic", 0, None, None, 64, "json", "tools", 30, "provider_client", 1, 7)
        changed = M20RealProviderConfiguration("provider", "model-v2", "api", "deterministic", 0, None, None, 64, "json", "tools", 30, "provider_client", 1, 7)
        self.assertNotEqual(config.identity_hash, changed.identity_hash)
        ceiling = M20RealResourceCeiling("ceiling", 2, 2, 2, 2)
        self.assertEqual(ceiling.digest, ceiling.digest)

    def test_duplicate_and_unreachable_eligible_cases_fail_closed(self):
        values = real_case_definitions()
        with self.assertRaises(ValueError): validate_real_case_definitions(values + (values[0],))
        bad = M20RealCaseDefinition("m20.real.multi_step_stateful.bad", "multi_step_stateful", "bad",
            {"task": "bad", "progress": 0, "required_progress": 1, "requires_observation": False, "requires_recovery": False},
            {"advance": {"schema": {}, "effect": "advance"}}, "target", ({"kind": "answer", "payload": "target"},), {"authorship": "test"})
        with self.assertRaises(ValueError): validate_real_case_definitions(tuple(item for item in values if item.cohort != "multi_step_stateful") + (bad,))
        excluded = M20RealCaseDefinition("m20.real.multi_step_stateful.excluded", "multi_step_stateful", "excluded",
            bad.initial_state, bad.actions, bad.target, bad.witness, {"authorship": "test"}, False, "unreachable_by_prospective_validation")
        self.assertFalse(excluded.eligible)


if __name__ == "__main__": unittest.main()
