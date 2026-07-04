"""Inference engine for immutable belief transformation in MIND-Lite."""

from __future__ import annotations

from src.core.belief import Belief, BeliefRecord
from src.core.observation import Observation


class InferenceEngine:
    """Derives a new immutable belief using the current observation.

    InferenceEngine is a stateless transformation component. It derives
    a new immutable ``Belief`` using the current ``Observation`` and the
    previous ``Belief`` without performing runtime orchestration.

    InferenceEngine shall remain implementation-independent. Future
    inference strategies may evolve without changing the public API.
    """

    @staticmethod
    def infer(
        observation: Observation,
        belief: Belief,
    ) -> Belief:
        """Derive a new immutable belief from the given runtime inputs.

        The prototype implementation remains deterministic and focuses on
        architectural validation rather than inference quality. Belief
        revision is treated as an internal implementation detail.

        Args:
            observation: The current immutable runtime observation.
            belief: The previous immutable belief state.

        Returns:
            A newly constructed immutable belief state.
        """

        identifier = (
            f"observation:{observation.source}"
            if observation.source
            else "observation:unknown"
        )
        updated_record = BeliefRecord(
            identifier=identifier,
            probability=1.0,
            confidence=1.0,
            evidence=observation.to_dict(),
            timestamp=observation.timestamp,
        )
        updated_state = dict(belief.state)
        updated_state[identifier] = updated_record

        updated_confidence = dict(belief.confidence)
        updated_confidence[identifier] = updated_record.confidence

        return Belief(
            state=updated_state,
            confidence=updated_confidence,
            version=belief.version + 1,
        )
