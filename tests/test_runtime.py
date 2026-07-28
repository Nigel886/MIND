"""Unit tests for the runtime state module and runtime controller."""

from __future__ import annotations

import unittest
from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from unittest.mock import patch

from src.core.belief import Belief, BeliefRecord
from src.core.inference import InferenceEngine
from src.core.observation import Observation
from src.core.policy import Policy
from src.core.runtime import RuntimeState, RuntimeController


class RuntimeStateTest(unittest.TestCase):
    """Tests for the RuntimeState model."""

    def _create_observation(self) -> Observation:
        """Create a reusable observation fixture.

        Returns:
            An immutable observation instance.
        """

        return Observation(
            source="user",
            content={"message": "hello"},
        )

    def _create_belief(self) -> Belief:
        """Create a reusable belief fixture.

        Returns:
            An immutable belief instance.
        """

        record = BeliefRecord(
            identifier="NeedResponse",
            probability=0.92,
            confidence=0.88,
            evidence={"source": "user"},
        )
        return Belief(
            state={"NeedResponse": record},
            confidence={"NeedResponse": 0.88},
            version=2,
        )

    def test_runtime_state_creation(self) -> None:
        """Creates a runtime state with observation, belief, and metadata."""

        runtime_state = RuntimeState(
            observation=self._create_observation(),
            belief=self._create_belief(),
            metadata={"phase": "prototype"},
        )

        self.assertEqual(runtime_state.observation.source, "user")
        self.assertEqual(runtime_state.belief.version, 2)
        self.assertEqual(runtime_state.metadata, {"phase": "prototype"})

    def test_runtime_state_is_immutable(self) -> None:
        """Prevents attribute mutation after creation."""

        runtime_state = RuntimeState(
            observation=self._create_observation(),
            belief=self._create_belief(),
        )

        with self.assertRaises(FrozenInstanceError):
            runtime_state.metadata = {"changed": True}

    def test_runtime_state_has_minimal_public_api(self) -> None:
        """Exposes only data and serialization interfaces."""

        self.assertFalse(hasattr(RuntimeState, "initialize"))
        self.assertFalse(hasattr(RuntimeState, "apply_decision"))
        self.assertFalse(hasattr(RuntimeState, "step"))
        self.assertFalse(hasattr(RuntimeState, "run"))
        self.assertFalse(hasattr(RuntimeState, "run_cycle"))
        self.assertFalse(hasattr(RuntimeState, "loop"))
        self.assertFalse(hasattr(RuntimeState, "stop"))
        self.assertFalse(hasattr(RuntimeState, "reset"))
        self.assertTrue(hasattr(RuntimeState, "to_dict"))
        self.assertTrue(hasattr(RuntimeState, "from_dict"))

    def test_runtime_state_serialization_delegates_nested_models(self) -> None:
        """Serializes nested observation and belief through their APIs."""

        observation = self._create_observation()
        belief = self._create_belief()
        runtime_state = RuntimeState(
            observation=observation,
            belief=belief,
            metadata={"note": "opaque"},
        )

        data = runtime_state.to_dict()

        self.assertEqual(data["observation"], observation.to_dict())
        self.assertEqual(data["belief"], belief.to_dict())
        self.assertEqual(data["metadata"], {"note": "opaque"})

    def test_runtime_state_deserialization_delegates_nested_models(self) -> None:
        """Reconstructs nested observation and belief through their APIs."""

        observation = self._create_observation()
        belief = self._create_belief()
        data = {
            "observation": observation.to_dict(),
            "belief": belief.to_dict(),
            "metadata": {"stage": "m3-01"},
        }

        runtime_state = RuntimeState.from_dict(data)

        self.assertEqual(runtime_state.observation, observation)
        self.assertEqual(runtime_state.belief, belief)
        self.assertEqual(runtime_state.metadata, {"stage": "m3-01"})

    def test_runtime_state_preserves_opaque_metadata(self) -> None:
        """Preserves metadata without semantic validation."""

        metadata = {
            "custom": {"unknown": [1, 2, 3]},
            "timestamp": datetime(2026, 6, 27, tzinfo=timezone.utc),
        }
        runtime_state = RuntimeState(
            observation=self._create_observation(),
            belief=self._create_belief(),
            metadata=metadata,
        )

        data = runtime_state.to_dict()

        self.assertEqual(data["metadata"]["custom"], {"unknown": [1, 2, 3]})
        self.assertEqual(
            data["metadata"]["timestamp"],
            "2026-06-27T00:00:00+00:00",
        )

    def test_runtime_state_round_trip(self) -> None:
        """Serializes and deserializes the runtime state losslessly."""

        runtime_state = RuntimeState(
            observation=self._create_observation(),
            belief=self._create_belief(),
            metadata={"status": "active", "count": 1},
        )

        restored = RuntimeState.from_dict(runtime_state.to_dict())

        self.assertEqual(restored, runtime_state)


