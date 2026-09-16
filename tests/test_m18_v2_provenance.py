"""Provider-free identity and admission tests for future M18 v2 records."""
from __future__ import annotations

import unittest

from src.evaluation.m18_execution_harness import M18RunSpec
from src.evaluation.m18_suite_freeze import formal_suite, pilot_suite
from src.evaluation.m18_v2_provenance import (
    M18V2ResultAdmission,
    M18V2ResultRecord,
    M18V2RunIdentity,
    M18V2RunProvenance,
    M18_V2_COMPARATOR_CONDITIONS,
    M18_V2_REPETITIONS,
    comparator_condition_for_system,
    derive_m18_v2_run_id,
    project_m18_v2_run_provenances,
)
from src.evaluation.m18_v2_semantics import (
    M18_V2_BUDGET_ID,
    M18_V2_ENVIRONMENT_ID,
    M18_V2_EVALUATOR_ID,
    M18_V2_SUITE_VERSION,
)
from src.evaluation.m18_pilot_execution import (
    M18OperationalStopCategory,
    M18OperationalStopCondition,
)


HASH = "c" * 64
BASELINE = "candidate_execution_baseline"


def provenance(
    case_id: str = "pilot.multi_step.easy.1.0",
    comparator: str = "mind_lite_v11",
    repetition: int = 1,
) -> M18V2RunProvenance:
    return M18V2RunProvenance(
        M18V2RunIdentity(
            M18_V2_SUITE_VERSION, case_id,
            comparator_condition_for_system(comparator), repetition,
        ),
        M18_V2_ENVIRONMENT_ID, M18_V2_EVALUATOR_ID, M18_V2_BUDGET_ID,
        "m18_shared_execution_runtime_v2", HASH, BASELINE,
    )


def record(value: M18V2RunProvenance) -> M18V2ResultRecord:
    return M18V2ResultRecord(
        value, "success", None,
        {"logical_provider_calls": 2, "transport_attempts": 2},
        {"prompt_tokens": 1, "completion_tokens": 1, "latency_ms": 1},
    )


class M18V2ProvenanceTests(unittest.TestCase):
    def test_typed_identity_is_deterministic_and_repetition_is_explicit(self):
        first = provenance()
        second = M18V2RunProvenance.from_dict(first.to_dict())
        self.assertEqual(first, second)
        self.assertEqual(first.run_id, second.run_id)
        self.assertNotEqual(first.run_id, provenance(repetition=2).run_id)
        self.assertEqual(first.to_dict()["repetition"], 1)
        self.assertEqual(first.run_id, M18V2RunProvenance(
            first.identity, first.environment_id, first.evaluator_id, first.budget_id,
            first.runtime_id, first.provider_config_hash, "later_delivery_commit",
        ).run_id)

    def test_canonical_tuple_prevents_ambiguous_field_concatenation(self):
        self.assertNotEqual(
            derive_m18_v2_run_id("m18_suite_v2", "ab", "c", 1),
            derive_m18_v2_run_id("m18_suite_v2", "a", "bc", 1),
        )
        self.assertNotEqual(
            derive_m18_v2_run_id("m18_suite_v1", "case", "direct", 1),
            derive_m18_v2_run_id("m18_suite_v2", "case", "direct", 1),
        )

    def test_case_comparator_and_suite_changes_do_not_collide(self):
        base = provenance()
        self.assertNotEqual(base.run_id, provenance(case_id="pilot.multi_step.easy.2.0").run_id)
        self.assertNotEqual(base.run_id, provenance(comparator="direct_tool_calling").run_id)
        self.assertNotEqual(
            base.run_id,
            derive_m18_v2_run_id("m18_suite_v1", base.identity.case_id,
                                 base.identity.comparator_condition_id, 1),
        )

    def test_record_admission_recomputes_identity_and_rejects_tampering(self):
        value = provenance()
        admitted = M18V2ResultAdmission((value,))
        admitted.admit(record(value))
        self.assertEqual(admitted.completed_ids(), frozenset({value.run_id}))
        with self.assertRaises(M18OperationalStopCondition) as error:
            admitted.admit(record(value))
        self.assertEqual(error.exception.event.category, M18OperationalStopCategory.PROVENANCE_INTEGRITY_FAILURE)
        for key, changed in (("run_id", "0" * 64), ("repetition", 2), ("case_id", "other"),
                             ("suite_identity", "m18_suite_v1"),
                             ("comparator_condition_id", "not_a_condition"),
                             ("environment_id", "m18_environment_v1"),
                             ("evaluator_id", "m18_evaluator_v1"),
                             ("budget_id", "m18_budget_v1"),
                             ("runtime_id", "m18_runtime_v1"),
                             ("provider_config_hash", "d" * 64)):
            with self.subTest(key=key):
                payload = record(value).to_dict()
                payload["provenance"][key] = changed
                if key in {"run_id", "repetition"}:
                    payload[key] = changed
                if key == "provider_config_hash":
                    parsed = M18V2ResultRecord.from_dict(payload)
                    with self.assertRaises(M18OperationalStopCondition):
                        M18V2ResultAdmission((value,)).admit(parsed)
                else:
                    with self.assertRaises(ValueError):
                        M18V2ResultRecord.from_dict(payload)

    def test_resume_uses_admitted_records_not_filenames(self):
        first, second = provenance(), provenance(repetition=2)
        admission = M18V2ResultAdmission((first, second))
        self.assertEqual(admission.missing(), (first, second))
        admission.admit(record(first))
        self.assertEqual(admission.missing(), (second,))
        with self.assertRaises(ValueError):
            M18V2ResultAdmission((first, first))

    def test_all_comparators_share_the_same_identity_derivation(self):
        ids = {
            provenance(comparator=system).run_id
            for system in M18_V2_COMPARATOR_CONDITIONS
        }
        self.assertEqual(len(ids), 4)
        self.assertEqual(
            {provenance(comparator=system).identity.comparator_condition_id
             for system in M18_V2_COMPARATOR_CONDITIONS},
            set(M18_V2_COMPARATOR_CONDITIONS.values()),
        )

    def test_candidate_pilot_and_formal_identity_projections_are_unique(self):
        conditions = tuple(M18_V2_COMPARATOR_CONDITIONS.values())
        pilot = project_m18_v2_run_provenances(
            (item.case_id for item in pilot_suite()), conditions, HASH, BASELINE,
        )
        formal = project_m18_v2_run_provenances(
            (item.case_id for item in formal_suite()), conditions, HASH, BASELINE,
        )
        pilot_ids, formal_ids = {item.run_id for item in pilot}, {item.run_id for item in formal}
        self.assertEqual((len(pilot), len(pilot_ids)), (18 * 4 * M18_V2_REPETITIONS,) * 2)
        self.assertEqual((len(formal), len(formal_ids)), (162 * 4 * M18_V2_REPETITIONS,) * 2)
        self.assertFalse(pilot_ids & formal_ids)

    def test_no_collision_with_derived_historical_v1_run_ids(self):
        projected = project_m18_v2_run_provenances(
            (item.case_id for item in pilot_suite()),
            tuple(M18_V2_COMPARATOR_CONDITIONS.values()), HASH, BASELINE,
        )
        v2_ids = {item.run_id for item in projected}
        v1_ids = {
            M18RunSpec("m18_suite_v1", item.case_id, system, repetition, HASH).run_id
            for item in pilot_suite()
            for system in M18_V2_COMPARATOR_CONDITIONS
            for repetition in range(1, M18_V2_REPETITIONS + 1)
        }
        self.assertFalse(v2_ids & v1_ids)


if __name__ == "__main__":
    unittest.main()
