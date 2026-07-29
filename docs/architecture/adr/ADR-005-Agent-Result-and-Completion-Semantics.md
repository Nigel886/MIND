# ADR-005 — Agent Result and Completion Semantics

**Status:** Accepted

## Context

M8 needs an explicit task-level outcome without turning `RuntimeState` into a
task result or moving completion behavior into Policy, runtime orchestration, or
tools. The existing bounded runtime supplies immutable state transitions but has
no completed, failed, or incomplete outcome contract.

## Decision drivers

Clear task-level status, deterministic validation, immutable and serializable
results, bounded-exhaustion semantics, compact evidence, and preservation of
the accepted Task/Goal and RuntimeState boundaries.

## Alternatives

1. Use an independent `AgentResult` and `CompletionEvaluator`.
2. Return `RuntimeState` as the task result.
3. Let `PolicyEngine` decide completion and return the result.
4. Put all completion logic in a future `GoalDirectedAgent`.

## Proposed decision

Adopt separate immutable result and evaluation models. `AgentResult` stores a
Task UUID, `AgentStatus`, optional answer, optional final RuntimeState,
`TerminationReason`, non-negative completed-cycle count, compact evidence, and
metadata. It stores the Task identity rather than the complete Task and never
stores a full execution trajectory, Policy, Tool registry, exception object, or
hidden controller state.

`AgentStatus` is a string Enum with `completed`, `failed`, and `incomplete`.
`TerminationReason` is a separate string Enum with `goal_satisfied`,
`max_cycles_reached`, `unsupported_task`, `tool_failure`, and `policy_failure`.
The valid initial combinations are: completed/goal_satisfied;
incomplete/max_cycles_reached; and failed with unsupported_task, tool_failure,
or policy_failure. Completed results require both an answer and final state.
Incomplete results require final state. A failed unsupported-task result may
have no final state when failure occurs before runtime initialization; other
failed results retain the final state reached before controlled failure.

`CompletionEvaluator` is a stateless evaluator separate from orchestration. It
accepts a Task, current RuntimeState, and optional candidate answer, and returns
an immutable `CompletionDecision` containing satisfaction, the verified answer
when satisfied, and compact evidence. It does not generate answers, generate
Policy, invoke tools, mutate state, update Belief, run loops, or suppress
unexpected exceptions. The future Agent owns converting a decision plus runtime
termination context into AgentResult.

## Status and termination model

Model-construction errors raise TypeError for wrong types and ValueError for
invalid values or inconsistent combinations. Invalid Task/Goal values already
fail construction and are not converted to AgentResult. Expected unsupported
tasks are failed results; bounded exhaustion is incomplete; controlled future
tool or policy failures are failed results. Programming defects and evaluator
defects propagate.

## Completion interpretation boundary

Goal descriptions and success criteria remain plain data, not executable
predicates. This ADR defines the evaluator boundary but does not claim general
natural-language goal interpretation. A later approved implementation must use
only explicit deterministic task/criterion conventions for direct and calculator
tasks; it must not add callable predicates or arbitrary execution.

## Consequences

Task-level outcomes become serializable and independently testable while
RuntimeState remains observation, belief, and metadata only. A compact evidence
summary and final state support validation without retaining a trajectory.

## Compatibility

Task/Goal, RuntimeState, RuntimeController, InferenceEngine, PolicyEngine, and
ActionExecutor APIs remain unchanged. No Tool, GoalAwarePolicyEngine, or
GoalDirectedAgent is introduced by this decision.

## Deferred decisions

The concrete deterministic criterion vocabulary, ToolResult, tool protocol,
goal-aware policy generation, task orchestrator, partial-output presentation,
and any future termination reasons require later M8 decisions.
