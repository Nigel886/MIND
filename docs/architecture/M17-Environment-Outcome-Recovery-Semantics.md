# M17 Environment Outcome and Recovery Semantics

## Status

Implemented as an additive MIND-Lite v1.1 development contract. MIND-Lite v1.1 is not released.

## Typed Outcome

`EnvironmentOutcome` is an immutable, serializable public result for external tool/environment admission and execution events. Its closed categories are:

- `SUCCESS`
- `RECOVERABLE_FAILURE`
- `UNRECOVERABLE_FAILURE`
- `INVALID_ACTION`

It uses closed `EnvironmentOutcomeReason` values rather than arbitrary routing strings. Public payload is JSON-safe, detached, and rejects evaluator truth, private judge data, prompts, credentials, hidden reasoning, and raw exception/traceback fields. An optional diagnostic is bounded public text and is non-authoritative.

## Ownership

The external registry/environment admission boundary maps unknown tools and invalid parameters to `INVALID_ACTION`. The executor/environment maps successful results, explicit transient failures, permanent failures, and execution/environment failures to their typed categories. `ToolResult` remains unchanged; its bare success/error shape does not itself establish recoverability.

## Observation Integration

An outcome crosses the existing boundary as:

```text
EnvironmentOutcome -> Observation(source="agent_environment",
                                  content={"environment_outcome": ...})
```

`CognitiveAgentSession` validates this typed representation while remaining registry-free. `RuntimeController.apply_inference()` incorporates the Observation into a new immutable state. Existing legacy environment feedback remains compatible.

## Policy-Safe Exposure

The #102 `PolicyObservationView` recognizes and normalizes typed outcome observations. A policy receives only the public category, reason, payload, and bounded diagnostic through its immutable `PolicyDecisionContext`; it never receives full runtime state, evaluator completion results, expected answers, correct actions, or exception internals.

## No Automatic Recovery

This contract does not retry a tool, select an alternate action, modify a policy, or add loop orchestration. A recoverable failure is evidence available to a future recovery-aware policy. The existing session may request the next policy decision through its unchanged lifecycle, but no outcome-specific recovery decision is made by this module.

## Compatibility and Deferred Work

Direct-answer, calculator, `GoalDirectedAgent.run()`, `RuntimeController`, existing sessions, #101/#102 contracts, and M16 artifacts remain unchanged. Retry budgets, recovery policy, generalized loop control, providers, planners, and benchmark-specific failure injection are deferred.