class RuntimeControllerTest(unittest.TestCase):
    """Tests for the RuntimeController component."""

    def test_initialize_creates_default_runtime_state(self) -> None:
        """Creates a default runtime state when no arguments are provided."""

        controller = RuntimeController()
        runtime_state = controller.initialize()

        self.assertIsInstance(runtime_state, RuntimeState)
        self.assertIsInstance(runtime_state.observation, Observation)
        self.assertIsInstance(runtime_state.belief, Belief)
        self.assertEqual(runtime_state.metadata, {})

    def test_initialize_uses_provided_observation(self) -> None:
        """Uses the provided observation when given."""

        controller = RuntimeController()
        observation = Observation(source="user", content="test")
        runtime_state = controller.initialize(observation=observation)

        self.assertEqual(runtime_state.observation, observation)

    def test_initialize_uses_provided_belief(self) -> None:
        """Uses the provided belief when given."""

        controller = RuntimeController()
        belief = Belief(state={}, confidence={}, version=1)
        runtime_state = controller.initialize(belief=belief)

        self.assertEqual(runtime_state.belief, belief)

    def test_initialize_uses_provided_metadata(self) -> None:
        """Uses the provided metadata when given."""

        controller = RuntimeController()
        metadata = {"test": "value"}
        runtime_state = controller.initialize(metadata=metadata)

        self.assertEqual(runtime_state.metadata, metadata)

    def test_initialize_creates_new_instance_each_time(self) -> None:
        """Returns a new RuntimeState instance on each call."""

        controller = RuntimeController()
        first = controller.initialize()
        second = controller.initialize()

        self.assertIsNot(first, second)

    def test_runtime_controller_is_stateless(self) -> None:
        """Verifies RuntimeController stores no internal state."""

        controller = RuntimeController()
        controller.initialize()

        self.assertFalse(hasattr(controller, "runtime_state"))
        self.assertFalse(hasattr(controller, "observation"))
        self.assertFalse(hasattr(controller, "belief"))

    def test_runtime_controller_has_approved_public_api(self) -> None:
        """Exposes the approved runtime state orchestration operations."""

        controller = RuntimeController()

        self.assertTrue(hasattr(controller, "initialize"))
        self.assertTrue(hasattr(controller, "update"))
        self.assertTrue(hasattr(controller, "apply_inference"))
        self.assertTrue(hasattr(controller, "apply_decision"))
        self.assertTrue(hasattr(controller, "run_cycle"))
        self.assertFalse(hasattr(controller, "step"))
        self.assertFalse(hasattr(controller, "run"))
        self.assertFalse(hasattr(controller, "loop"))
        self.assertFalse(hasattr(controller, "stop"))
        self.assertFalse(hasattr(controller, "reset"))

    def test_update_preserves_original_state(self) -> None:
        """Verifies original RuntimeState remains unchanged after update."""

        controller = RuntimeController()
        original = controller.initialize()

        new_observation = Observation(source="test", content="new")
        updated = controller.update(original, observation=new_observation)

        self.assertIsNot(original, updated)
        self.assertNotEqual(original.observation, updated.observation)
        self.assertEqual(original.belief, updated.belief)
        self.assertEqual(original.metadata, updated.metadata)

    def test_update_replaces_only_specified_components(self) -> None:
        """Updates only the components explicitly provided by the caller."""

        controller = RuntimeController()
        original = controller.initialize(
            metadata={"phase": "initial"},
        )

        new_belief = Belief(state={}, confidence={}, version=999)
        updated = controller.update(original, belief=new_belief)

        self.assertEqual(updated.observation, original.observation)
        self.assertEqual(updated.belief, new_belief)
        self.assertEqual(updated.metadata, original.metadata)
        self.assertIsNot(original, updated)

    def test_update_replaces_multiple_components(self) -> None:
        """Supports updating multiple components in a single call."""

        controller = RuntimeController()
        original = controller.initialize()

        new_observation = Observation(source="test", content="multi")
        new_belief = Belief(state={}, confidence={}, version=123)
        new_metadata = {"phase": "updated"}

        updated = controller.update(
            original,
            observation=new_observation,
            belief=new_belief,
            metadata=new_metadata,
        )

        self.assertEqual(updated.observation, new_observation)
        self.assertEqual(updated.belief, new_belief)
        self.assertEqual(updated.metadata, new_metadata)
        self.assertIsNot(original, updated)

    def test_update_returns_new_instance(self) -> None:
        """Always returns a new RuntimeState instance even with no changes."""

        controller = RuntimeController()
        original = controller.initialize()

        updated = controller.update(original)

        self.assertIsNot(original, updated)
        self.assertEqual(original.observation, updated.observation)
        self.assertEqual(original.belief, updated.belief)
        self.assertEqual(original.metadata, updated.metadata)

    def test_update_preserves_metadata_immutability(self) -> None:
        """Ensures metadata dictionary is copied when preserved."""

        controller = RuntimeController()
        original = controller.initialize(metadata={"key": "value"})

        updated = controller.update(original)

        self.assertEqual(original.metadata, updated.metadata)
        self.assertIsNot(original.metadata, updated.metadata)


