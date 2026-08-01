"""Deterministic, explicitly invoked Cohort A evaluation runner."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from src.evaluation.agent_adapter import MINDGoalDirectedEvaluationAdapter
from src.evaluation.cohort_a import (
    CohortAResultRecord,
    M14CohortATaskFixture,
    aggregate_cohort_a_metrics,
    canonical_json_hash,
    fixture_suite_hash,
)
from src.evaluation.contracts import (
    EvaluationAction,
    EvaluationActionType,
    EvaluationCase,
    EvaluationFeedback,
    EvaluationFeedbackType,
    EvaluationOutcome,
    EvaluationOutcomeType,
)
from src.evaluation.environment import DeterministicEvaluationEnvironment
from src.evaluation.execution import (
    AgentStepInput,
    AgentStepResult,
    EnvironmentInteraction,
    EvaluationBudgetState,
)


MIND_BASELINE_ID = "mind_goal_directed"
CONTROL_BASELINE_ID = "deterministic_direct_policy"
COHORT_A_BASELINE_ORDER = (MIND_BASELINE_ID, CONTROL_BASELINE_ID)


class _StepAgent(Protocol):
    def step(self, step_input: AgentStepInput) -> AgentStepResult:
        """Return one public step result."""


class DeterministicDirectPolicy:
    """Evaluation-only deterministic control with no access to MIND state."""

    def step(self, step_input: AgentStepInput) -> AgentStepResult:
        if not isinstance(step_input, AgentStepInput):
            raise TypeError("step_input must be an AgentStepInput")
        feedback = step_input.previous_feedback
        if feedback.feedback_type is EvaluationFeedbackType.TOOL_RESPONSE:
            payload = feedback.payload
            response = payload.get("response")
            answer = response.get("output") if isinstance(response, Mapping) else None
            return AgentStepResult(
                EvaluationAction(EvaluationActionType.ANSWER, {"answer": deepcopy(answer)}),
                True,
            )
        if feedback.feedback_type is EvaluationFeedbackType.TOOL_FAILURE:
            return _failure("tool_failure")
        if feedback.feedback_type is EvaluationFeedbackType.INVALID_ACTION:
            return _invalid("invalid_action")
        if feedback.feedback_type is EvaluationFeedbackType.BUDGET:
            return _failure("budget_exhausted")
        if feedback.feedback_type is EvaluationFeedbackType.TIMEOUT:
            return _failure("timeout")
        if feedback.feedback_type is not EvaluationFeedbackType.INITIAL_INPUT:
            return _invalid("unexpected_feedback")

        task_input = step_input.case.task.input
        if "value" in task_input:
            return AgentStepResult(
                EvaluationAction(EvaluationActionType.ANSWER, {"answer": deepcopy(task_input["value"])}),
                True,
            )
        operation = task_input.get("operation")
        operands = task_input.get("operands")
        if operation == "multiply" and isinstance(operands, tuple):
            return AgentStepResult(
                EvaluationAction(
                    EvaluationActionType.TOOL_CALL,
                    {
                        "tool_name": "calculator",
                        "parameters": {
                            "operation": operation,
                            "operands": [deepcopy(item) for item in operands],
                        },
                    },
                ),
                False,
            )
        return _failure("unsupported_task")


def _failure(reason: str) -> AgentStepResult:
    return AgentStepResult(
        EvaluationAction(EvaluationActionType.FAIL, {"reason": reason}),
        True,
    )


def _invalid(reason: str) -> AgentStepResult:
    return AgentStepResult(
        EvaluationAction(EvaluationActionType.INVALID, {"reason": reason}),
        True,
    )


@dataclass(frozen=True)
class CohortACompletionJudge:
    """Declarative local judge using only public actions, feedback, and config."""

    completion_rule_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.completion_rule_version, str):
            raise TypeError("completion_rule_version must be a str")
        if not self.completion_rule_version.strip():
            raise ValueError("completion_rule_version must not be empty")

    def evaluate(
        self,
        case: EvaluationCase,
        interactions: tuple[EnvironmentInteraction, ...],
        budget_state: EvaluationBudgetState,
        terminal_action: EvaluationAction | None,
        environment_config: Any,
    ) -> EvaluationOutcome:
        """Assign one outcome without accessing private Adapter or MIND state."""

        if not isinstance(case, EvaluationCase):
            raise TypeError("case must be an EvaluationCase")
        if not isinstance(interactions, tuple):
            raise TypeError("interactions must be a tuple")
        if any(not isinstance(item, EnvironmentInteraction) for item in interactions):
            raise TypeError("interactions must contain EnvironmentInteraction values")
        if not isinstance(budget_state, EvaluationBudgetState):
            raise TypeError("budget_state must be an EvaluationBudgetState")
        completion_context = environment_config.completion_context
        last_feedback = interactions[-1].feedback if interactions else None
        if last_feedback is not None and last_feedback.feedback_type is EvaluationFeedbackType.TIMEOUT:
            return EvaluationOutcome(EvaluationOutcomeType.TIMEOUT, {"failure_category": "timeout"})
        if last_feedback is not None and last_feedback.feedback_type is EvaluationFeedbackType.BUDGET:
            return EvaluationOutcome(EvaluationOutcomeType.FAILURE, {"failure_category": "budget_exhausted"})
        if terminal_action is None:
            return EvaluationOutcome(EvaluationOutcomeType.FAILURE, {"failure_category": "budget_exhausted"})
        if terminal_action.action_type is EvaluationActionType.INVALID:
            return EvaluationOutcome(EvaluationOutcomeType.INVALID_EXECUTION, {"failure_category": "invalid_execution"})
        if terminal_action.action_type is EvaluationActionType.FAIL:
            reason = terminal_action.payload.get("reason", "failure")
            expected = completion_context.get("expected_failure_category")
            return EvaluationOutcome(
                EvaluationOutcomeType.SUCCESS if reason == expected else EvaluationOutcomeType.FAILURE,
                {"failure_category": reason},
            )
        if terminal_action.action_type is not EvaluationActionType.ANSWER:
            return EvaluationOutcome(EvaluationOutcomeType.INVALID_EXECUTION, {"failure_category": "invalid_execution"})
        answer = terminal_action.payload.get("answer")
        expected_answer = completion_context.get("expected_answer")
        return EvaluationOutcome(
            EvaluationOutcomeType.SUCCESS if answer == expected_answer else EvaluationOutcomeType.FAILURE,
            {} if answer == expected_answer else {"failure_category": "incorrect_answer"},
        )


class CohortARunner:
    """Explicitly invoked deterministic runner; importing this module has no effects."""

    def __init__(
        self,
        baseline_order: tuple[str, ...] = COHORT_A_BASELINE_ORDER,
        repetitions: int = 3,
    ) -> None:
        if not isinstance(baseline_order, tuple):
            raise TypeError("baseline_order must be a tuple")
        if not baseline_order or any(identifier not in COHORT_A_BASELINE_ORDER for identifier in baseline_order):
            raise ValueError("baseline_order must contain known Cohort A baseline identifiers")
        if len(set(baseline_order)) != len(baseline_order):
            raise ValueError("baseline_order must not contain duplicates")
        if isinstance(repetitions, bool) or not isinstance(repetitions, int):
            raise TypeError("repetitions must be an int, not bool")
        if repetitions < 1:
            raise ValueError("repetitions must be at least 1")
        self._baseline_order = baseline_order
        self._repetitions = repetitions

    @property
    def baseline_order(self) -> tuple[str, ...]:
        return self._baseline_order

    @property
    def repetitions(self) -> int:
        return self._repetitions

    def run(self, fixtures: tuple[M14CohortATaskFixture, ...]) -> tuple[CohortAResultRecord, ...]:
        """Run explicitly supplied fixtures in frozen fixture/baseline/repeat order."""

        if not isinstance(fixtures, tuple):
            raise TypeError("fixtures must be a tuple")
        if any(not isinstance(fixture, M14CohortATaskFixture) for fixture in fixtures):
            raise TypeError("fixtures must contain M14CohortATaskFixture values")
        suite_hash = fixture_suite_hash(fixtures)
        records: list[CohortAResultRecord] = []
        for fixture in fixtures:
            for baseline_id in self._baseline_order:
                for repeat_index in range(self._repetitions):
                    records.append(self._run_one(fixture, baseline_id, repeat_index, suite_hash))
        return tuple(records)

    def metrics(self, records: tuple[CohortAResultRecord, ...]):
        """Aggregate records explicitly, without generating an artifact."""

        return aggregate_cohort_a_metrics(records)

    def _run_one(
        self,
        fixture: M14CohortATaskFixture,
        baseline_id: str,
        repeat_index: int,
        suite_hash: str,
    ) -> CohortAResultRecord:
        case = EvaluationCase.from_dict(fixture.to_dict()["task_definition"]["case"])
        environment = DeterministicEvaluationEnvironment(fixture.environment_config)
        actor = (
            MINDGoalDirectedEvaluationAdapter()
            if baseline_id == MIND_BASELINE_ID
            else DeterministicDirectPolicy()
        )
        feedback = environment.reset(case)
        actions: list[EvaluationAction] = []
        feedbacks: list[EvaluationFeedback] = [feedback]
        interactions: list[EnvironmentInteraction] = []
        steps_used = tool_calls_used = 0
        terminal_action: EvaluationAction | None = None

        while steps_used < fixture.budget.max_steps:
            state = EvaluationBudgetState(
                fixture.budget,
                steps_used=steps_used,
                tool_calls_used=tool_calls_used,
            )
            result = actor.step(AgentStepInput(case, feedback, state))
            actions.append(result.action)
            steps_used += 1
            if result.request_termination:
                terminal_action = result.action
                break
            if result.action.action_type is not EvaluationActionType.TOOL_CALL:
                terminal_action = EvaluationAction(EvaluationActionType.INVALID, {"reason": "nonterminal_non_tool_action"})
                break
            feedback = environment.apply(result.action, state)
            interactions.append(EnvironmentInteraction(result.action, feedback))
            feedbacks.append(feedback)
            tool_calls_used += 1

        judge = CohortACompletionJudge(fixture.completion_rule_version)
        budget_state = EvaluationBudgetState(
            fixture.budget,
            steps_used=steps_used,
            tool_calls_used=tool_calls_used,
        )
        outcome = judge.evaluate(
            case,
            tuple(interactions),
            budget_state,
            terminal_action,
            fixture.environment_config,
        )
        trace_summary = {
            "action_types": [action.action_type.value for action in actions],
            "feedback_types": [item.feedback_type.value for item in feedbacks],
            "interaction_count": len(interactions),
        }
        resource_usage = {
            "steps": steps_used,
            "tool_calls": tool_calls_used,
            "resource_counters": {},
        }
        configuration_hash = canonical_json_hash(
            {
                "suite_hash": suite_hash,
                "environment": fixture.environment_config.to_dict(),
                "budget": fixture.budget.to_dict(),
                "completion_rule_version": fixture.completion_rule_version,
            }
        )
        return CohortAResultRecord(
            task_id=fixture.task_id,
            baseline_id=baseline_id,
            repeat_index=repeat_index,
            outcome=outcome,
            trace_summary=trace_summary,
            resource_usage=resource_usage,
            configuration_hash=configuration_hash,
        )
