import hashlib
import unittest
from pathlib import Path

from src.evaluation.m16_failure_mechanism_audit import synthetic_matrix, visible_formal_pattern, write_audit_outputs


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation/results/m16_deepseek_v4_flash_restart1"


class M16FailureMechanismAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = {row["candidate"]: row for row in synthetic_matrix()}

    def test_candidate_fail_branches_map_to_agent_fail(self) -> None:
        for candidate in ("provider_interpreter_failure", "malformed_structured_proposal", "proposal_validation_failure", "meta_inference_nonselection", "private_session_max_cycles", "private_policy_failure_not_m16_eligible"):
            self.assertEqual(self.rows[candidate]["runner_category_if_terminal"], "agent_fail")
            self.assertEqual(self.rows[candidate]["action_type"], "fail")

    def test_valid_direct_answer_reaches_non_fail_action(self) -> None:
        row = self.rows["valid_direct_answer"]
        self.assertEqual((row["integration_selected"], row["action_type"]), ("true", "answer"))

    def test_valid_calculator_reaches_tool_boundary(self) -> None:
        row = self.rows["valid_calculator"]
        self.assertEqual((row["integration_selected"], row["action_type"], row["evaluator_boundary"]), ("true", "tool_call", "tool_response"))

    def test_provider_compatible_valid_proposal_and_semantic_failures_are_distinct(self) -> None:
        self.assertEqual(self.rows["valid_direct_answer"]["provider_calls"], 1)
        self.assertEqual(self.rows["malformed_structured_proposal"]["provider_calls"], 1)
        self.assertEqual(self.rows["proposal_validation_failure"]["provider_calls"], 1)
        self.assertNotEqual(self.rows["valid_direct_answer"]["action_type"], self.rows["proposal_validation_failure"]["action_type"])

    def test_visible_pattern_is_public_and_uniform(self) -> None:
        pattern = visible_formal_pattern(RESULTS)
        self.assertEqual(sum(row["count"] for row in pattern), 480)
        self.assertTrue(all((row["failure_category"], row["agent_steps"], row["tool_calls"], row["provider_request_attempts"], row["model_calls"]) == ("agent_fail", 1, 0, 1, 1) for row in pattern))

    def test_audit_output_does_not_modify_raw_records(self) -> None:
        raw = RESULTS / "formal_run_attempts_v1.jsonl"; before = hashlib.sha256(raw.read_bytes()).hexdigest()
        write_audit_outputs(RESULTS, ROOT / "evaluation/analysis/m16_mind_failure_audit")
        self.assertEqual(before, hashlib.sha256(raw.read_bytes()).hexdigest())
