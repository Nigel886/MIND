"""Inference engine for immutable belief transformation in MIND-Lite."""

from __future__ import annotations

from src.core.belief import Belief, BeliefRecord
from src.core.observation import Observation


def _observation_identifier(observation: Observation) -> str:
    """Create the deterministic belief identifier for an observation.

    Args:
        observation: The observation being incorporated into belief state.

    Returns:
        The identifier used to locate the corresponding belief record.
    """

    return (
        f"observation:{observation.source}"
        if observation.source
        else "observation:unknown"
    )


def _merge_evidence(
    previous_evidence: object,
    observation_evidence: dict[str, object],
) -> list[object]:
    """Return an evidence history containing the new observation.

    Existing evidence is preserved as-is when it predates the revision
    mechanism. New observations are appended in arrival order so revision
    remains deterministic and traceable.

    Args:
        previous_evidence: Evidence attached to the previous belief record.
        observation_evidence: Serialized evidence for the new observation.

    Returns:
        A new ordered evidence history.
    """

    if previous_evidence is None:
        return [observation_evidence]
    if isinstance(previous_evidence, list):
        return [*previous_evidence, observation_evidence]
    return [previous_evidence, observation_evidence]


def _revised_confidence(previous_confidence: float | None) -> float:
    """Calculate the deterministic confidence after one observation.

    The prototype treats each received observation as fully reliable. A
    new record therefore starts at ``1.0``. Revising an existing record
    averages its prior confidence with the new observation confidence.

    Args:
        previous_confidence: Confidence of the previous belief record.

    Returns:
        The updated confidence value.
    """

    observation_confidence = 1.0
    if previous_confidence is None:
        return observation_confidence
    return (previous_confidence + observation_confidence) / 2


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

        identifier = _observation_identifier(observation)
        previous_record = belief.state.get(identifier)
        previous_confidence = (
            previous_record.confidence
            if previous_record is not None
            else None
        )
        previous_evidence = (
            previous_record.evidence
            if previous_record is not None
            else None
        )
        confidence = _revised_confidence(previous_confidence)
        updated_record = BeliefRecord(
            identifier=identifier,
            probability=(
                previous_record.probability
                if previous_record is not None
                else 1.0
            ),
            confidence=confidence,
            evidence=_merge_evidence(
                previous_evidence,
                observation.to_dict(),
            ),
            timestamp=observation.timestamp,
        )
        updated_state = dict(belief.state)
        updated_state[identifier] = updated_record

        updated_confidence = dict(belief.confidence)
        updated_confidence[identifier] = confidence

        return Belief(
            state=updated_state,
            confidence=updated_confidence,
            version=belief.version + 1,
        )