class RuntimeInferenceIntegrationTest(unittest.TestCase):
    """Tests for RuntimeController and InferenceEngine integration."""

    def test_apply_inference_returns_updated_runtime_state(self) -> None:
        """Delegates belief transformation and updates runtime state."""

        controller = RuntimeController()
        original = controller.initialize(
            metadata={"phase": "initial"},
        )
        observation = Observation(
            source="user",
            content={"message": "infer this"},
        )
        expected_belief = InferenceEngine.infer(
            observation,
            original.belief,
        )

        updated = controller.apply_inference(original, observation)

        self.assertIsInstance(updated, RuntimeState)
        self.assertIsNot(updated, original)
        self.assertIs(updated.observation, observation)
        self.assertEqual(updated.belief, expected_belief)
        self.assertIsNot(updated.belief, original.belief)
        self.assertEqual(updated.metadata, original.metadata)
        self.assertIsNot(updated.metadata, original.metadata)

    def test_apply_inference_preserves_state_across_repeated_calls(self) -> None:
        """Preserves prior states while the controller remains stateless."""

        controller = RuntimeController()
        original = controller.initialize(
            belief=Belief(
                state={
                    "observation:user": BeliefRecord(
                        identifier="observation:user",
                        probability=0.75,
                        confidence=0.6,
                        evidence={"source": "earlier"},
                    ),
                },
                confidence={"observation:user": 0.6},
                version=4,
            ),
            metadata={"phase": "revision"},
        )
        first_observation = Observation(
            source="user",
            content={"message": "new evidence"},
        )
        second_observation = Observation(
            source="system",
            content={"message": "follow-up evidence"},
        )
        runtime_snapshot = deepcopy(original.to_dict())
        belief_snapshot = deepcopy(original.belief.to_dict())
        first_observation_snapshot = deepcopy(first_observation.to_dict())
        second_observation_snapshot = deepcopy(second_observation.to_dict())

        first_updated = controller.apply_inference(original, first_observation)
        first_runtime_snapshot = deepcopy(first_updated.to_dict())
        first_belief_snapshot = deepcopy(first_updated.belief.to_dict())
        expected_second_belief = InferenceEngine.infer(
            second_observation,
            first_updated.belief,
        )

        second_updated = controller.apply_inference(
            first_updated,
            second_observation,
        )

        self.assertEqual(original.to_dict(), runtime_snapshot)
        self.assertEqual(original.belief.to_dict(), belief_snapshot)
        self.assertEqual(first_observation.to_dict(), first_observation_snapshot)
        self.assertEqual(second_observation.to_dict(), second_observation_snapshot)
        self.assertIsNot(first_updated, original)
        self.assertIsNot(second_updated, first_updated)
        self.assertEqual(first_updated.to_dict(), first_runtime_snapshot)
        self.assertEqual(first_updated.belief.to_dict(), first_belief_snapshot)
        self.assertEqual(second_updated.belief, expected_second_belief)
        self.assertEqual(
            first_updated.belief.version,
            original.belief.version + 1,
        )
        self.assertEqual(
            second_updated.belief.version,
            first_updated.belief.version + 1,
        )
        self.assertEqual(len(dir(controller)), len(dir(RuntimeController)))
        self.assertFalse(hasattr(controller, "runtime_state"))
        self.assertFalse(hasattr(controller, "observation"))
        self.assertFalse(hasattr(controller, "belief"))


