"""Provider-free validation of the frozen M18 v3 suite universe."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.evaluation.m18_task_generation import canonical_hash
from src.evaluation.m18_v2_budget_diagnostic import (
    M18V2BudgetDiagnosticPlan, M18V2BudgetDiagnosticStore,
    M18_V2_BUDGET_DIAGNOSTIC_NAMESPACE,
)
from src.evaluation.m18_v2_pilot_runner import M18V2PilotPlan, M18V2PilotResultStore
from src.evaluation.m18_v3_pilot_runner import M18V3PilotPlan, M18V3PilotResultStore
from src.evaluation.m18_v3_runtime import M18V3SharedExecutionHarness, m18_v3_concrete_adapters
from src.evaluation.m18_v3_suite_freeze import SYSTEMS, build, cases, load_and_validate, write


class _PublicActionProvider:
    """Deterministic provider double that reads the public current action only."""
    transport_attempts_per_logical_call = 1

    @staticmethod
    def _context(request):
        value = request.to_dict()
        if "public_context" in value:
            return value["public_context"]["task"]["public_input"]["m18_v3_public_action_context"]
        return value["public_task"]["public_input"]["m18_v3_public_action_context"]

    def generate(self, request):
        context = self._context(request)
        action = context["current_action"]
        if action is None:
            return json.dumps({"action": "answer", "answer": context["state"]["current_value"]})
        return json.dumps({"action": "tool_call", "tool_name": action["tool_id"], "parameters": action["parameters"]})

    def plan(self, request):
        self._context(request)
        return json.dumps({"steps": [{"step_id": f"cycle-{index}", "subgoal": "perform one current public action", "capability_id": None} for index in range(6)]})

    def execute(self, request):
        return self.generate(request)


class M18V3SuiteFreezeTests(unittest.TestCase):
    def test_regeneration_split_hashes_and_full_suite_contract_are_deterministic(self):
        split_a, manifest_a, fixtures_a = build()
        split_b, manifest_b, fixtures_b = build()
        self.assertEqual((split_a, manifest_a, fixtures_a), (split_b, manifest_b, fixtures_b))
        self.assertEqual((len(split_a["pilot_ids"]), len(split_a["formal_ids"])), (18, 162))
        self.assertFalse(set(split_a["pilot_ids"]) & set(split_a["formal_ids"]))
        for scope, count in (("pilot", 18), ("formal", 162)):
            audit = manifest_a[scope]
            self.assertEqual(audit["reachable"], count)
            for key in ("uncovered_public_predicates", "stale_context_occurrences", "future_context_occurrences", "truth_leakage_occurrences", "tool_id_mismatches", "parameter_contract_mismatches"):
                self.assertEqual(audit[key], 0, f"{scope}:{key}")
            self.assertLessEqual(audit["max_action_cycles"], 6)
            self.assertLessEqual(audit["max_tool_attempts"], 4)
        self.assertEqual((manifest_a["pilot"]["run_count"], manifest_a["formal"]["run_count"]), (360, 3240))

    def test_all_four_real_adapters_consume_every_pilot_public_context(self):
        pilot, _ = cases()
        checks = 0
        for item in pilot:
            adapters = m18_v3_concrete_adapters({name: _PublicActionProvider() for name in SYSTEMS})
            for name, adapter in adapters.items():
                outcome = M18V3SharedExecutionHarness().dry_run(item, adapter)
                self.assertEqual(outcome.evaluator_outcome, "success", f"{item.case_id}:{name}")
                checks += 1
        self.assertEqual(checks, 72)

    def test_run_identity_domain_isolated_and_frozen_artifacts_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = write(root)
            self.assertEqual(load_and_validate(root), manifest)
        pilot, formal = cases()
        from src.evaluation.m18_v3_provenance import M18V3RunIdentity
        pilot_ids = {M18V3RunIdentity(item.case_id, system, repetition).run_id for item in pilot for system in SYSTEMS for repetition in range(1, 6)}
        formal_ids = {M18V3RunIdentity(item.case_id, system, repetition).run_id for item in formal for system in SYSTEMS for repetition in range(1, 6)}
        self.assertEqual((len(pilot_ids), len(formal_ids)), (360, 3240))
        self.assertFalse(pilot_ids & formal_ids)
        legacy = M18V2PilotPlan.from_repository(Path("."))
        diagnostic = M18V2BudgetDiagnosticPlan(legacy)
        self.assertFalse((pilot_ids | formal_ids) & {item.run_id for item in legacy.expected})
        self.assertFalse((pilot_ids | formal_ids) & set(diagnostic.run_ids))

    def test_historical_evidence_and_v3_real_namespaces_remain_untouched(self):
        """Protect a clean checkout while admitting only frozen evidence after execution.

        Before any authorized execution the reserved v3 namespaces are absent.
        Once the canonical pilot namespace exists, this test stays read-only and
        accepts it only when its store manifest and every record pass the frozen
        pilot admission contract, while the formal namespace remains empty.
        """
        pilot = M18V2PilotPlan.from_repository(Path("."))
        canonical = M18V2PilotResultStore(pilot.result_root, pilot.expected, pilot.suite_manifest)
        diagnostic = M18V2BudgetDiagnosticStore(Path(M18_V2_BUDGET_DIAGNOSTIC_NAMESPACE), M18V2BudgetDiagnosticPlan(pilot))
        self.assertEqual((len(canonical.records()), canonical.digest()), (360, "50caa6c9afaaf3712e10c5f75f397bb1f8306ebe12b0fd305a8f076a4a79473c"))
        ordered = [item.to_dict() for item in sorted(diagnostic.records(), key=lambda item: item.run_id)]
        self.assertEqual((len(ordered), canonical_hash(ordered)), (72, "2c2f3f52dfde996fba8b91e491297b7fdc7cc2f09425d3ba51595a06a0bbf0e2"))
        formal = Path("evaluation/m18/results/v3/formal")
        self.assertFalse(any(formal.glob("*.json")) if formal.exists() else False)
        root = Path("evaluation/m18/results/v3/pilot/m18_suite_v3")
        if not root.exists(): return
        v3 = M18V3PilotPlan.from_repository(Path("."))
        self.assertEqual(root.resolve(), v3.result_root.resolve())
        store = M18V3PilotResultStore(root, v3.expected, v3.manifest)
        self.assertTrue(store.manifest_path.exists())
        self.assertEqual(json.loads(store.manifest_path.read_text(encoding="utf-8")), store._store_manifest())
        records = store.records()
        self.assertEqual(len(records), len({record.run_id for record in records}))
        self.assertTrue(all(record.run_id in {item.run_id for item in v3.expected} for record in records))
