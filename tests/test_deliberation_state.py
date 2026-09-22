"""Focused tests for immutable M19 deliberation/epistemic state values."""

from dataclasses import FrozenInstanceError, replace
from math import inf, nan
import unittest

from src.core.deliberation_state import (
    DeliberationState,
    EpistemicSignal,
    EpistemicState,
    FailureRecoveryProjection,
    RecoveryEvent,
    RecoveryEventCategory,
    SignalAvailability,
    SignalSource,
)


def available(value: float, *, normalized: bool = False) -> EpistemicSignal:
    return EpistemicSignal(
        SignalAvailability.AVAILABLE, value, SignalSource.RUNTIME_DERIVED,
        "m19_unit_interval_v1" if normalized else "m19_value_v1", "m19_signal_v1", normalized,
    )


def state() -> DeliberationState:
    epistemic = EpistemicState(
        available(0.2, normalized=True), available(0.4, normalized=True),
        available(0.8, normalized=True), available(1.25), available(-0.5),
        "m19_epistemic_v1", "transition:epistemic:1",
    )
    history = FailureRecoveryProjection(
        (RecoveryEvent(RecoveryEventCategory.RECOVERABLE_FAILURE, "transition:failure:1"),),
        "m19_history_v1", "transition:history:1",
    )
    return DeliberationState("runtime:projection:1", epistemic, history, "m19_state_v1", "transition:state:1")


class DeliberationStateTest(unittest.TestCase):
    def test_valid_state_is_immutable_and_has_no_policy_or_execution_api(self) -> None:
        value = state()
        self.assertEqual(value.epistemic_state.uncertainty.value, 0.2)
        with self.assertRaises(FrozenInstanceError):
            value.version = "other"
        for name in ("choose_decision", "should_stop", "should_observe", "execute", "consume"):
            self.assertFalse(hasattr(value, name))

    def test_unknown_signal_is_explicit_and_carries_no_default_or_provenance(self) -> None:
        unknown = EpistemicSignal.unknown()
        self.assertEqual(unknown.availability, SignalAvailability.UNKNOWN)
        self.assertIsNone(unknown.value)
        with self.assertRaises(ValueError):
            EpistemicSignal(SignalAvailability.UNKNOWN, 0.0)

    def test_signal_rejects_nan_inf_and_normalized_range_errors(self) -> None:
        for value in (nan, inf, -inf):
            with self.assertRaises(ValueError):
                available(value)
        for value in (-0.01, 1.01):
            with self.assertRaises(ValueError):
                available(value, normalized=True)

    def test_state_rejects_negative_formal_non_negative_signals_and_bad_metadata(self) -> None:
        with self.assertRaises(ValueError):
            EpistemicState(available(-1), available(0), available(0), available(0), available(0), "v", "t")
        with self.assertRaises(ValueError):
            EpistemicState(available(0), available(0), available(0), available(0), available(0), "", "t")
        with self.assertRaises(TypeError):
            RecoveryEvent("failure", "transition:1")

    def test_serialization_is_deterministic_and_round_trips(self) -> None:
        original = state()
        serialized = original.to_dict()
        self.assertEqual(serialized, original.to_dict())
        self.assertEqual(DeliberationState.from_dict(serialized), original)

    def test_replace_creates_new_state_and_leaves_original_unchanged(self) -> None:
        original = state()
        updated = replace(original, transition_identity="transition:state:2")
        self.assertEqual(original.transition_identity, "transition:state:1")
        self.assertEqual(updated.transition_identity, "transition:state:2")
        self.assertNotEqual(updated, original)

    def test_deserialization_rejects_malformed_state(self) -> None:
        with self.assertRaises(TypeError):
            DeliberationState.from_dict([])
        data = state().to_dict()
        data["epistemic_state"]["uncertainty"]["availability"] = "missing"
        with self.assertRaises(ValueError):
            DeliberationState.from_dict(data)


if __name__ == "__main__":
    unittest.main()