class RuntimeDecisionIntegrationTest(unittest.TestCase):
    """Tests for RuntimeController decision orchestration."""

    def _create_state(self, belief: Belief) -> RuntimeState:
        """Create a RuntimeState fixture with nested immutable inputs."""

        return RuntimeController.initialize(
            observation=Observation(
                source="user",
                content={"message": "initial"},
            ),
            belief=belief,
            metadata={"phase": "decision", "nested": {"value": 1}},
        )

    def _create_non_empty_belief(self) -> Belief:
        """Create a Belief fixture with nested BeliefRecord evidence."""

        record = BeliefRecord(
            identifier="decision:ready",
            probability=0.8,
            confidence=0.9,
            evidence={"nested": {"source": "runtime-test"}},
        )
        return Belief(
            state={"decision:ready": record},
            confidence={"decision:ready": 0.9},
            version=3,
        )

    def test_apply_decision_integrates_empty_belief_without_mutation(self) -> None:
        """Stores the await-observation result in a new RuntimeState."""

        belief = Belief(state={}, confidence={}, version=2)
        original = self._create_state(belief)
        runtime_snapshot = deepcopy(original.to_dict())
        observation_snapshot = deepcopy(original.observation.to_dict())
        belief_snapshot = deepcopy(belief.to_dict())
        metadata_snapshot = deepcopy(original.metadata)

        updated = RuntimeController.apply_decision(original)

        self.assertIsInstance(updated, RuntimeState)
        self.assertIsNot(updated, original)
        self.assertEqual(updated.observation.source, "action_executor")
        self.assertEqual(
            updated.observation.content["action"],
            "await_observation",
        )
        self.assertEqual(updated.observation.content["status"], "completed")
        self.assertEqual(updated.observation.content["parameters"], {})
        self.assertIs(updated.belief, belief)
        self.assertEqual(updated.metadata, metadata_snapshot)
        self.assertIsNot(updated.metadata, original.metadata)
        self.assertEqual(original.to_dict(), runtime_snapshot)
        self.assertEqual(original.observation.to_dict(), observation_snapshot)
        self.assertEqual(belief.to_dict(), belief_snapshot)
        self.assertNotIn("policy", updated.to_dict())
        self.assertNotIn("action_result", updated.to_dict())

    def test_apply_decision_integrates_non_empty_belief_without_mutation(self) -> None:
        """Stores the maintain-belief result and preserves all input values."""

        belief = self._create_non_empty_belief()
        original = self._create_state(belief)
        runtime_snapshot = deepcopy(original.to_dict())
        belief_snapshot = deepcopy(belief.to_dict())
        record_snapshot = deepcopy(belief.state["decision:ready"].to_dict())

        updated = RuntimeController.apply_decision(original)

        self.assertIsNot(updated, original)
        self.assertEqual(updated.observation.source, "action_executor")
        self.assertEqual(
            updated.observation.content["action"],
            "maintain_belief",
        )
        self.assertEqual(updated.observation.content["status"], "completed")
        self.assertEqual(updated.observation.content["parameters"], {})
        self.assertIs(updated.belief, belief)
        self.assertEqual(original.to_dict(), runtime_snapshot)
        self.assertEqual(belief.to_dict(), belief_snapshot)
        self.assertEqual(
            belief.state["decision:ready"].to_dict(),
            record_snapshot,
        )

    def test_apply_decision_is_stateless_and_creates_fresh_observations(self) -> None:
        """Keeps calls independent while returning fresh state transitions."""

        controller = RuntimeController()
        first_state = self._create_state(self._create_non_empty_belief())
        second_state = RuntimeState.from_dict(first_state.to_dict())
        first_snapshot = deepcopy(first_state.to_dict())

        first_result = controller.apply_decision(first_state)
        second_result = controller.apply_decision(second_state)

        self.assertIsNot(first_result, first_state)
        self.assertIsNot(second_result, second_state)
        self.assertIsNot(first_result.observation, second_result.observation)
        self.assertNotEqual(
            first_result.observation.id,
            second_result.observation.id,
        )
        self.assertEqual(
            first_result.observation.content,
            second_result.observation.content,
        )
        self.assertIs(first_result.observation.timestamp.tzinfo, timezone.utc)
        self.assertIs(second_result.observation.timestamp.tzinfo, timezone.utc)
        self.assertEqual(first_state.to_dict(), first_snapshot)
        self.assertEqual(len(dir(controller)), len(dir(RuntimeController)))
        self.assertFalse(hasattr(controller, "runtime_state"))
        self.assertFalse(hasattr(controller, "policy"))
        self.assertFalse(hasattr(controller, "observation"))
        self.assertFalse(hasattr(controller, "belief"))

    def test_apply_decision_delegates_to_components_and_update(self) -> None:
        """Delegates the exact values through the approved component APIs."""

        original = self._create_state(
            Belief(state={}, confidence={}, version=0),
        )
        policy = Policy(
            action="await_observation",
            parameters={"nested": {"value": 1}},
            metadata={"source": "delegation-test"},
        )
        action_observation = Observation(
            source="action_executor",
            content={
                "action": "await_observation",
                "status": "completed",
                "parameters": policy.parameters,
            },
        )

        with patch(
            "src.core.runtime.PolicyEngine.generate",
            return_value=policy,
        ) as generate, patch(
            "src.core.runtime.ActionExecutor.execute",
            return_value=action_observation,
        ) as execute, patch.object(
            RuntimeController,
            "update",
            wraps=RuntimeController.update,
        ) as update, patch(
            "src.core.runtime.InferenceEngine.infer",
            side_effect=AssertionError("apply_decision must not infer"),
        ):
            updated = RuntimeController.apply_decision(original)

        generate.assert_called_once_with(original.belief)
        execute.assert_called_once_with(policy)
        update.assert_called_once_with(
            original,
            observation=action_observation,
        )
        self.assertIs(updated.observation, action_observation)
        self.assertIs(updated.belief, original.belief)

    def test_apply_decision_propagates_execution_errors(self) -> None:
        """Propagates execution failure without creating a fallback state."""

        controller = RuntimeController()
        original = self._create_state(
            Belief(state={}, confidence={}, version=0),
        )
        original_snapshot = deepcopy(original.to_dict())

        with patch(
            "src.core.runtime.ActionExecutor.execute",
            side_effect=ValueError("unsupported action"),
        ), patch.object(RuntimeController, "update") as update:
            with self.assertRaisesRegex(ValueError, "unsupported action"):
                controller.apply_decision(original)

        update.assert_not_called()
        self.assertEqual(original.to_dict(), original_snapshot)
        self.assertFalse(hasattr(controller, "runtime_state"))
        self.assertFalse(hasattr(controller, "policy"))

        later_result = controller.apply_decision(original)

        self.assertIsInstance(later_result, RuntimeState)
        self.assertEqual(later_result.observation.source, "action_executor")


