"""Immutable policy models and deterministic policy generation for MIND-Lite."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from src.core.belief import Belief


def _serialize_value(value: Any) -> Any:
    """Recursively serialize values to JSON-compatible structures.

    Args:
        value: Value to serialize.

    Returns:
        A serialized representation of the value.
    """

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            key: _serialize_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    return value


@dataclass(frozen=True)
class Policy:
    """Represents an immutable decision for a future ActionExecutor.

    Policy describes a selected action and its execution inputs. It does not
    execute actions or own runtime state.

    Attributes:
        action: The selected action type.
        parameters: Data required by a future ActionExecutor.
        metadata: Non-execution information about the decision.
    """

    action: str
    parameters: dict[str, Any]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize this policy to a dictionary.

        Returns:
            A JSON-compatible dictionary representation of the policy.
        """

        return _serialize_value(asdict(self))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Policy":
        """Deserialize a Policy from a dictionary.

        Args:
            data: Serialized policy data.

        Returns:
            A reconstructed immutable policy.
        """

        return cls(
            action=data["action"],
            parameters=dict(data["parameters"]),
            metadata=dict(data["metadata"]),
        )


class PolicyEngine:
    """Generates deterministic prototype Policies from immutable Beliefs.

    PolicyEngine is stateless and performs decision generation only. It does not
    execute actions, invoke tools, create observations, or orchestrate runtime
    state.
    """

    @staticmethod
    def generate(belief: Belief) -> Policy:
        """Generate one deterministic Policy from the supplied Belief.

        Empty belief states wait for new evidence. Non-empty belief states return
        a decision to maintain the current belief state. The strategy deliberately
        validates the Policy boundary without implementing planning or action
        selection algorithms.

        Args:
            belief: The current immutable belief state.

        Returns:
            One immutable decision policy.
        """

        belief_record_count = len(belief.state)
        action = (
            "await_observation"
            if belief_record_count == 0
            else "maintain_belief"
        )
        return Policy(
            action=action,
            parameters={},
            metadata={
                "belief_version": belief.version,
                "belief_record_count": belief_record_count,
            },
        )
