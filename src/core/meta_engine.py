"""Deterministic, selection-only M9 Meta-Inference engine."""

from __future__ import annotations

from src.core.meta_inference import (
    DecisionEvidence,
    MetaInferenceDecision,
    MetaInferenceDecisionStatus,
)
from src.core.inference_registry import InferenceStrategyRegistry
from src.core.runtime import RuntimeState
from src.core.task import Task


class MetaInferenceEngine:
    """Select one registered strategy without executing or updating it."""

    def __init__(self, registry: InferenceStrategyRegistry) -> None:
        if not isinstance(registry, InferenceStrategyRegistry):
            raise TypeError("registry must be an InferenceStrategyRegistry")
        self._registry = registry

    def select(
        self,
        task: Task,
        runtime_state: RuntimeState,
    ) -> MetaInferenceDecision:
        """Return a deterministic capability-based selection decision."""

        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        if not isinstance(runtime_state, RuntimeState):
            raise TypeError("runtime_state must be a RuntimeState")

        required = task.metadata.get("required_inference_capabilities", ())
        if isinstance(required, str) or not isinstance(required, (list, tuple)):
            raise TypeError("required_inference_capabilities must be a sequence of strings")
        if any(not isinstance(capability, str) for capability in required):
            raise TypeError("required_inference_capabilities must contain strings")
        if any(not capability.strip() for capability in required):
            raise ValueError("required_inference_capabilities must not contain empty strings")
        if len(set(required)) != len(required):
            raise ValueError("required_inference_capabilities must not contain duplicates")

        required_set = set(required)
        names = self._registry.list_names()
        matches = [
            self._registry.get(name)
            for name in names
            if required_set.issubset(set(self._registry.get(name).capabilities))
        ]
        if len(matches) == 1:
            return MetaInferenceDecision(
                MetaInferenceDecisionStatus.SELECTED,
                matches[0].name,
                (
                    DecisionEvidence(
                        "capability_match",
                        "Selected strategy because required capabilities are supported",
                        {"required_capabilities": list(required)},
                    ),
                ),
            )
        if not matches:
            description = (
                "No strategy is registered"
                if not names
                else "No strategy supports the required capabilities"
            )
            return MetaInferenceDecision(
                MetaInferenceDecisionStatus.UNAVAILABLE,
                None,
                (DecisionEvidence("capability_unavailable", description, {"required_capabilities": list(required)}),),
            )
        return MetaInferenceDecision(
            MetaInferenceDecisionStatus.REJECTED,
            None,
            (DecisionEvidence("capability_ambiguity", "Multiple strategies support the required capabilities", {"required_capabilities": list(required), "matching_strategies": [item.name for item in matches]}),),
        )
