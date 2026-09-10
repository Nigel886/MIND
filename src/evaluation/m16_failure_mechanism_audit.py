"""Synthetic-only post-hoc M16 MIND failure-mechanism audit.

It reads restart1 records only for public aggregate patterns.  All executable
controls use invented Tasks and in-process provider results; no provider,
held-out fixture, runner, or raw result writer is imported.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.core.inference_registry import InferenceStrategyRegistry
from src.core.inference_strategy import InferenceStrategy
from src.core.cognitive_session import CognitiveAgentSession
from src.core.meta_inference import DecisionEvidence, MetaInferenceDecision, MetaInferenceDecisionStatus
from src.core.task import Goal, Task
from src.evaluation.contracts import EvaluationActionType, EvaluationCase, EvaluationFeedback, EvaluationFeedbackType
from src.evaluation.execution import AgentStepInput, EvaluationBudget, EvaluationBudgetState
from src.evaluation.m16_benchmark_contracts import M16FailureCategory
from src.evaluation.m16_benchmark_runner import M16BenchmarkRunner
from src.evaluation.m16_leakage_free import M16PrivateEvaluationEnvironment, M16PrivateEnvironmentSpecification
from src.evaluation.m16_mind_session_adapter import M16MINDSessionEvaluationAdapter
from src.integration.llm_provider import ProviderFailure, ProviderFailureCategory, ProviderResponse
from src.integration.llm_session_admission import M13SessionAdmissionResolver
from src.integration.meta_inference_adapter import IntegrationSelected
from src.integration.task_interpreter import TaskInterpreter


class _IdentityInference:
    def infer(self, observation, belief):
        return belief


class CountingSyntheticProvider:
    """A non-network provider whose counter is audit evidence, not telemetry."""
    def __init__(self, result: ProviderResponse | ProviderFailure) -> None:
        self.result, self.calls = result, 0

    def interpret(self, task: Task):
        self.calls += 1
        return self.result


def synthetic_task(family: str) -> Task:
    metadata = {"m16_cohort_a": {"task_family": family, "tool_call_limit": 0 if family == "direct_answer" else 1, "requires_planning": False, "requires_multi_tool": False, "requires_dependent_multistep": False, "requires_recovery": False}}
    if family == "direct_answer":
        return Task(Goal("return the synthetic value", ("answer",)), {"value": "synthetic-answer"}, metadata=metadata)
    return Task(Goal("perform synthetic arithmetic", ("answer",)), {"operation": "add", "operands": [2, 3]}, metadata=metadata)


def _registry(selected: bool = True) -> InferenceStrategyRegistry:
    registry = InferenceStrategyRegistry()
    if selected:
        registry.register(InferenceStrategy("synthetic_calculator", "Synthetic audit capability", ("calculator",)), _IdentityInference())
    return registry


def _step_input(task: Task) -> AgentStepInput:
    return AgentStepInput(EvaluationCase("synthetic.audit", task), EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT, {"audit": "synthetic"}), EvaluationBudgetState(EvaluationBudget(2, 1)))


def _resolver(provider_result: ProviderResponse | ProviderFailure, selected: bool = True):
    provider = CountingSyntheticProvider(provider_result)
    return provider, M13SessionAdmissionResolver(TaskInterpreter(provider), _registry(selected))


def _action_name(result) -> str:
    return result.action.action_type.value


def synthetic_matrix() -> list[dict[str, Any]]:
    """Exercise candidate public paths; never reads a formal Task or provider."""
    valid = ProviderResponse({"intent": "synthetic", "required_capabilities": ["calculator"], "constraints": {}, "evidence": {}})
    malformed = ProviderResponse({"missing": "intent"})
    unknown = ProviderResponse({"intent": "synthetic", "required_capabilities": ["unknown"], "constraints": {}, "evidence": {}})
    cases = [
        ("provider_interpreter_failure", synthetic_task("direct_answer"), ProviderFailure(ProviderFailureCategory.UNAVAILABLE, {"reason": "synthetic"}), True, 2),
        ("malformed_structured_proposal", synthetic_task("direct_answer"), malformed, True, 2),
        ("proposal_validation_failure", synthetic_task("direct_answer"), unknown, True, 2),
        ("meta_inference_nonselection", synthetic_task("direct_answer"), ProviderResponse({"intent": "synthetic", "required_capabilities": [], "constraints": {}, "evidence": {}}), False, 2),
        ("valid_direct_answer", synthetic_task("direct_answer"), valid, True, 2),
        ("valid_calculator", synthetic_task("controlled_single_tool"), valid, True, 2),
        ("private_session_max_cycles", synthetic_task("direct_answer"), valid, True, 0),
    ]
    rows = []
    for name, task, provider_result, selected, cycles in cases:
        provider, resolver = _resolver(provider_result, selected)
        step = M16MINDSessionEvaluationAdapter(resolver, max_cycles=cycles).step(_step_input(task))
        rows.append({"candidate": name, "provider_calls": provider.calls, "admission_outcome": "selected" if step.action.action_type is not EvaluationActionType.FAIL or name.startswith("valid") else "non_selected_or_failed", "integration_selected": str(step.action.action_type is not EvaluationActionType.FAIL).lower(), "private_session_reached": str(name.startswith("valid") or name == "private_session_max_cycles").lower(), "policy_reached": str(step.action.action_type in {EvaluationActionType.ANSWER, EvaluationActionType.TOOL_CALL}).lower(), "action_type": _action_name(step), "tool_calls": 1 if step.action.action_type is EvaluationActionType.TOOL_CALL else 0, "terminal_adapter_action": _action_name(step), "runner_category_if_terminal": M16FailureCategory.AGENT_FAIL.value if step.action.action_type is EvaluationActionType.FAIL else "not_agent_fail"})
    # The unsupported-policy branch cannot be reached from an eligible M16
    # projection, so exercise it only as a direct private-session source path.
    selected_context = IntegrationSelected(MetaInferenceDecision(MetaInferenceDecisionStatus.SELECTED, "synthetic_calculator", (DecisionEvidence("synthetic", "Synthetic selected context", {}),)))
    unsupported = Task(Goal("unsupported synthetic task", ("answer",)), {"unsupported": True})
    session = CognitiveAgentSession(max_cycles=2); session.start(unsupported, validated_context=selected_context)
    projected_failure = M16MINDSessionEvaluationAdapter._project(session.step())
    rows.append({"candidate": "private_policy_failure_not_m16_eligible", "provider_calls": 0, "admission_outcome": "preselected_synthetic_context", "integration_selected": "true", "private_session_reached": "true", "policy_reached": "true", "action_type": _action_name(projected_failure), "tool_calls": 0, "terminal_adapter_action": _action_name(projected_failure), "runner_category_if_terminal": M16FailureCategory.AGENT_FAIL.value, "evaluator_boundary": "not_reached"})
    # Positive calculator action reaching a deterministic evaluator environment boundary.
    calculator_row = next(row for row in rows if row["candidate"] == "valid_calculator")
    calculator_action = None
    provider, resolver = _resolver(valid, True)
    step = M16MINDSessionEvaluationAdapter(resolver).step(_step_input(synthetic_task("controlled_single_tool")))
    if step.action.action_type is EvaluationActionType.TOOL_CALL:
        environment = M16PrivateEvaluationEnvironment(M16PrivateEnvironmentSpecification("synthetic-calculator"))
        environment.reset(EvaluationCase("synthetic.audit", synthetic_task("controlled_single_tool")))
        calculator_action = environment.apply(step.action, EvaluationBudgetState(EvaluationBudget(2, 1), 1, 0)).feedback_type.value
    calculator_row["evaluator_boundary"] = calculator_action or "not_reached"
    return rows


def visible_formal_pattern(result_directory: str | Path) -> list[dict[str, Any]]:
    """Read only public fields from the valid restart1 JSONL."""
    records = [json.loads(line) for line in (Path(result_directory) / "formal_run_attempts_v1.jsonl").read_text(encoding="utf-8").splitlines() if line]
    mind = [r for r in records if r["baseline_id"] == "mind_lite_v1"]
    groups = Counter((r["task_family"], r["difficulty"], r["repetition"], r["failure_category"], r["agent_steps"], r["tool_calls"], r["provider_request_attempts"], r["model_calls"]) for r in mind)
    return [{"family": key[0], "difficulty": key[1], "repetition": key[2], "failure_category": key[3], "agent_steps": key[4], "tool_calls": key[5], "provider_request_attempts": key[6], "model_calls": key[7], "count": count} for key, count in sorted(groups.items())]


def _write(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)


def write_audit_outputs(result_directory: str | Path, output_directory: str | Path) -> dict[str, Any]:
    output = Path(output_directory); output.mkdir(parents=True, exist_ok=True)
    availability = [{"field": field, "persisted": value} for field, value in (("failure_category", "yes"), ("family/difficulty/repetition", "yes"), ("agent_steps/tool_calls", "yes"), ("provider request/model call counters", "yes"), ("terminal action/reason", "no"), ("M13/interpreter/validation/decision result", "no"), ("provider payload/error/status", "no"), ("session/policy/action trace", "no"), ("evaluator payload", "no"))]
    mapping = [
        {"source_branch": "provider/interpreter failure → non-IntegrationSelected", "adapter_action": "fail:m13_admission_failed", "terminal_reason": "not persisted", "runner_category": "agent_fail"},
        {"source_branch": "proposal validation failure → non-IntegrationSelected", "adapter_action": "fail:m13_admission_failed", "terminal_reason": "not persisted", "runner_category": "agent_fail"},
        {"source_branch": "Meta-Inference unavailable/rejected → non-IntegrationSelected", "adapter_action": "fail:m13_admission_failed", "terminal_reason": "not persisted", "runner_category": "agent_fail"},
        {"source_branch": "private session terminated non-completed", "adapter_action": "fail:<termination_reason>", "terminal_reason": "session-specific; not persisted", "runner_category": "agent_fail"},
        {"source_branch": "GoalAwarePolicy fail_task", "adapter_action": "fail:failed", "terminal_reason": "failed; not persisted", "runner_category": "agent_fail"},
        {"source_branch": "unsupported policy projection", "adapter_action": "fail:failed", "terminal_reason": "failed; not persisted", "runner_category": "agent_fail"},
    ]
    direct = [{"stage": stage, "mind_lite": mind, "direct_tool_calling": direct_value} for stage, mind, direct_value in (("M13 interpretation", "used", "bypassed"), ("deterministic validation", "used", "bypassed"), ("Meta-Inference admission", "used", "bypassed"), ("private compatibility projection", "used", "bypassed"), ("CognitiveAgentSession", "used after admission", "bypassed"), ("evaluator boundary", "used", "used"))]
    matrix = synthetic_matrix()
    _write(output / "persisted_field_availability.csv", availability, ["field", "persisted"])
    _write(output / "mind_formal_visible_pattern.csv", visible_formal_pattern(result_directory), ["family", "difficulty", "repetition", "failure_category", "agent_steps", "tool_calls", "provider_request_attempts", "model_calls", "count"])
    _write(output / "agent_fail_source_mapping.csv", mapping, ["source_branch", "adapter_action", "terminal_reason", "runner_category"])
    _write(output / "synthetic_candidate_path_matrix.csv", matrix, ["candidate", "provider_calls", "admission_outcome", "integration_selected", "private_session_reached", "policy_reached", "action_type", "tool_calls", "terminal_adapter_action", "runner_category_if_terminal", "evaluator_boundary"])
    _write(output / "direct_vs_mind_stage_comparison.csv", direct, ["stage", "mind_lite", "direct_tool_calling"])
    controls = [row for row in matrix if row["candidate"] in {"valid_direct_answer", "valid_calculator"}]
    _write(output / "positive_control_results.csv", controls, ["candidate", "provider_calls", "integration_selected", "private_session_reached", "policy_reached", "action_type", "tool_calls", "terminal_adapter_action", "runner_category_if_terminal", "evaluator_boundary"])
    return {"matrix": matrix, "visible": visible_formal_pattern(result_directory)}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    report = write_audit_outputs(root / "evaluation/results/m16_deepseek_v4_flash_restart1", root / "evaluation/analysis/m16_mind_failure_audit")
    print(json.dumps({"candidate_paths": len(report["matrix"]), "visible_groups": len(report["visible"])}, sort_keys=True))