class RuntimeCycleTest(unittest.TestCase):
    """Tests for one complete RuntimeController orchestration cycle."""

    def _state(self, belief: Belief) -> RuntimeState:
        return RuntimeController.initialize(
            observation=Observation(source="initial", content={"value": 0}),
            belief=belief,
            metadata={"phase": "cycle", "nested": {"value": 1}},
        )

    def _non_empty_belief(self) -> Belief:
        record = BeliefRecord(
            identifier="existing",
            probability=0.7,
            confidence=0.8,
            evidence={"nested": {"source": "fixture"}},
        )
        return Belief(
            state={"existing": record},
            confidence={"existing": 0.8},
            version=4,
        )

    def test_run_cycle_empty_belief_infers_before_decision(self) -> None:
        """Uses the inferred non-empty Belief for the final decision."""

        original = self._state(Belief(state={}, confidence={}, version=0))
        incoming = Observation(source="user", content={"message": "evidence"})
        expected_inferred = RuntimeController.apply_inference(original, incoming)
        original_snapshot = deepcopy(original.to_dict())
        incoming_snapshot = deepcopy(incoming.to_dict())

        final = RuntimeController.run_cycle(original, incoming)

        self.assertIsNot(final, original)
        self.assertIsNot(final, expected_inferred)
        self.assertEqual(final.belief, expected_inferred.belief)
        self.assertNotEqual(final.belief.state, {})
        self.assertEqual(final.belief.version, original.belief.version + 1)
        self.assertEqual(final.observation.source, "action_executor")
        self.assertEqual(final.observation.content["action"], "maintain_belief")
        self.assertEqual(final.observation.content["status"], "completed")
        self.assertNotEqual(final.observation, incoming)
        self.assertEqual(original.to_dict(), original_snapshot)
        self.assertEqual(incoming.to_dict(), incoming_snapshot)
        self.assertEqual(final.metadata, original.metadata)
        self.assertIsNot(final.metadata, original.metadata)

    def test_run_cycle_preserves_non_empty_inputs_and_final_contract(self) -> None:
        """Preserves input state while retaining the inferred Belief at the end."""

        belief = self._non_empty_belief()
        original = self._state(belief)
        incoming = Observation(source="user", content={"message": "new"})
        original_snapshot = deepcopy(original.to_dict())
        belief_snapshot = deepcopy(belief.to_dict())
        record_snapshot = deepcopy(belief.state["existing"].to_dict())
        incoming_snapshot = deepcopy(incoming.to_dict())

        final = RuntimeController.run_cycle(original, incoming)

        self.assertIsNot(final, original)
        self.assertEqual(final.belief.version, belief.version + 1)
        self.assertEqual(final.observation.source, "action_executor")
        self.assertEqual(final.observation.content["action"], "maintain_belief")
        self.assertEqual(original.to_dict(), original_snapshot)
        self.assertEqual(belief.to_dict(), belief_snapshot)
        self.assertEqual(belief.state["existing"].to_dict(), record_snapshot)
        self.assertEqual(incoming.to_dict(), incoming_snapshot)
        self.assertEqual(set(final.to_dict()), {"observation", "belief", "metadata"})

    def test_run_cycle_composes_exact_orchestration_results(self) -> None:
        """Passes exact state values between the approved public operations."""

        original = self._state(Belief(state={}, confidence={}, version=0))
        incoming = Observation(source="user", content="incoming")
        inferred = RuntimeController.initialize(metadata={"intermediate": True})
        final = RuntimeController.initialize(metadata={"final": True})

        with patch.object(
            RuntimeController,
            "apply_inference",
            return_value=inferred,
        ) as apply_inference, patch.object(
            RuntimeController,
            "apply_decision",
            return_value=final,
        ) as apply_decision:
            result = RuntimeController.run_cycle(original, incoming)

        apply_inference.assert_called_once_with(original, incoming)
        apply_decision.assert_called_once_with(inferred)
        self.assertIs(result, final)

    def test_run_cycle_is_stateless_and_returns_fresh_action_observations(self) -> None:
        """Keeps equivalent cycles independent and leaves prior inputs intact."""

        controller = RuntimeController()
        first_state = self._state(Belief(state={}, confidence={}, version=0))
        second_state = RuntimeState.from_dict(first_state.to_dict())
        first_incoming = Observation(source="user", content={"message": "same"})
        second_incoming = Observation.from_dict(first_incoming.to_dict())
        first_snapshot = deepcopy(first_state.to_dict())

        first_final = controller.run_cycle(first_state, first_incoming)
        second_final = controller.run_cycle(second_state, second_incoming)

        self.assertEqual(first_final.belief, second_final.belief)
        self.assertEqual(first_final.observation.content, second_final.observation.content)
        self.assertIsNot(first_final.observation, second_final.observation)
        self.assertNotEqual(first_final.observation.id, second_final.observation.id)
        self.assertIs(first_final.observation.timestamp.tzinfo, timezone.utc)
        self.assertIs(second_final.observation.timestamp.tzinfo, timezone.utc)
        self.assertEqual(first_state.to_dict(), first_snapshot)
        self.assertFalse(hasattr(controller, "runtime_state"))
        self.assertFalse(hasattr(controller, "observation"))
        self.assertFalse(hasattr(controller, "belief"))
        self.assertFalse(hasattr(controller, "policy"))
        self.assertFalse(hasattr(controller, "intermediate_state"))

    def test_run_cycle_propagates_failures_without_fallback(self) -> None:
        """Propagates failures and leaves later valid cycles independent."""

        controller = RuntimeController()
        original = self._state(Belief(state={}, confidence={}, version=0))
        incoming = Observation(source="user", content="incoming")
        original_snapshot = deepcopy(original.to_dict())
        incoming_snapshot = deepcopy(incoming.to_dict())

        with patch.object(
            RuntimeController,
            "apply_inference",
            side_effect=RuntimeError("inference failure"),
        ), patch.object(RuntimeController, "apply_decision") as apply_decision:
            with self.assertRaisesRegex(RuntimeError, "inference failure"):
                controller.run_cycle(original, incoming)

        apply_decision.assert_not_called()
        self.assertEqual(original.to_dict(), original_snapshot)
        self.assertEqual(incoming.to_dict(), incoming_snapshot)

        with patch.object(
            RuntimeController,
            "apply_decision",
            side_effect=ValueError("decision failure"),
        ):
            with self.assertRaisesRegex(ValueError, "decision failure"):
                controller.run_cycle(original, incoming)

        self.assertEqual(original.to_dict(), original_snapshot)
        self.assertEqual(incoming.to_dict(), incoming_snapshot)
        self.assertIsInstance(controller.run_cycle(original, incoming), RuntimeState)


