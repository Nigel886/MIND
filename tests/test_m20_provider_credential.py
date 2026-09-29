import unittest
from src.evaluation.m20_provider_credential import M20_PROVIDER_CREDENTIAL_ENV, credential_status, require_credential

class M20ProviderCredentialTest(unittest.TestCase):
 def test_absent_empty_and_present_are_secret_safe(self):
  self.assertEqual(credential_status({}), "CREDENTIAL NOT READY")
  self.assertEqual(credential_status({M20_PROVIDER_CREDENTIAL_ENV:"  "}), "CREDENTIAL NOT READY")
  secret="dummy-secret-for-test-only"
  self.assertEqual(credential_status({M20_PROVIDER_CREDENTIAL_ENV:secret}), "CREDENTIAL READY")
  with self.assertRaises(RuntimeError) as error: require_credential({})
  self.assertNotIn(secret, str(error.exception))
if __name__ == "__main__": unittest.main()
