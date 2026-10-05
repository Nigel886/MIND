import unittest

from src.evaluation.m20_real_execution_configuration import (
    M20FrozenResourceCeilingV2, M20_REAL_RESOURCE_CEILING,
    M20_REAL_RESOURCE_CEILING_V2, primary_condition_bindings_v2,
    validate_m20_real_resource_ceiling_v2, validate_primary_condition_bindings_v2,
)


class M20ResourceCeilingV2Test(unittest.TestCase):
    def test_v1_is_immutable_and_v2_is_exact_deterministic(self):
        self.assertEqual(M20_REAL_RESOURCE_CEILING.identity,
                         "m20_real_ceiling_v1:6d497729bdb5d5fd87639a690b3d35064f8588e56268770ccbbecf143f5d1423")
        self.assertEqual((M20_REAL_RESOURCE_CEILING_V2.reasoning_steps,
                          M20_REAL_RESOURCE_CEILING_V2.tool_attempts,
                          M20_REAL_RESOURCE_CEILING_V2.logical_provider_interactions,
                          M20_REAL_RESOURCE_CEILING_V2.decision_cycles), (16, 8, 8, 8))
        self.assertEqual(M20_REAL_RESOURCE_CEILING_V2,
                         M20FrozenResourceCeilingV2(16, 8, 8, 8))
        validate_m20_real_resource_ceiling_v2(M20_REAL_RESOURCE_CEILING_V2)
        bindings = primary_condition_bindings_v2()
        validate_primary_condition_bindings_v2(bindings)
        self.assertEqual({item["resource_ceiling_identity"] for item in bindings.values()},
                         {M20_REAL_RESOURCE_CEILING_V2.identity})

    def test_v2_rejects_v1_and_all_altered_or_mixed_values(self):
        with self.assertRaises(ValueError):
            validate_m20_real_resource_ceiling_v2(M20_REAL_RESOURCE_CEILING)  # type: ignore[arg-type]
        for changed in ((15, 8, 8, 8), (16, 7, 8, 8), (16, 8, 7, 8), (16, 8, 8, 7)):
            with self.assertRaises(ValueError):
                validate_m20_real_resource_ceiling_v2(M20FrozenResourceCeilingV2(*changed))
        bindings = primary_condition_bindings_v2()
        first = next(iter(bindings)); bindings[first]["resource_ceiling_identity"] = "mixed"
        with self.assertRaises(ValueError): validate_primary_condition_bindings_v2(bindings)


if __name__ == "__main__": unittest.main()
