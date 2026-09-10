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
from src.integration.meta_inference_adapter import IntegrationSelected, MetaInferenceAdapter
from src.integration.task_interpreter import InterpreterFailure, TaskInterpreter
from src.integration.llm_provider import ProviderFailure
from src.evaluation.m16_diagnostic_telemetry import M16DiagnosticReason, M16DiagnosticStage, M16DiagnosticTelemetry


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
        telemetry: M16DiagnosticTelemetry | None = None,
    ) -> None:
        if not isinstance(interpreter, TaskInterpreter):
            raise TypeError("interpreter must be a TaskInterpreter")
        if not isinstance(registry, InferenceStrategyRegistry):
            raise TypeError("registry must be an InferenceStrategyRegistry")
        if telemetry is not None and not isinstance(telemetry, M16DiagnosticTelemetry):
            raise TypeError("telemetry must be M16DiagnosticTelemetry or None")
        self._interpreter = interpreter
        self._registry = registry
        self._adapter = MetaInferenceAdapter(registry)
        self._telemetry = telemetry

    def __call__(self, task: Task, runtime_state: RuntimeState) -> object:
        """Return an existing M13 result using the supplied canonical state."""

        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        if not isinstance(runtime_state, RuntimeState):
            raise TypeError("runtime_state must be a RuntimeState")

        self._emit(M16DiagnosticStage.PROVIDER_REQUEST_STARTED)
        interpretation = self._interpreter.interpret(
            task,
            response_observer=lambda: self._emit(
                M16DiagnosticStage.PROVIDER_RESPONSE_RECEIVED,
                success=True,
            ),
        )
        if not isinstance(interpretation, TaskInterpretationProposal):
            reason = M16DiagnosticReason.PROVIDER_TRANSPORT_FAILURE if isinstance(interpretation, ProviderFailure) else M16DiagnosticReason.MALFORMED_STRUCTURED_OUTPUT if isinstance(interpretation, InterpreterFailure) else M16DiagnosticReason.UNKNOWN
            self._emit(M16DiagnosticStage.PROVIDER_DECODE_FAILURE, success=False, normalized_reason=reason)
            return interpretation

        self._emit(M16DiagnosticStage.PROVIDER_DECODE_SUCCESS, success=True)
        self._emit(M16DiagnosticStage.PROPOSAL_CONSTRUCTED, success=True)

        snapshot = self._snapshot()
        validation = validate_proposal(interpretation, snapshot)
        if not isinstance(validation, ValidatedRequirement):
            self._emit(M16DiagnosticStage.PROPOSAL_VALIDATION_FAILURE, success=False, normalized_reason=M16DiagnosticReason.PROPOSAL_VALIDATION_FAILURE)
            return validation
        self._emit(M16DiagnosticStage.PROPOSAL_VALIDATION_SUCCESS, success=True)
        self._emit(M16DiagnosticStage.VALIDATED_REQUIREMENT_CREATED, success=True)

        self._emit(M16DiagnosticStage.META_INFERENCE_STARTED)
        result = self._adapter.resolve(task, runtime_state, validation, snapshot)
        if isinstance(result, IntegrationSelected):
            self._emit(M16DiagnosticStage.META_INFERENCE_SELECTED, success=True, selected_strategy=result.decision.selected_strategy)
        else:
            self._emit(M16DiagnosticStage.META_INFERENCE_NOT_SELECTED, success=False, normalized_reason=M16DiagnosticReason.META_INFERENCE_NON_SELECTION)
        return result

    def _snapshot(self) -> CapabilitySnapshot:
        """Build one immutable capability snapshot through public Registry APIs."""

        return CapabilitySnapshot(
            tuple(
                (name, self._registry.get(name).capabilities)
                for name in self._registry.list_names()
            ),
        )

    def _emit(self, stage: M16DiagnosticStage, **data: object) -> None:
        if self._telemetry is not None:
            self._telemetry.emit(stage, **data)
