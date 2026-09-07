"""Internal observation-driven cognitive transition coordination for M15.

This module is intentionally not re-exported as a public package API.  It
coordinates one immutable state transition for ``CognitiveAgentSession`` and
does not execute actions, tools, providers, or environments.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from src.core.completion import CompletionEvaluator
from src.core.goal_policy import GoalAwarePolicyEngine
from src.core.observation import Observation
from src.core.policy import Policy
from src.core.runtime import RuntimeController, RuntimeState
from src.core.task import Task


@dataclass(frozen=True)
class _CognitiveCycleTransition:
    """Private data returned from one controller transition to its Session."""

    runtime_state: RuntimeState
    policy: Policy | None = None
    completed_answer: Any | None = None
    failure_category: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_state, RuntimeState):
            raise TypeError("runtime_state must be a RuntimeState")
        if self.policy is not None and not isinstance(self.policy, Policy):
            raise TypeError("policy must be a Policy or None")
        if self.failure_category is not None and not isinstance(self.failure_category, str):
            raise TypeError("failure_category must be a string or None")
        outcomes = sum(
            value is not None
            for value in (self.policy, self.completed_answer, self.failure_category)
        )
        if outcomes > 1:
            raise ValueError("a transition may have only one policy or terminal outcome")
        object.__setattr__(self, "completed_answer", deepcopy(self.completed_answer))


class CognitiveExecutionLoopController:
    """Internal stateless coordinator for one cognitive execution transition.

    This implementation component intentionally retains no RuntimeState. The
    containing ``CognitiveAgentSession`` owns private state and projects the
    controller's internal result to its public step models.
    """

    @staticmethod
    def advance(
        task: Task,
        runtime_state: RuntimeState,
        observation: Observation | None = None,
        feedback: Mapping[str, Any] | None = None,
        *,
        request_policy: bool = True,
    ) -> _CognitiveCycleTransition:
        """Run one internal feedback-to-state-to-policy transition.

        An accepted Observation is always applied with the existing canonical
        ``RuntimeController.apply_inference`` API before terminal feedback is
        classified. Nonterminal transitions may then invoke the unchanged
        Goal-aware Policy engine using the updated state.
        """

        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        if not isinstance(runtime_state, RuntimeState):
            raise TypeError("runtime_state must be a RuntimeState")
        if observation is not None and not isinstance(observation, Observation):
            raise TypeError("observation must be an Observation or None")
        if feedback is not None and not isinstance(feedback, Mapping):
            raise TypeError("feedback must be a mapping or None")
        if not isinstance(request_policy, bool):
            raise TypeError("request_policy must be a bool")
        if observation is None and feedback is not None:
            raise ValueError("feedback requires an observation")

        next_state = runtime_state
        if observation is not None:
            next_state = RuntimeController.apply_inference(runtime_state, observation)

        if feedback is not None:
            if feedback.get("status") == "failed":
                category = feedback.get("failure_category", "external_failure")
                return _CognitiveCycleTransition(
                    runtime_state=next_state,
                    failure_category=str(category),
                )
            if "output" in feedback:
                completion = CompletionEvaluator.evaluate(
                    task,
                    next_state,
                    deepcopy(feedback["output"]),
                )
                if completion.is_satisfied:
                    return _CognitiveCycleTransition(
                        runtime_state=next_state,
                        completed_answer=completion.answer,
                    )

        if not request_policy:
            return _CognitiveCycleTransition(runtime_state=next_state)

        return _CognitiveCycleTransition(
            runtime_state=next_state,
            policy=GoalAwarePolicyEngine.generate(task, next_state),
        )
