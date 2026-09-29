"""Provider-free tests for frozen prospective M20 execution configuration."""
import unittest
from dataclasses import replace

from src.evaluation.m20_harness import M20Condition
from src.evaluation.m20_real_case_source import real_case_source_digest
from src.evaluation.m20_real_execution_configuration import (
    M20FrozenProviderConfiguration, M20FrozenResourceCeiling, M20_REAL_PROVIDER_CONFIGURATION,
    M20_REAL_RESOURCE_CEILING, primary_condition_bindings,
)


class M20RealExecutionConfigurationTest(unittest.TestCase):
    def test_provider_identity_is_deterministic_and_sensitive(self):
        self.assertEqual(M20_REAL_PROVIDER_CONFIGURATION.identity_hash, M20_REAL_PROVIDER_CONFIGURATION.identity_hash)
        self.assertNotEqual(M20_REAL_PROVIDER_CONFIGURATION.identity_hash,
                            replace(M20_REAL_PROVIDER_CONFIGURATION, model="gpt-5.6-sol-next").identity_hash)
        with self.assertRaises(ValueError): replace(M20_REAL_PROVIDER_CONFIGURATION, model="")

    def test_secret_free_provider_and_ceiling_identity(self):
        self.assertFalse(any(item in M20_REAL_PROVIDER_CONFIGURATION.canonical() for item in ("api_key", "credential", "secret")))
        self.assertNotEqual(M20_REAL_RESOURCE_CEILING.identity_hash,
                            replace(M20_REAL_RESOURCE_CEILING, tool_attempts=5).identity_hash)
        with self.assertRaises(ValueError): M20FrozenResourceCeiling(0, 4, 4, 8)

    def test_primary_parity_and_case_source_binding(self):
        bindings = primary_condition_bindings()
        adaptive, fixed = bindings[M20Condition.MIND_ADAPTIVE], bindings[M20Condition.MIND_FIXED]
        self.assertEqual(adaptive, fixed)
        self.assertEqual(adaptive["case_source_digest"], real_case_source_digest())
        self.assertEqual(M20_REAL_RESOURCE_CEILING.canonical(), {"reasoning_steps": 8, "tool_attempts": 4,
                         "logical_provider_interactions": 4, "decision_cycles": 8,
                         "version": "m20_real_execution_configuration_v1"})


if __name__ == "__main__": unittest.main()
