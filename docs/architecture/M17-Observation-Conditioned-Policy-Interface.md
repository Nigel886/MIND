# M17 Observation-Conditioned Policy Interface

## Status

Implemented as an additive MIND-Lite v1.1 development contract. MIND-Lite v1.1 is not released.

## Policy Protocol

`PolicyDecisionEngine` is a provider-independent protocol with one operation:

```text
decide(PolicyDecisionContext) -> Policy
```

It selects a decision only. It does not invoke tools, environments, providers, sessions, or runtime transitions.

## Decision Context

`PolicyDecisionContext` is immutable and contains:

- `PolicyTaskContext`: task identity, Goal description/criteria, and sanitized public task input;
- `PolicyRuntimeView`: belief version and record count, rather than the full runtime state;
- optional `PolicyObservationView`: the latest `agent_environment` observation after sanitization;
- ordered immutable `CapabilityDescriptor` values.

The caller owns capability ordering. A registry can supply descriptors through `ToolRegistry.capability_descriptors()`; a session receives the resulting tuple and remains registry-free.

## Action Boundary

Policies return the existing `Policy` model. Session projection supports only existing public action semantics:

- `produce_answer` projects to `answer`;
- `call_tool` projects to JSON-safe `tool_call`.

The registry/executor, not the policy, remains authoritative for tool existence, schemas, parameters, and execution.

## Truth-Leakage and Side-Effect Boundary

Context projections remove evaluator/private fields, including expected answers, ground truth, correct tool/action labels, completion labels, evaluator success, judge metadata, prompts, credentials, and hidden reasoning. Full `RuntimeState`, raw task input, opaque metadata, and belief evidence are not exposed.

Policy evaluation is read-only and side-effect-free: it cannot mutate session/runtime/task/observation/capability data and has no tool or environment boundary.

## Compatibility

`GoalAwarePolicyEngine.generate(task, runtime_state)` remains unchanged for existing M8/M15 callers. Its additive `decide(context)` method implements the new protocol against sanitized data, preserving direct-answer and calculator output for those supported task shapes. `CognitiveAgentSession` uses generalized policy only when an explicit keyword-only `policy_engine` is supplied; default behavior remains unchanged.

## Deferred Work

Recovery semantics, failure taxonomy, generalized loop redesign, provider-backed policies/prompts, planning, benchmark tasks, and M18 work are not part of this contract.
