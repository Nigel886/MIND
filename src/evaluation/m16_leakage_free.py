"""Leakage-free M16 evaluation helpers around the frozen MIND-Lite artifact.

The public benchmark Task remains unchanged.  A private, constant-null legacy
schema projection exists solely because the frozen v1.0 GoalAwarePolicy checks
for a legacy key.  This module does not compute answers, execute MIND tools,
or expose evaluator-private truth through public evaluation structures.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping

from src.core.task import Task
from src.evaluation.agent_adapter import MINDGoalDirectedEvaluationAdapter
from src.evaluation.contracts import (
    EvaluationAction,
    EvaluationActionType,
    EvaluationCase,
    EvaluationFeedback,
    EvaluationFeedbackType,
    EvaluationOutcome,
    EvaluationOutcomeType,
)
from src.evaluation.direct_tool_calling import assess_cohort_a_eligibility
from src.evaluation.execution import (
    AgentStepInput,
    AgentStepResult,
    EnvironmentInteraction,
    EvaluationBudgetState,
)


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("mapping keys must be strings")
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("float values must be finite")
        return value
    raise ValueError("values must be JSON-compatible")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return deepcopy(value)


def _freeze_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict")
    return _freeze_json(value)


def _reject_private_environment_keys(value: Any) -> None:
    """Keep known completion-truth containers out of public reset payloads."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in {"expected_answer", "completion_context"}:
                raise ValueError(f"M16 public environment payload must not contain {key}")
            _reject_private_environment_keys(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _reject_private_environment_keys(item)


def _text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
    if value != value.strip():
        raise ValueError(f"{name} must not have leading or trailing whitespace")


def _is_finite_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _canonical_json(value: Any) -> Any:
    """Normalize JSON-compatible data for deterministic direct-answer equality."""

    frozen = _freeze_json(value)
    if isinstance(frozen, Mapping):
        return tuple((key, _canonical_json(item)) for key, item in sorted(frozen.items()))
    if isinstance(frozen, tuple):
        return tuple(_canonical_json(item) for item in frozen)
    return frozen


def project_m16_legacy_task(public_task: Task) -> Task:
    """Create a private legacy Task with the fixed null compatibility sentinel."""

    if not isinstance(public_task, Task):
        raise TypeError("public_task must be a Task")
    eligibility = assess_cohort_a_eligibility(
        EvaluationCase("m16.projection", public_task),
    )
    if not eligibility.eligible:
        raise ValueError(f"public_task is not M16 Cohort A eligible: {eligibility.reason}")
    public_input = public_task.input
    keys = set(public_input)
    if "expected_answer" in public_input:
        raise ValueError("public_task input must not contain expected_answer")
    if keys == {"value"}:
        projected_input = {"value": _thaw_json(public_input["value"]), "expected_answer": None}
    elif keys == {"operation", "operands"}:
        operation = public_input["operation"]
        operands = public_input["operands"]
        if operation not in {"add", "multiply"}:
            raise ValueError("unsupported calculator operation")
        if not isinstance(operands, tuple) or len(operands) != 2:
            raise ValueError("calculator operands must contain exactly two values")
        if not all(_is_finite_int(value) for value in operands):
            raise TypeError("calculator operands must be ints, not bool")
        projected_input = {
            "operation": operation,
            "operands": _thaw_json(operands),
            "expected_answer": None,
        }
    else:
        raise ValueError("public_task input does not match a frozen M16 schema")
    return Task(
        id=public_task.id,
        goal=public_task.goal,
        input=projected_input,
        context=_thaw_json(public_task.context),
        constraints=_thaw_json(public_task.constraints),
        metadata=_thaw_json(public_task.metadata),
    )


@dataclass(frozen=True)
class M16PrivateTruth:
    """Evaluator-only exact truth, deliberately lacking public serialization."""

    expected_answer: Any
    judge_id: str
    normalization_version: str = "m16-exact-v1"

    def __post_init__(self) -> None:
        _text(self.judge_id, "judge_id")
        _text(self.normalization_version, "normalization_version")
        object.__setattr__(self, "expected_answer", _freeze_json(self.expected_answer))

    def to_private_dict(self) -> dict[str, Any]:
        """Serialize only for evaluator-private fixture storage."""

        return {
            "expected_answer": _thaw_json(self.expected_answer),
            "judge_id": self.judge_id,
            "normalization_version": self.normalization_version,
        }

    @classmethod
    def from_private_dict(cls, data: dict[str, Any]) -> "M16PrivateTruth":
        if not isinstance(data, dict):
            raise TypeError("M16PrivateTruth data must be a dict")
        return cls(
            expected_answer=data["expected_answer"],
            judge_id=data["judge_id"],
            normalization_version=data.get("normalization_version", "m16-exact-v1"),
        )


@dataclass(frozen=True)
class M16PrivateEnvironmentSpecification:
    """Evaluator-owned M16 environment configuration with no completion truth."""

    environment_id: str
    initial_payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _text(self.environment_id, "environment_id")
        frozen_payload = _freeze_mapping(self.initial_payload, "initial_payload")
        _reject_private_environment_keys(frozen_payload)
        object.__setattr__(self, "initial_payload", frozen_payload)

    def to_private_dict(self) -> dict[str, Any]:
        return {
            "environment_id": self.environment_id,
            "initial_payload": _thaw_json(self.initial_payload),
        }


class M16PrivateEvaluationEnvironment:
    """M16 deterministic calculator environment that never emits completion truth."""

    def __init__(self, specification: M16PrivateEnvironmentSpecification) -> None:
        if not isinstance(specification, M16PrivateEnvironmentSpecification):
            raise TypeError("specification must be M16PrivateEnvironmentSpecification")
        self._specification = specification
        self._is_reset = False

    def reset(self, case: EvaluationCase) -> EvaluationFeedback:
        if not isinstance(case, EvaluationCase):
            raise TypeError("case must be an EvaluationCase")
        self._is_reset = True
        return EvaluationFeedback(
            EvaluationFeedbackType.INITIAL_INPUT,
            {
                "environment_id": self._specification.environment_id,
                "initial": _thaw_json(self._specification.initial_payload),
            },
        )

    def apply(
        self,
        action: EvaluationAction,
        budget_state: EvaluationBudgetState,
    ) -> EvaluationFeedback:
        if not self._is_reset:
            raise RuntimeError("environment must be reset before apply")
        if not isinstance(action, EvaluationAction):
            raise TypeError("action must be an EvaluationAction")
        if not isinstance(budget_state, EvaluationBudgetState):
            raise TypeError("budget_state must be an EvaluationBudgetState")
        if budget_state.remaining_steps <= 0:
            return EvaluationFeedback(EvaluationFeedbackType.BUDGET, {"reason": "max_steps"})
        if action.action_type is not EvaluationActionType.TOOL_CALL:
            return EvaluationFeedback(
                EvaluationFeedbackType.INVALID_ACTION,
                {"reason": "environment_accepts_tool_call_only"},
            )
        if budget_state.remaining_tool_calls <= 0:
            return EvaluationFeedback(EvaluationFeedbackType.BUDGET, {"reason": "max_tool_calls"})
        if action.payload.get("tool_name") != "calculator":
            return EvaluationFeedback(EvaluationFeedbackType.INVALID_ACTION, {"reason": "unknown_tool"})
        parameters = action.payload.get("parameters")
        if not isinstance(parameters, Mapping) or set(parameters) != {"operation", "operands"}:
            return EvaluationFeedback(EvaluationFeedbackType.INVALID_ACTION, {"reason": "invalid_calculator_parameters"})
        operation = parameters["operation"]
        operands = parameters["operands"]
        if operation not in {"add", "multiply"}:
            return EvaluationFeedback(EvaluationFeedbackType.INVALID_ACTION, {"reason": "unsupported_operation"})
        if not isinstance(operands, (tuple, list)) or len(operands) != 2 or not all(
            _is_finite_int(value) for value in operands
        ):
            return EvaluationFeedback(EvaluationFeedbackType.INVALID_ACTION, {"reason": "invalid_operands"})
        result = operands[0] + operands[1] if operation == "add" else operands[0] * operands[1]
        return EvaluationFeedback(
            EvaluationFeedbackType.TOOL_RESPONSE,
            {
                "tool_name": "calculator",
                "parameters": {
                    "operation": operation,
                    "operands": _thaw_json(operands),
                },
                "response": {"output": result},
            },
        )


M16_COMPLETION_SEMANTICS_VERSION = "m16_completion_v2"


class M16CompletionMode(str, Enum):
    """Frozen family-specific M16 benchmark completion modes."""

    AGENT_FINAL_ANSWER = "agent_final_answer"
    EVALUATOR_TOOL_OUTCOME = "evaluator_tool_outcome"


def m16_completion_mode(case: EvaluationCase) -> M16CompletionMode:
    """Resolve the evaluator-owned completion mode from frozen public family metadata."""

    family = case.task.metadata["m16_cohort_a"]["task_family"]
    if family == "direct_answer":
        return M16CompletionMode.AGENT_FINAL_ANSWER
    if family == "controlled_single_tool":
        return M16CompletionMode.EVALUATOR_TOOL_OUTCOME
    raise ValueError("unsupported M16 task family")


class M16ExactCompletionJudge:
    """Evaluator-owned exact judge using only private injected truth."""

    def __init__(self, private_truth: M16PrivateTruth) -> None:
        if not isinstance(private_truth, M16PrivateTruth):
            raise TypeError("private_truth must be M16PrivateTruth")
        self._private_truth = private_truth

    def evaluate(
        self,
        case: EvaluationCase,
        interactions: tuple[EnvironmentInteraction, ...],
        budget_state: EvaluationBudgetState,
        terminal_action: EvaluationAction | None,
    ) -> EvaluationOutcome:
        if not isinstance(case, EvaluationCase):
            raise TypeError("case must be an EvaluationCase")
        if not isinstance(interactions, tuple) or any(
            not isinstance(item, EnvironmentInteraction) for item in interactions
        ):
            raise TypeError("interactions must be a tuple of EnvironmentInteraction values")
        if not isinstance(budget_state, EvaluationBudgetState):
            raise TypeError("budget_state must be an EvaluationBudgetState")
        last_feedback = interactions[-1].feedback if interactions else None
        if last_feedback is not None and last_feedback.feedback_type is EvaluationFeedbackType.TIMEOUT:
            return EvaluationOutcome(EvaluationOutcomeType.TIMEOUT, {"failure_category": "timeout"})
        if last_feedback is not None and last_feedback.feedback_type is EvaluationFeedbackType.BUDGET:
            return EvaluationOutcome(EvaluationOutcomeType.FAILURE, {"failure_category": "budget_exhaustion"})
        if terminal_action is None and m16_completion_mode(case) is M16CompletionMode.AGENT_FINAL_ANSWER:
            return EvaluationOutcome(EvaluationOutcomeType.FAILURE, {"failure_category": "budget_exhaustion"})
        if terminal_action is not None and terminal_action.action_type is EvaluationActionType.INVALID:
            return EvaluationOutcome(EvaluationOutcomeType.INVALID_EXECUTION, {"failure_category": "invalid_execution"})
        if terminal_action is not None and terminal_action.action_type is EvaluationActionType.FAIL:
            return EvaluationOutcome(EvaluationOutcomeType.FAILURE, {"failure_category": "explicit_agent_failure"})
        mode = m16_completion_mode(case)
        if mode is M16CompletionMode.EVALUATOR_TOOL_OUTCOME:
            return self._evaluate_calculator_outcome(case, interactions)
        if terminal_action is None or terminal_action.action_type is not EvaluationActionType.ANSWER:
            return EvaluationOutcome(EvaluationOutcomeType.INVALID_EXECUTION, {"failure_category": "invalid_execution"})
        answer = terminal_action.payload.get("answer")
        if self._is_correct(case, answer):
            return EvaluationOutcome(EvaluationOutcomeType.SUCCESS, {})
        return EvaluationOutcome(EvaluationOutcomeType.FAILURE, {"failure_category": "incorrect_answer"})

    def _evaluate_calculator_outcome(
        self, case: EvaluationCase, interactions: tuple[EnvironmentInteraction, ...]
    ) -> EvaluationOutcome:
        """Judge only an environment result caused by the submitted public action."""

        if len(interactions) != 1:
            return EvaluationOutcome(EvaluationOutcomeType.FAILURE, {"failure_category": "incorrect_answer"})
        interaction = interactions[0]
        action, feedback = interaction.action, interaction.feedback
        if action.action_type is not EvaluationActionType.TOOL_CALL:
            return EvaluationOutcome(EvaluationOutcomeType.INVALID_EXECUTION, {"failure_category": "invalid_execution"})
        if feedback.feedback_type is not EvaluationFeedbackType.TOOL_RESPONSE:
            return EvaluationOutcome(EvaluationOutcomeType.FAILURE, {"failure_category": "incorrect_answer"})
        parameters = action.payload.get("parameters")
        feedback_parameters = feedback.payload.get("parameters")
        response = feedback.payload.get("response")
        if action.payload.get("tool_name") != "calculator" or parameters != feedback_parameters or not isinstance(response, Mapping):
            return EvaluationOutcome(EvaluationOutcomeType.FAILURE, {"failure_category": "incorrect_answer"})
        if self._is_correct(case, response.get("output")):
            return EvaluationOutcome(EvaluationOutcomeType.SUCCESS, {})
        return EvaluationOutcome(EvaluationOutcomeType.FAILURE, {"failure_category": "incorrect_answer"})

    def _is_correct(self, case: EvaluationCase, answer: Any) -> bool:
        family = case.task.metadata["m16_cohort_a"]["task_family"]
        if family == "direct_answer":
            return _canonical_json(answer) == _canonical_json(self._private_truth.expected_answer)
        if family == "controlled_single_tool":
            return _is_finite_int(answer) and _is_finite_int(self._private_truth.expected_answer) and answer == self._private_truth.expected_answer
        return False


class M16MINDGoalDirectedEvaluationAdapter:
    """M16-only wrapper that sends a private projected Task to frozen MIND code."""

    def __init__(self) -> None:
        self._delegate = MINDGoalDirectedEvaluationAdapter()

    def step(self, step_input: AgentStepInput) -> AgentStepResult:
        if not isinstance(step_input, AgentStepInput):
            raise TypeError("step_input must be an AgentStepInput")
        projected_case = EvaluationCase(
            evaluation_id=step_input.case.evaluation_id,
            task=project_m16_legacy_task(step_input.case.task),
            environment_config=_thaw_json(step_input.case.environment_config),
        )
        return self._delegate.step(
            AgentStepInput(
                case=projected_case,
                previous_feedback=step_input.previous_feedback,
                budget_state=step_input.budget_state,
            )
        )
