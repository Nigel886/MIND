# ADR-007 — Goal-Directed Agent Orchestration

**Status:** Accepted

## Context

M8 now has immutable Task/Goal, result/completion, local Tools, and goal-aware
Policy generation but lacks a task-level execution owner.

## Decision

Introduce a behaviorally stateless `GoalDirectedAgent` above RuntimeController:

```python
GoalDirectedAgent(tool_registry: ToolRegistry)
run(task: Task, max_cycles: int) -> AgentResult
```

The caller owns registry composition and CalculatorTool registration. The Agent
uses only `RuntimeController.initialize()`, `apply_inference()`, and `update()`;
it does not use `apply_decision()`, `run_cycle()`, or `run()`. This prevents the
prototype PolicyEngine/ActionExecutor path from competing with GoalAwarePolicy.

Each run validates inputs, derives a private `task` Observation containing Task
UUID, Goal serialization, input, context, and constraints, initializes state,
and then performs at most `max_cycles` task-level cycles. A cycle is one
goal-aware Policy generation, consumption, optional Tool invocation and result
inference, then candidate-answer completion evaluation.

`produce_answer` evaluates its candidate without changing RuntimeState. A
nonmatching direct candidate returns incomplete immediately because repeating
the same deterministic policy cannot change state. `call_tool` resolves through
the injected registry, executes the Tool, adapts ToolResult to Observation,
applies inference, then evaluates ToolResult output. `fail_task` returns failed
unsupported-task with the initialized final state. Zero cycles is allowed and
returns incomplete with zero cycles and initialized state.

Completed results use goal_satisfied, current state, candidate answer, and
compact policy/completion evidence. Incomplete uses max_cycles_reached and no
trajectory. Unknown registry Tool or failed ToolResult maps to TOOL_FAILURE;
known malformed internal Policy output and unknown actions map to POLICY_FAILURE.
Unexpected programming exceptions propagate.

## Alternatives

Putting task orchestration in RuntimeController, GoalAwarePolicyEngine, or one
combined Tool/Policy/Completion object is rejected because it mixes established
responsibilities. A hidden default registry is rejected because composition must
be explicit.

## Consequences and compatibility

RuntimeState fields and RuntimeController APIs remain unchanged; Policy remains
transient; Tools remain independent from ActionExecutor; CompletionEvaluator
alone validates satisfaction; AgentResult is assembled only here. No trajectory,
retry, network, filesystem, shell, LLM, Meta-Inference, async, or concurrency
guarantee is introduced. Registry mutation during a run is unsupported.

## Deferred

Broad task semantics, retries, memory, tools beyond calculator, final demo,
Meta-Inference, and multi-agent execution.
