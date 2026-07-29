"""Deterministic, stateless completion evaluation for M8."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from src.core.result import CompletionDecision
from src.core.runtime import RuntimeState
from src.core.task import Task


class CompletionEvaluator:
    """Verifies candidate answers using explicit Task input data only."""

    @staticmethod
    def evaluate(
        task: Task,
        runtime_state: RuntimeState,
        candidate_answer: Any | None,
    ) -> CompletionDecision:
        """Evaluate a candidate against Task.input['expected_answer'] if present."""

        if not isinstance(task, Task):
            raise TypeError("task must be a Task")
        if not isinstance(runtime_state, RuntimeState):
            raise TypeError("runtime_state must be a RuntimeState")

        if "expected_answer" not in task.input:
            return CompletionDecision(
                is_satisfied=False,
                answer=candidate_answer,
                evidence=({"criterion_type": "expected_answer", "available": False},),
            )
        expected_answer = task.input["expected_answer"]
        matched = (
            candidate_answer is not None
            and _comparison_value(candidate_answer) == _comparison_value(expected_answer)
        )
        return CompletionDecision(
            is_satisfied=matched,
            answer=candidate_answer,
            evidence=(
                {
                    "criterion_type": "expected_answer",
                    "available": True,
                    "matched": matched,
                },
            ),
        )


def _comparison_value(value: Any) -> Any:
    """Normalize immutable storage containers for deterministic equality only."""

    if isinstance(value, Mapping):
        return {key: _comparison_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_comparison_value(item) for item in value]
    if isinstance(value, frozenset):
        return sorted((_comparison_value(item) for item in value), key=repr)
    return deepcopy(value)
