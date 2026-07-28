"""End-to-end validation tests for the MIND-Lite runtime foundation."""

from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from src.core.action import ActionExecutor
from src.core.observation import Observation
from src.core.runtime import RuntimeController, RuntimeState


class _ActionExecutionFailure(Exception):
    """Sentinel exception used to verify unchanged runtime error propagation."""


def _normalize_runtime_value(value: object) -> object:
    """Remove only documented generated identity fields for semantic comparison."""

    if isinstance(value, dict):
        return {
            key: _normalize_runtime_value(item)
            for key, item in value.items()
            if key not in {"id", "timestamp"}
        }
    if isinstance(value, list):
        return [_normalize_runtime_value(item) for item in value]
    return value


class RuntimeEndToEndValidationTest(unittest.TestCase):
    """Cross-layer validation of the completed bounded runtime foundation."""

    def _initial_content(self) -> dict[str, object]:
        """Create semantically rich observation content for real inference."""

        return {
            "request": "validate runtime",
            "attempt": 3,
            "enabled": True,
            "context": {
                "tags": ["runtime", "end-to-end"],
                "options": {"strict": True},
            },
        }

    def _initial_metadata(self) -> dict[str, object]:
        """Create nested metadata that the runtime must preserve."""

        return {
            "validation": {
                "suite": "M7",
                "flags": ["immutable", "bounded"],
            },
            "enabled": True,
        }

    def _state_and_observation(self) -> tuple[RuntimeState, Observation]:
        """Create independent public-API inputs for a bounded real run."""

        return (
            RuntimeController.initialize(metadata=self._initial_metadata()),
            Observation(source="validation", content=self._initial_content()),
        )

    def test_complete_three_cycle_run_preserves_inputs_and_chains_observations(
        self,
    ) -> None:
        """Runs three real cycles and validates observable end-to-end behavior."""

        original_state, initial_observation = self._state_and_observation()
        state_snapshot = deepcopy(original_state.to_dict())
        belief_snapshot = deepcopy(original_state.belief.to_dict())
        metadata_snapshot = deepcopy(original_state.metadata)
        content_snapshot = deepcopy(initial_observation.content)
        observation_snapshot = deepcopy(initial_observation.to_dict())

        result = RuntimeController.run(
            original_state,
            initial_observation,
            max_cycles=3,
        )

        self.assertIsInstance(result, RuntimeState)
        self.assertIsNot(result, original_state)
        self.assertEqual(result.observation.source, "action_executor")
        self.assertEqual(result.observation.content["status"], "completed")
        self.assertEqual(result.observation.content["action"], "maintain_belief")
        self.assertIn(
            result.observation.content["action"],
            {"await_observation", "maintain_belief"},
        )

        self.assertNotEqual(result.belief.state, {})
        self.assertEqual(result.belief.version, original_state.belief.version + 3)
        initial_record = result.belief.state["observation:validation"]
        self.assertEqual(initial_record.evidence[0]["content"], content_snapshot)

        action_record = result.belief.state["observation:action_executor"]
        self.assertEqual(len(action_record.evidence), 2)
        action_evidence_ids = [
            evidence["id"]
            for evidence in action_record.evidence
        ]
        self.assertEqual(len(set(action_evidence_ids)), 2)
        self.assertNotIn(result.observation.id, action_evidence_ids)
        self.assertTrue(
            all(
                evidence["source"] == "action_executor"
                for evidence in action_record.evidence
            ),
        )

        self.assertEqual(result.metadata, metadata_snapshot)
        for prohibited_key in (
            "cycle_count",
            "iteration",
            "history",
            "trajectory",
            "status",
            "termination_reason",
        ):
            self.assertNotIn(prohibited_key, result.metadata)

        self.assertEqual(original_state.to_dict(), state_snapshot)
        self.assertEqual(original_state.belief.to_dict(), belief_snapshot)
        self.assertEqual(original_state.metadata, metadata_snapshot)
        self.assertEqual(initial_observation.content, content_snapshot)
        self.assertEqual(initial_observation.to_dict(), observation_snapshot)

    def test_equivalent_bounded_runs_are_semantically_deterministic_and_stateless(
        self,
    ) -> None:
        """Confirms deterministic semantic results despite generated identities."""

        first_state, first_observation = self._state_and_observation()
        second_state, second_observation = self._state_and_observation()
        first_snapshot = deepcopy(first_state.to_dict())
        second_snapshot = deepcopy(second_state.to_dict())
        first_observation_snapshot = deepcopy(first_observation.to_dict())
        second_observation_snapshot = deepcopy(second_observation.to_dict())
        controller = RuntimeController()

        second_result = controller.run(second_state, second_observation, 3)
        first_result = controller.run(first_state, first_observation, 3)
        repeated_first_result = controller.run(first_state, first_observation, 3)

        normalized_second = _normalize_runtime_value(second_result.to_dict())
        normalized_first = _normalize_runtime_value(first_result.to_dict())
        normalized_repeated = _normalize_runtime_value(
            repeated_first_result.to_dict(),
        )

        self.assertEqual(normalized_first, normalized_second)
        self.assertEqual(normalized_first, normalized_repeated)
        self.assertEqual(first_result.belief.version, second_result.belief.version)
        self.assertEqual(
            first_result.observation.content["action"],
            second_result.observation.content["action"],
        )
        self.assertEqual(
            first_result.observation.source,
            second_result.observation.source,
        )
        self.assertNotEqual(
            first_result.observation.id,
            second_result.observation.id,
        )
        self.assertEqual(controller.__dict__, {})
        self.assertEqual(first_state.to_dict(), first_snapshot)
        self.assertEqual(second_state.to_dict(), second_snapshot)
        self.assertEqual(first_observation.to_dict(), first_observation_snapshot)
        self.assertEqual(
            second_observation.to_dict(),
            second_observation_snapshot,
        )

    def test_final_state_from_real_bounded_run_round_trips_without_loss(self) -> None:
        """Round-trips a genuine final state through its public serialization API."""

        initial_state, initial_observation = self._state_and_observation()
        final_state = RuntimeController.run(
            initial_state,
            initial_observation,
            max_cycles=3,
        )
        final_snapshot = deepcopy(final_state.to_dict())

        serialized = final_state.to_dict()
        restored = RuntimeState.from_dict(serialized)

        self.assertIsInstance(restored, RuntimeState)
        self.assertEqual(restored.to_dict(), serialized)
        self.assertEqual(restored.observation.to_dict(), serialized["observation"])
        self.assertEqual(restored.belief.to_dict(), serialized["belief"])
        self.assertEqual(restored.belief.version, final_state.belief.version)
        self.assertEqual(restored.metadata, final_state.metadata)
        self.assertEqual(
            restored.belief.state["observation:validation"].evidence[0]["content"],
            self._initial_content(),
        )
        self.assertEqual(
            restored.belief.state["observation:action_executor"].evidence,
            final_state.belief.state["observation:action_executor"].evidence,
        )
        self.assertEqual(final_state.to_dict(), final_snapshot)

    def test_run_propagates_action_failure_without_retry_and_later_run_succeeds(
        self,
    ) -> None:
        """Propagates an executor failure unchanged and retains no failed state."""

        original_state, initial_observation = self._state_and_observation()
        state_snapshot = deepcopy(original_state.to_dict())
        observation_snapshot = deepcopy(initial_observation.to_dict())
        controller = RuntimeController()
        failure = _ActionExecutionFailure("sentinel action failure")

        with patch.object(
            ActionExecutor,
            "execute",
            side_effect=failure,
        ) as execute:
            with self.assertRaises(_ActionExecutionFailure) as caught:
                controller.run(original_state, initial_observation, 2)

        self.assertIs(caught.exception, failure)

        execute.assert_called_once()
        self.assertEqual(original_state.to_dict(), state_snapshot)
        self.assertEqual(initial_observation.to_dict(), observation_snapshot)
        self.assertEqual(controller.__dict__, {})

        later_result = controller.run(original_state, initial_observation, 1)

        self.assertIsInstance(later_result, RuntimeState)
        self.assertEqual(later_result.observation.source, "action_executor")
        self.assertEqual(controller.__dict__, {})


if __name__ == "__main__":
    unittest.main()
