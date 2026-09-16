"""Provider-free infrastructure tests for the M18 v2 pilot-only runner."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.evaluation.m18_v2_pilot_runner import (
    M18V2PilotIntegrityError, M18V2PilotPlan, M18V2PilotResultStore,
    M18V2PilotRunner, main,
)


class FakeProvider:
    """Returns valid terminal output without reading evaluator-owned fixture data."""
    transport_attempts_per_logical_call = 1

    def __init__(self, system: str, ledger: dict[str, list[dict]]) -> None:
        self.system, self.ledger = system, ledger

    def generate(self, request):
        value = request.to_dict()
        self.ledger[self.system].append(value)
        return json.dumps({"action": "answer", "answer": 0}, separators=(",", ":"))

    def plan(self, request):
        value = request.to_dict()
        self.ledger[self.system].append(value)
        tool_id = value["capabilities"][0]["tool_id"]
        return json.dumps({"steps": [{"step_id": "s0", "subgoal": "public", "capability_id": tool_id}]}, separators=(",", ":"))

    def execute(self, request):
        self.ledger[self.system].append(request.to_dict())
        return json.dumps({"action": "answer", "answer": 0}, separators=(",", ":"))


class M18V2PilotRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = M18V2PilotPlan.from_repository(Path("."))

    def runner(self, root: Path):
        return M18V2PilotRunner(self.plan, result_root=root)

    @staticmethod
    def factory(ledger):
        return lambda system: FakeProvider(system, ledger)

    def test_frozen_plan_is_pilot_only_and_has_ordered_360_universe(self):
        self.assertEqual(len(self.plan.cases), 18)
        self.assertEqual(len(self.plan.expected), len({item.run_id for item in self.plan.expected}), 360)
        self.assertEqual([item.identity.repetition for item in self.plan.expected[:5]], [1, 2, 3, 4, 5])
        self.assertTrue(all(item.identity.case_id.startswith("pilot.") for item in self.plan.expected))

    def test_dry_run_is_provider_free_and_does_not_create_namespace(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "pilot"
            summary = self.runner(root).dry_run()
            self.assertEqual((summary.expected, summary.valid_existing, summary.missing), (360, 0, 360))
            self.assertEqual(summary.per_comparator, {"mind_lite_v11": 90, "direct_tool_calling": 90, "react": 90, "plan_and_execute": 90})
            self.assertEqual(summary.per_repetition, {1: 72, 2: 72, 3: 72, 4: 72, 5: 72})
            self.assertFalse(root.exists())

    def test_full_fake_lifecycle_persists_and_rereads_all_concrete_adapters(self):
        with TemporaryDirectory() as directory:
            ledger = {key: [] for key in self.plan.suite_manifest["comparator_conditions"]}
            runner = self.runner(Path(directory) / "pilot")
            records = runner.execute(provider_factory=self.factory(ledger))
            self.assertEqual(len(records), 360)
            reread = runner.store.records()
            self.assertEqual(len(reread), 360)
            self.assertEqual(len(runner.store.missing()), 0)
            self.assertEqual({key: len(value) for key, value in ledger.items()}, {"mind_lite_v11": 90, "direct_tool_calling": 90, "react": 90, "plan_and_execute": 180})
            self.assertTrue(all("expected_final_result" not in str(request) for values in ledger.values() for request in values))
            self.assertEqual(len({record.provenance.identity.case_id for record in reread}), 18)
            self.assertEqual({record.provenance.identity.repetition for record in reread}, {1, 2, 3, 4, 5})
            self.assertEqual({record.provenance.identity.comparator_condition_id for record in reread}, set(self.plan.suite_manifest["comparator_conditions"].values()))
            self.assertEqual(runner.store.digest(), M18V2PilotResultStore(runner.result_root, self.plan.expected, self.plan.suite_manifest).digest())

    def test_missing_only_resume_and_pre_post_commit_interruption(self):
        with TemporaryDirectory() as directory:
            ledger = {key: [] for key in self.plan.suite_manifest["comparator_conditions"]}
            runner = self.runner(Path(directory) / "pilot")
            runner.execute(provider_factory=self.factory(ledger), limit=7)
            self.assertEqual(len(runner.store.records()), 7)
            with self.assertRaisesRegex(RuntimeError, "after commit"):
                runner.execute(provider_factory=self.factory(ledger), limit=1,
                               after_persist=lambda _: (_ for _ in ()).throw(RuntimeError("after commit")))
            self.assertEqual(len(runner.store.records()), 8)
            runner.execute(provider_factory=self.factory(ledger))
            self.assertEqual(len(runner.store.records()), 360)

    def test_invalid_duplicate_and_unexpected_records_fail_closed(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "pilot"; ledger = {key: [] for key in self.plan.suite_manifest["comparator_conditions"]}
            runner = self.runner(root); runner.execute(provider_factory=self.factory(ledger), limit=1)
            record = runner.store.records()[0]
            with self.assertRaises(M18V2PilotIntegrityError): runner.store.persist(record)
            payload = record.to_dict(); payload["provenance"]["case_id"] = "pilot.tampered"
            (root / "tampered.json").write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(M18V2PilotIntegrityError): runner.store.records()

    def test_cli_guard_rejects_formal_and_defaults_to_provider_free_dry_run(self):
        with TemporaryDirectory() as directory:
            self.assertEqual(main(["--result-root", directory]), 0)
            with self.assertRaises(SystemExit): main(["--split", "formal", "--execute"])
            with self.assertRaises(SystemExit): main(["--suite", "m18_suite_v1", "--execute"])


if __name__ == "__main__":
    unittest.main()
