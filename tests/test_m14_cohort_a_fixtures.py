"""Tests for frozen M14 Cohort A fixture registrations."""

from __future__ import annotations

import unittest

from evaluation.tasks.m14_cohort_a_fixtures import (
    get_m14_cohort_a_fixtures,
    get_m14_cohort_a_suite_metadata,
)
from src.evaluation.cohort_a import (
    M14CohortADifficulty,
    M14CohortATaskCategory,
    M14CohortATaskFixture,
    fixture_suite_hash,
)


class M14CohortAFixtureTests(unittest.TestCase):
    def test_fixtures_are_ordered_and_deterministic(self) -> None:
        first = get_m14_cohort_a_fixtures()
        second = get_m14_cohort_a_fixtures()

        self.assertEqual(
            [fixture.task_id for fixture in first],
            [
                "m14-direct-ready",
                "m14-calculator-multiply",
                "m14-unsupported-operation",
                "m14-declared-tool-failure",
            ],
        )
        self.assertEqual(first, second)
        self.assertEqual(fixture_suite_hash(first), fixture_suite_hash(second))

    def test_fixture_serialization_round_trip(self) -> None:
        fixture = get_m14_cohort_a_fixtures()[0]

        restored = M14CohortATaskFixture.from_dict(fixture.to_dict())

        self.assertEqual(restored, fixture)

    def test_suite_hash_changes_with_registered_input(self) -> None:
        fixtures = get_m14_cohort_a_fixtures()
        altered_data = fixtures[0].to_dict()
        altered_data["budget"]["max_steps"] = 2
        altered = M14CohortATaskFixture.from_dict(altered_data)

        self.assertNotEqual(fixture_suite_hash(fixtures), fixture_suite_hash((altered,) + fixtures[1:]))

    def test_supported_categories_and_difficulties_are_closed_enums(self) -> None:
        self.assertEqual(M14CohortATaskCategory.MULTI_STEP_DEPENDENCY_TASK.value, "multi_step_dependency_task")
        self.assertEqual(M14CohortATaskCategory.FAILURE_RECOVERY_TASK.value, "failure_recovery_task")
        self.assertEqual(
            {item.value for item in M14CohortADifficulty},
            {"easy", "medium", "hard"},
        )

    def test_fixture_detaches_caller_owned_nested_definition(self) -> None:
        source = get_m14_cohort_a_fixtures()[0].to_dict()
        fixture = M14CohortATaskFixture.from_dict(source)
        source["task_definition"]["case"]["environment_config"]["environment_id"] = "changed"

        self.assertEqual(fixture.task_definition["case"]["environment_config"]["environment_id"], "m14-direct-v1")

    def test_suite_metadata_is_stable(self) -> None:
        metadata = get_m14_cohort_a_suite_metadata()

        self.assertEqual(metadata["suite_id"], "m14-cohort-a")
        self.assertEqual(metadata["suite_version"], "1.0.0")
        self.assertEqual(len(metadata["suite_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
