"""Controlled M13 admission resolver for an M15 cognitive session.

This integration-side component composes existing M13 interpretation,
validation, and Meta-Inference adapter contracts.  It does not execute tools
or actions and is the only component in this flow that calls TaskInterpreter.
"""

from __future__ import annotations

from src.core.inference_registry import InferenceStrategyRegistry
from src.core.runtime import RuntimeState
from src.core.task import Task
from src.core.task_interpretation import (
    CapabilitySnapshot,
    TaskInterpretationProposal,
    ValidatedRequirement,
)
from src.core.task_validation import validate_proposal
from src.integration.meta_inference_adapter import MetaInferenceAdapter
from src.integration.task_interpreter import TaskInterpreter


class M13SessionAdmissionResolver:
    """Resolve one M13 context against the exact Session-provided RuntimeState.

    The resolver returns only existing M13 result values.  A caller such as
    ``CognitiveAgentSession`` admits solely an ``IntegrationSelected`` value;
    all other existing explicit M13 outcomes remain non-success results.
    """

    def __init__(
        self,
        interpreter: TaskInterpreter,
        registry: InferenceStrategyRegistry,
    ) -> None:
        if not isinstance(interpreter, TaskInterpreter):
            raise TypeError("interpreter must be a TaskInterpreter")
        if not isinstance(registry, InferenceStrategyRegistry):
            raise TypeError("registry must be an InferenceStrategyRegistry")
        self._interpreter = interpreter
        self._registry = registry
        self._adapter = MetaInferenceAdapter(registry)

    def __call__(self, task: Task, runtime_state: RuntimeState) -> object:
        """Return an existing M13 result using the supplied canonical state."""

        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        if not isinstance(runtime_state, RuntimeState):
            raise TypeError("runtime_state must be a RuntimeState")

        interpretation = self._interpreter.interpret(task)
        if not isinstance(interpretation, TaskInterpretationProposal):
            return interpretation

        snapshot = self._snapshot()
        validation = validate_proposal(interpretation, snapshot)
        if not isinstance(validation, ValidatedRequirement):
            return validation

        return self._adapter.resolve(task, runtime_state, validation, snapshot)

    def _snapshot(self) -> CapabilitySnapshot:
        """Build one immutable capability snapshot through public Registry APIs."""

        return CapabilitySnapshot(
            tuple(
                (name, self._registry.get(name).capabilities)
                for name in self._registry.list_names()
            ),
        )
