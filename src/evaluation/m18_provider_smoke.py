"""Development-only real-provider contract smoke for the frozen M18 condition.

Run explicitly as ``python -m src.evaluation.m18_provider_smoke``.  Importing
this module performs no I/O, provider request, or suite access.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core.policy_context import PolicyDecisionContext
from src.core.runtime import RuntimeController
from src.core.task import Goal, Task
from src.core.tool import CapabilityDescriptor
from src.evaluation.contracts import EvaluationCase, EvaluationFeedback, EvaluationFeedbackType
from src.evaluation.execution import AgentStepInput, EvaluationBudget, EvaluationBudgetState
from src.evaluation.m18_direct_tool_calling import M18DirectToolCallingBaseline
from src.evaluation.m18_mind_policy_condition import M18MINDPolicyCondition
from src.evaluation.m18_plan_and_execute import M18PlanAndExecuteBaseline
from src.evaluation.m18_react import M18ReActBaseline
from src.evaluation.m18_shared_provider import (
    M18SharedDirectProvider, M18SharedMINDProvider, M18SharedPlanProvider,
    M18SharedProviderClient, M18SharedProviderConfiguration, M18SharedReActProvider,
)


SMOKE_OUTPUT = Path("evaluation/m18/provider_smoke/m18_shared_provider_smoke_v1.json")


def _synthetic_inputs() -> tuple[Task, tuple[CapabilityDescriptor, ...], AgentStepInput]:
    """Create fresh non-suite inputs whose only purpose is decoder validation."""
    task = Task(Goal("return a synthetic acknowledgement", ("return one JSON-compatible acknowledgement",)),
                {"synthetic_contract_marker": "m18_provider_smoke_only"})
    capabilities = (CapabilityDescriptor("synthetic_echo", "Synthetic Echo", "Return public synthetic input.",
                                         {"type": "object", "additionalProperties": False,
                                          "properties": {"value": {"type": "string"}}, "required": ["value"]}),)
    case = EvaluationCase("m18.provider-smoke.synthetic.v1", task)
    step = AgentStepInput(case, EvaluationFeedback(EvaluationFeedbackType.INITIAL_INPUT),
                          EvaluationBudgetState(EvaluationBudget(3, 1)))
    return task, capabilities, step


def _observation(record: Any) -> dict[str, Any]:
    """Persist metadata only: provider content may be model-produced reasoning."""
    return {"requested_model": record.requested_model, "returned_model": record.returned_model,
            "finish_reason": record.finish_reason, "prompt_tokens": record.prompt_tokens,
            "completion_tokens": record.completion_tokens, "total_tokens": record.total_tokens,
            "cached_tokens": record.cached_tokens, "transport_attempts": record.transport_attempts,
            "logical_call_id": record.logical_call_id, "infrastructure_status": record.infrastructure_status,
            "latency_ms": record.latency_ms}


def run_smoke(output_path: Path = SMOKE_OUTPUT) -> dict[str, Any]:
    """Make the minimum five logical calls: MIND, Direct, ReAct, planner, executor."""
    configuration = M18SharedProviderConfiguration()
    client = M18SharedProviderClient(configuration)
    task, capabilities, step = _synthetic_inputs()
    statuses: dict[str, str] = {}
    try:
        context = PolicyDecisionContext.from_runtime(task, RuntimeController.initialize(), None, capabilities)
        M18MINDPolicyCondition(M18SharedMINDProvider(client)).decide(context)
        statuses["mind"] = "PASS"
        M18DirectToolCallingBaseline(M18SharedDirectProvider(client), capabilities).step(step)
        statuses["direct"] = "PASS"
        M18ReActBaseline(M18SharedReActProvider(client), capabilities).step(step)
        statuses["react"] = "PASS"
        plan = M18PlanAndExecuteBaseline(M18SharedPlanProvider(client), capabilities)
        plan.step(step)  # initial planner and executor are distinct logical calls.
        statuses["plan_planner"] = "PASS"
        statuses["plan_executor"] = "PASS"
    except Exception:
        # Evidence remains auditable even on a failed adapter boundary; never retry here.
        for key in ("mind", "direct", "react", "plan_planner", "plan_executor"):
            statuses.setdefault(key, "FAIL")
    evidence = {"artifact_type": "m18_shared_provider_synthetic_smoke_v1",
                "non_benchmark": True, "provider_config_hash": configuration.config_hash,
                "requested_model": configuration.requested_model,
                "documented_model_identity": configuration.documented_model_identity,
                "thinking": dict(configuration.thinking), "adapter_contract_status": statuses,
                "logical_provider_calls": client.logical_provider_calls,
                "transport_attempts": client.transport_attempts,
                "responses": [_observation(item) for item in client.responses]}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    print(json.dumps(run_smoke(), sort_keys=True, separators=(",", ":"), ensure_ascii=False))
