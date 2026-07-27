"""Deterministic prototype action execution for MIND-Lite."""

from __future__ import annotations

from src.core.observation import Observation
from src.core.policy import Policy


class ActionExecutor:
    """Executes prototype Policies as immutable execution observations.

    ActionExecutor is stateless. It creates local result observations only and
    does not invoke tools, mutate beliefs, or coordinate runtime state.
    """

    @staticmethod
    def execute(policy: Policy) -> Observation:
        """Execute one supported Policy and return its result Observation.

        Args:
            policy: The immutable Policy to execute.

        Returns:
            A new immutable Observation describing the completed execution.

        Raises:
            ValueError: If ``policy.action`` is not a supported prototype action.
        """

        if policy.action not in (
            "await_observation",
            "maintain_belief",
        ):
            raise ValueError(f"Unsupported policy action: {policy.action}")

        return Observation(
            source="action_executor",
            content={
                "action": policy.action,
                "status": "completed",
                "parameters": policy.parameters,
            },
        )
