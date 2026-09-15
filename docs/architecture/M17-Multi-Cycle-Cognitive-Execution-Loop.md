# M17 Multi-Cycle Cognitive Execution Loop

## Status

Implemented as an opt-in MIND-Lite v1.1 development runtime. MIND-Lite v1.1 is not released.

## Controller and Environment Boundary

`CognitiveExecutionController` coordinates a bounded sequence of existing session/policy/action/observation boundaries. `CognitiveExecutionEnvironment` is provider-independent and exposes one operation:

```text
apply(CognitiveActionRequest) -> EnvironmentOutcome
```

The controller never selects tools, rewrites parameters, judges correctness, invokes a provider, or maintains a plan. Policies choose semantic actions; environments own execution/admission; evaluators remain outside the runtime.

## Capability Freeze and Initial Cycle

An ordered tuple of immutable `CapabilityDescriptor` values is frozen when the controller is created and supplied unchanged to every policy context. The first policy context has no external observation. It contains only the #102 sanitized task/runtime projections.

## Cycle Semantics

One cycle is one policy decision and processed public action. Tool-call cycles are submitted to the environment; answer cycles end with `ANSWER_SUBMITTED`. For each tool outcome the order is fixed:

```text
EnvironmentOutcome -> agent_environment Observation -> immutable inference/state transition
-> fresh sanitized policy context -> policy decision, if continuation is allowed
```

Tool `SUCCESS` does not imply task success and permits another policy decision. `RECOVERABLE_FAILURE` and `INVALID_ACTION` likewise permit policy re-invocation only within their independent budgets. The controller never chooses a retry or alternate action. `UNRECOVERABLE_FAILURE` is admitted into state and then terminates without another policy call.

## Answer and Termination Semantics

`ANSWER_SUBMITTED` means only that the policy submitted a terminal answer. It does not mean correct, complete, or evaluator-successful. Other controller reasons include unrecoverable environment failure, budget exhaustion, policy failure, and environment failure. No evaluator truth or completion judge participates.

## Budget Model

`CognitiveExecutionBudget` has finite deterministic counters:

- `max_cycles`: maximum policy/action units;
- `max_tool_calls`: maximum external tool submissions;
- `max_invalid_actions`: maximum admitted invalid-action outcomes;
- `max_recoverable_failures`: maximum admitted recoverable outcomes.

The latter three default to `max_cycles` when omitted. Counters increment after the associated action/outcome is admitted; if an outcome consumes the final allowed invalid/recoverable count, the controller terminates before another policy invocation. A tool-call limit is checked before a further external submission.

## Safety and Immutability

The controller uses the existing `RuntimeController` transition through a private session admission hook, so outcome evidence is committed before control flow classification. Prior runtime state remains immutable. Policy and environment exceptions become compact architecture-level termination results without exposing exception detail. Finite budgets prevent repeated tool, invalid-action, and recoverable-failure loops.

## Compatibility and Deferred Work

The controller is opt-in. Existing `CognitiveAgentSession.start/step/observe/terminate`, direct answer, calculator, `GoalDirectedAgent.run()`, #101–#103, and M16 behavior remain unchanged. Providers, planners, ReAct, Plan-and-Execute, dynamic capabilities, evaluator integration, benchmark tasks, and performance claims are deferred.
