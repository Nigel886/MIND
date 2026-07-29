"""Tests for the runtime benchmark development utility."""

from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from benchmark import runtime_benchmark as module
from benchmark.runtime_benchmark import (
    RuntimeBenchmarkConfig,
    RuntimeBenchmarkResult,
    run_runtime_benchmark,
)
from src.core.runtime import RuntimeController


class BenchmarkConfigTest(unittest.TestCase):
    def _valid(self, **changes: object) -> RuntimeBenchmarkConfig:
        data: dict[str, object] = {
            "scenario": "bounded_runtime", "repeats": 2, "max_cycles": 2,
            "observation_content": {"nested": {"items": [1, 2]}},
            "metadata": {"nested": {"items": ["a"]}},
        }
        data.update(changes)
        return RuntimeBenchmarkConfig(**data)

    def test_validation_rejects_invalid_public_values(self) -> None:
        for value in (True, False, 1, None):
            if isinstance(value, int) and not isinstance(value, bool):
                continue
            with self.assertRaises(TypeError):
                self._valid(scenario=value)
        with self.assertRaises(ValueError):
            self._valid(scenario="unknown")
        for field in ("repeats", "max_cycles"):
            for value in (True, False, 1.0, "1", None):
                with self.assertRaises(TypeError):
                    self._valid(**{field: value})
            for value in (0, -1):
                with self.assertRaises(ValueError):
                    self._valid(**{field: value})
        with self.assertRaises(ValueError):
            self._valid(scenario="single_cycle", max_cycles=2)
        for field in ("observation_content", "metadata"):
            with self.assertRaises(TypeError):
                self._valid(**{field: []})

    def test_config_defensively_copies_nested_inputs_and_round_trips(self) -> None:
        content = {"id": "payload", "nested": {"items": [1]}}
        metadata = {"timestamp": "payload", "nested": {"items": ["x"]}}
        config = self._valid(observation_content=content, metadata=metadata)
        snapshot = config.to_dict()
        content["nested"]["items"].append(2)
        metadata["nested"]["items"].append("y")

        self.assertEqual(config.to_dict(), snapshot)
        self.assertEqual(RuntimeBenchmarkConfig.from_dict(snapshot).to_dict(), snapshot)


class RuntimeBenchmarkTest(unittest.TestCase):
    def _config(self, scenario: str = "bounded_runtime", **changes: object) -> RuntimeBenchmarkConfig:
        data: dict[str, object] = {
            "scenario": scenario, "repeats": 3,
            "max_cycles": 1 if scenario == "single_cycle" else 2,
            "observation_content": {"id": "user-id", "timestamp": "user-time", "nested": [1]},
            "metadata": {"phase": "benchmark", "nested": {"value": True}},
        }
        data.update(changes)
        return RuntimeBenchmarkConfig(**data)

    def test_single_cycle_reports_real_runtime_semantics(self) -> None:
        result = run_runtime_benchmark(self._config("single_cycle"))

        self.assertEqual(result.repeats_completed, 3)
        self.assertEqual(len(result.durations_seconds), 3)
        self.assertTrue(all(isinstance(value, float) and value >= 0 for value in result.durations_seconds))
        self.assertEqual(result.initial_belief_version, 0)
        self.assertEqual(result.final_belief_versions, (1, 1, 1))
        self.assertEqual(result.final_observation_sources, ("action_executor",) * 3)
        self.assertEqual(result.final_actions, ("maintain_belief",) * 3)
        self.assertTrue(result.semantically_deterministic)
        self.assertEqual(result.semantic_mismatch_count, 0)
        self.assertEqual(set(result.environment), {
            "python_version", "python_implementation", "platform_system",
            "platform_release", "benchmark_timestamp",
        })

    def test_bounded_runtime_uses_fresh_inputs_and_preserves_config(self) -> None:
        config = self._config(repeats=3, max_cycles=2)
        snapshot = deepcopy(config.to_dict())
        seen: list[tuple[object, object]] = []
        original = RuntimeController.run

        def record(state: object, observation: object, max_cycles: int) -> object:
            seen.append((state, observation))
            return original(state, observation, max_cycles)

        with patch.object(RuntimeController, "run", side_effect=record):
            result = run_runtime_benchmark(config)

        self.assertEqual(result.final_belief_versions, (2, 2, 2))
        self.assertEqual(len({id(pair[0]) for pair in seen}), 3)
        self.assertEqual(len({id(pair[1]) for pair in seen}), 3)
        self.assertEqual(len({pair[1].id for pair in seen}), 3)
        self.assertEqual(config.to_dict(), snapshot)
        self.assertEqual(result.semantic_mismatch_count, 0)
        self.assertEqual(
            result.semantic_signatures[0]["belief"]["state"]["observation:runtime_benchmark"]["evidence"][0]["content"]["id"],
            "user-id",
        )

    def test_normalization_preserves_user_payload_identity_keys(self) -> None:
        first = {
            "observation": {"id": "model-a", "timestamp": "a", "source": "x", "content": {"id": "user", "timestamp": "value"}},
            "belief": {"state": {}, "confidence": {}, "version": 1},
            "metadata": {"id": "metadata"},
        }
        second = deepcopy(first)
        second["observation"]["id"] = "model-b"
        second["observation"]["timestamp"] = "b"
        self.assertEqual(module._normalize_final_state(first), module._normalize_final_state(second))
        changed = deepcopy(second)
        changed["observation"]["content"]["id"] = "other"
        self.assertNotEqual(module._normalize_final_state(first), module._normalize_final_state(changed))

    def test_result_aggregates_and_serialization_are_derived_and_lossless(self) -> None:
        result = RuntimeBenchmarkResult(
            scenario="single_cycle", repeats_requested=2, repeats_completed=2,
            max_cycles=1, durations_seconds=(0.1, 0.3), initial_belief_version=0,
            final_belief_versions=(1, 1), final_observation_sources=("action_executor",) * 2,
            final_actions=("maintain_belief",) * 2, semantic_signatures=({"a": 1}, {"a": 1}),
            semantically_deterministic=True, semantic_mismatch_count=0,
            environment={"python_version": "test"},
        )
        self.assertAlmostEqual(result.total_duration_seconds, 0.4)
        self.assertAlmostEqual(result.mean_duration_seconds, 0.2)
        self.assertEqual(result.min_duration_seconds, 0.1)
        self.assertEqual(result.max_duration_seconds, 0.3)
        data = result.to_dict()
        self.assertEqual(RuntimeBenchmarkResult.from_dict(data).to_dict(), data)

    def test_runtime_failure_is_fail_fast_and_later_call_succeeds(self) -> None:
        config = self._config(repeats=3)
        failure = RuntimeError("sentinel")
        original = RuntimeController.run
        calls = 0

        def fail_second(*args: object, **kwargs: object) -> object:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise failure
            return original(*args, **kwargs)

        with patch.object(RuntimeController, "run", side_effect=fail_second) as run:
            with self.assertRaisesRegex(RuntimeError, "sentinel"):
                run_runtime_benchmark(config)
        self.assertEqual(run.call_count, 2)
        self.assertIsInstance(run_runtime_benchmark(self._config(repeats=1)), RuntimeBenchmarkResult)

    def test_module_entry_point_is_finite_json_and_import_safe(self) -> None:
        result = run_runtime_benchmark(self._config(repeats=1))
        with patch.object(module, "run_runtime_benchmark", return_value=result), patch("builtins.print") as output:
            module.main()
        json.loads(output.call_args.args[0])
        self.assertEqual(output.call_args.kwargs, {})


if __name__ == "__main__":
    unittest.main()
