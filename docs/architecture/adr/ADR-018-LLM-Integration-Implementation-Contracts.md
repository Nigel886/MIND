# ADR-018 - LLM Integration Implementation Contracts

**Status:** Proposed

## Context

ADR-015 through ADR-017 establish an LLM as an untrusted task interpreter, a
deterministic validation/projection boundary, and controlled capability
vocabulary. Existing M9 behavior is public and validated: `MetaInferenceEngine`
selects from immutable Task requirements and a registry; `GoalDirectedAgent`
optionally consumes the decision; M12 validates the existing semantics.

M13 must freeze implementation boundaries without changing existing M9 APIs,
allowing raw LLM output into selection, or making provider failure implicit.

## Decision

### 1. Meta-Inference integration boundary: adapter layer

Choose **Option B: a dedicated integration adapter**. A future
`LLMMetaInferenceAdapter` (name provisional) owns this flow:

```text
Task + RuntimeState + provider
  -> interpretation result
  -> validation result
  -> immutable selection view based on validated requirement
  -> existing MetaInferenceEngine.select(selection_view, runtime_state)
  -> integration result
```

The adapter is outside `src/core` and is the only M13 component allowed to
coordinate the interpretation, validation, and selection sequence. It does not
execute a selected strategy, call a tool, create a Policy, mutate state, or
directly control Agent execution.

The current `MetaInferenceEngine.select(task, runtime_state)` API is not
modified. The source Task remains the provenance object used by the Agent. The
adapter may construct an internal, immutable, short-lived **selection view**
with the source Task's identity and non-requirement content, but only with
validated capabilities exposed under the current selection metadata key. This
view is not returned to callers, stored in RuntimeState, or passed as the
Agent's Task.

If the source Task already has explicit `required_inference_capabilities`, they
must exactly equal the validated capabilities; otherwise the adapter returns an
explicit integration failure (`task_requirement_conflict`). It must never
silently overwrite explicit user requirements.

Option A—changing the existing engine API—is rejected because it expands an M9
public API, changes the M12-tested selection boundary, and risks compatibility
regressions. A future core API change requires a separate ADR and review.

### 2. Explicit result models

M13 uses outcome variants, not `None`, exceptions hidden as normal results, or
optional error fields. Each result has exactly one of a success or failure
variant and owns only its own evidence.

```text
TaskInterpretationResult =
    InterpretationSucceeded(proposal, interpretation_evidence)
  | InterpretationFailed(category, interpretation_evidence)

ValidationResult =
    ValidationSucceeded(validated_requirement, validation_evidence)
  | ValidationFailed(category, validation_evidence)

MetaInferenceIntegrationResult =
    IntegrationSelected(decision, integration_evidence)
  | IntegrationFailed(category, integration_evidence)
```

All future result, proposal, requirement, evidence, and category values are
immutable and serializable using the existing project conventions. Success and
failure categories are explicit stable strings or enums. A success variant
cannot contain a failure category; a failure variant cannot contain a proposal,
validated requirement, or selected decision.

`IntegrationSelected` is permitted only for a MetaInferenceDecision with
`SELECTED` status. Validated selection results with existing `UNAVAILABLE` or
`REJECTED` decisions become explicit `IntegrationFailed` outcomes whose compact
integration evidence references the decision status without taking ownership of
the decision's evidence.

### 3. Evidence ownership

- The interpreter produces only interpretation evidence.
- The deterministic validator produces only validation evidence.
- MetaInferenceEngine produces only DecisionEvidence in MetaInferenceDecision.
- The adapter produces only integration evidence about sequencing and outcome.
- GoalDirectedAgent and execution components produce only Agent execution
  evidence.

No layer stores an earlier layer's private evidence object. A result may carry a
compact public reference (for example, a status/category or schema version) but
must not copy hidden reasoning, raw provider response, runtime state, provider
object, tool object, strategy implementation, or Agent execution record.

### 4. Capability snapshot strategy

At the start of one adapter invocation, the adapter captures a logical immutable
snapshot of registered strategy descriptors and their capability vocabulary.
Validation, capability normalization, and final selection for that invocation
must use this same snapshot. The adapter must not resolve the mutable registry a
second time after validation. This prevents a registry change between validation
and selection from changing the meaning of an accepted proposal.

The snapshot is transient, contains only controlled registry data needed for
selection, and is not stored on Task, RuntimeState, AgentResult, or provider
records. It is neither dynamic capability registration nor strategy execution.

### 5. Provider runtime policy

Provider access remains isolated in the integration layer. An invocation has one
bounded provider attempt with an explicit configured timeout. Timeout,
unavailability, transport failure, and malformed response produce an
`InterpretationFailed` result; they do not trigger provider switching, implicit
retry, a default proposal, or local capability guessing.

A deterministic mock provider must perform no network I/O and return a frozen,
repeatable response for equivalent serialized requests. Future external
providers are replaceable implementations of the provider contract and cannot
be imported by core modules. Credentials, endpoint, model version, retention,
logging, exact timeout value, and user-facing configuration remain deferred but
must be frozen before any external-provider implementation.

### 6. API stability

The following existing interfaces and behavior remain compatible and unchanged:

```text
MetaInferenceEngine.select(task, runtime_state)
InferenceStrategyRegistry register/get/list behavior
GoalDirectedAgent(tool_registry, meta_inference_engine=None)
```

M8 and M12 paths continue to invoke the existing engine directly. M13 is an
opt-in integration layer and cannot become an implicit default in Agent
construction or execution.

## Alternatives

### A. Extend or replace `MetaInferenceEngine.select`

Rejected. It changes established M9 public behavior and introduces M13 provider
concepts into a deterministic core boundary.

### B. Adapter with raw LLM output passed through

Rejected. It removes the validator as a control point.

### C. Resolve capability vocabulary at validation and again at runtime

Rejected. Mutable registry changes can make validated output semantically
different at selection time.

### D. Implicit provider retry or fallback

Rejected. It obscures failure provenance and harms reproducibility.

## Consequences

The adapter keeps M9/M12 compatibility and provides explicit, auditable M13
outcomes. It adds future schema and snapshot complexity, and still faces model
drift, provider availability, latency, cost, privacy, and interpretation error
risks. Capability snapshot copying must preserve registry order and descriptor
semantics without executing implementations.

## Compatibility Considerations

No current source API, Task, RuntimeState, registry, decision model, Agent,
tool, Policy, runtime, test, or evaluation behavior changes under this ADR. The
selection view is an internal integration construct, never a replacement user
Task. Existing M12 deterministic tests remain the compatibility baseline.

## Deferred Decisions

- Exact class, module, serialization, and category names;
- exact integration-error representation exposed to the Agent;
- exact capability-snapshot construction mechanics;
- provider request schema, credentials, network/privacy configuration, and
  timeout value;
- deterministic mock fixtures and M13 test/evaluation protocol.