class RuntimeCoreIntegrationTest(unittest.TestCase):
    """Integration tests for the complete Runtime Core."""

    def test_complete_runtime_workflow(self) -> None:
        """Verifies a complete Runtime Core workflow from initialization through multiple updates."""

        controller = RuntimeController()

        # Step 1: Initialize the runtime
        initial_state = controller.initialize()
        self.assertIsInstance(initial_state, RuntimeState)
        self.assertIsInstance(initial_state.observation, Observation)
        self.assertIsInstance(initial_state.belief, Belief)

        # Step 2: Update observation
        obs1 = Observation(source="user", content="first input")
        state1 = controller.update(initial_state, observation=obs1)
        self.assertIsNot(initial_state, state1)
        self.assertEqual(state1.observation, obs1)
        self.assertEqual(state1.belief, initial_state.belief)
        self.assertEqual(state1.metadata, initial_state.metadata)

        # Verify initial state is unmodified
        self.assertIsNot(initial_state.observation, obs1)

        # Step 3: Update belief
        belief1 = Belief(
            state={},
            confidence={},
            version=1,
        )
        state2 = controller.update(state1, belief=belief1)
        self.assertIsNot(state1, state2)
        self.assertEqual(state2.observation, obs1)
        self.assertEqual(state2.belief, belief1)

        # Step 4: Update metadata
        metadata1 = {"phase": "running", "iteration": 1}
        state3 = controller.update(state2, metadata=metadata1)
        self.assertIsNot(state2, state3)
        self.assertEqual(state3.metadata, metadata1)

        # Step 5: Update all components together
        obs2 = Observation(source="system", content="response")
        belief2 = Belief(
            state={},
            confidence={},
            version=2,
        )
        metadata2 = {"phase": "complete", "iteration": 2}

        state4 = controller.update(
            state3,
            observation=obs2,
            belief=belief2,
            metadata=metadata2,
        )
        self.assertIsNot(state3, state4)
        self.assertEqual(state4.observation, obs2)
        self.assertEqual(state4.belief, belief2)
        self.assertEqual(state4.metadata, metadata2)

    def test_runtime_state_immutability_through_workflow(self) -> None:
        """Ensures RuntimeState remains immutable throughout the entire workflow."""

        from dataclasses import FrozenInstanceError

        controller = RuntimeController()
        state = controller.initialize()

        # Attempt to modify the state directly (should fail)
        with self.assertRaises(FrozenInstanceError):
            state.metadata = {"modified": True}

        with self.assertRaises(FrozenInstanceError):
            state.observation = Observation(source="hacked", content="bad")

        with self.assertRaises(FrozenInstanceError):
            state.belief = Belief(state={}, confidence={}, version=999)

        # Update through controller creates new instance
        new_state = controller.update(
            state,
            metadata={"updated": True},
        )

        self.assertIsNot(state, new_state)
        self.assertEqual(state.metadata, {})  # Original unchanged
        self.assertEqual(new_state.metadata, {"updated": True})  # New has change

    def test_runtime_controller_statelessness(self) -> None:
        """Ensures RuntimeController never stores internal state."""

        controller = RuntimeController()

        # Check that no instance attributes are stored
        self.assertEqual(len(dir(controller)), len(dir(RuntimeController)))
        self.assertFalse(hasattr(controller, "runtime_state"))
        self.assertFalse(hasattr(controller, "observation"))
        self.assertFalse(hasattr(controller, "belief"))
        self.assertFalse(hasattr(controller, "metadata"))
        self.assertFalse(hasattr(controller, "state"))
        self.assertFalse(hasattr(controller, "current_state"))

        # Multiple operations don't leave any state behind
        state1 = controller.initialize()
        state2 = controller.update(state1)
        state3 = controller.update(state2)

        # No state stored in controller
        self.assertFalse(hasattr(controller, "state1"))
        self.assertFalse(hasattr(controller, "state2"))
        self.assertFalse(hasattr(controller, "state3"))

    def test_runtime_round_trip_serialization(self) -> None:
        """Verifies complete RuntimeState round-trip serialization."""

        controller = RuntimeController()
        original = controller.initialize(
            metadata={"test": "value", "number": 42},
        )

        # Serialize
        data = original.to_dict()
        self.assertIsInstance(data, dict)
        self.assertIn("observation", data)
        self.assertIn("belief", data)
        self.assertIn("metadata", data)

        # Deserialize
        restored = RuntimeState.from_dict(data)

        # Verify they are equivalent but different instances
        self.assertEqual(restored.observation, original.observation)
        self.assertEqual(restored.belief, original.belief)
        self.assertEqual(restored.metadata, original.metadata)
        self.assertIsNot(restored, original)
