# ADR-003 — Runtime Orchestration Model

**Status:** Accepted

**Date:** 2026-07-27

**Decision Makers:** MIND-Lite Architecture Team

---

# Context

M4 and M5 provide stateless inference, policy generation, and action execution
components over immutable state models. The prototype requires a single owner
for coordinating those components without moving behavior into RuntimeState or
creating a second runtime abstraction.

Earlier architecture language contained two conflicts: it prohibited
RuntimeController from directly executing policies or actions, and it described
a separate `Runtime` class using constructor-based dependency injection. Those
rules conflict with the approved M6 operation in which RuntimeController
coordinates existing stateless component APIs.

This ADR complements the existing immutable RuntimeState decision. It does not
change RuntimeState's passive-state responsibility.

---

# Decision

1. RuntimeController remains the single runtime orchestration component for the
   current MIND-Lite prototype.
2. M6 extends RuntimeController through stateless coordination operations; no
   separate Runtime class is introduced.
3. Constructor-based dependency injection is deferred to a future architecture
   revision.
4. RuntimeController may delegate to InferenceEngine, PolicyEngine, and
   ActionExecutor through their established static public APIs.
5. RuntimeController shall not implement inference algorithms, belief-revision
   logic, policy-generation logic, or action-execution logic.
6. RuntimeState remains unchanged and contains only observation, belief, and
   metadata.
7. Policy is a transient decision value. It shall not be persisted in
   RuntimeState.
8. Action execution results are represented as Observation objects.
9. The approved M6 decision-integration API is:

```python
class RuntimeController:

    @staticmethod
    def apply_decision(
        runtime_state: RuntimeState,
    ) -> RuntimeState:
        ...
```

`apply_decision()` reads `runtime_state.belief`, delegates to
`PolicyEngine.generate()`, delegates the Policy to `ActionExecutor.execute()`,
and calls `RuntimeController.update()` with the returned Observation. It does
not perform inference, implement a loop, or suppress unsupported-action
`ValueError`.

---

# Rationale

Keeping orchestration in RuntimeController preserves the established separation
between immutable models and behavior components. Static delegation matches the
current stateless public APIs and avoids introducing a Runtime wrapper or a
dependency-injection framework before configurable component instances are
actually required.

The decision preserves the RFC-001B hierarchy of Observation, Inference,
Belief, Policy, and Action; the RFC-002 and RFC-003 runtime cycle remains the
long-term conceptual model without requiring its full loop in Issue #16.

---

# Consequences

## Positive

- One explicit orchestration owner exists in the current prototype.
- RuntimeState remains a minimal, immutable, serializable state model.
- Policy and action responsibilities remain independent and testable.
- Existing `initialize()`, `update()`, `apply_inference()`,
  `PolicyEngine.generate()`, and `ActionExecutor.execute()` APIs remain
  unchanged.
- Decision integration can reuse `RuntimeController.update()` and preserve its
  metadata semantics.

## Trade-offs

- Static delegation is not yet configurable through injected component
  instances.
- One `apply_decision()` call is a state transition, not a complete runtime
  lifecycle or scheduling mechanism.

---

# Alternatives Considered

## Separate Runtime Class

A new Runtime class could wire and coordinate components. It was not selected
because it duplicates RuntimeController's current orchestration role and would
add an unneeded public abstraction.

## Constructor-Based Dependency Injection

Injected component instances could support replacement and configuration. It was
deferred because all current components expose stateless static APIs and M6 does
not require pluggable instances.

## Persisting Policy in RuntimeState

Persisting Policy could expose decision history, but it would expand the
RuntimeState contract and turn a transient operation value into persistent
runtime state. It was not selected.

---

# Rejected Alternatives

- Embedding policy-generation or action-execution rules in RuntimeController.
- Adding Policy, Action, ActionResult, trajectory, or cycle-count fields to
  RuntimeState.
- Catching unsupported-action ValueError and returning a fallback state.
- Introducing a loop, scheduler, tool integration, memory, or Issue #17/#18
  behavior in Issue #16.

---

# Future Extension Boundary

Any future introduction of a Runtime class, dependency injection, pluggable
component instances, or persistent Policy state requires a separate approved
ADR. A continuous runtime loop, scheduling, tools, memory, and additional M6
issues remain outside this decision.
