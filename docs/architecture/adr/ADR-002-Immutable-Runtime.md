# ADR-002 — Immutable Runtime State

- **Status:** Accepted
- **Date:** 2026-06-27
- **Authors:** MIND-Lite Architecture Team
- **Supersedes:** None
- **Superseded by:** None

---

# Context

The Runtime is the central runtime state of the MIND-Lite cognitive architecture.

It maintains the current execution context by holding the latest Observation and the corresponding Belief state.

During the architectural design of MIND-Lite, one key question arose:

Should the Runtime itself execute cognitive operations, or should it merely represent the current runtime state?

The project architecture already establishes the following principles:

- Observation is an immutable data model.
- Belief is an immutable data model.
- Inference is responsible for belief evolution.
- Policy is responsible for decision generation.
- Action is responsible for execution.

To preserve a clear separation of responsibilities, the Runtime should not duplicate the responsibilities of these components.

---

# Decision

The Runtime SHALL be implemented as an immutable passive state container.

The Runtime SHALL own the current runtime state, including:

- the current Observation;
- the current Belief;
- runtime metadata.

The Runtime SHALL NOT:

- perform inference;
- update beliefs;
- execute policies;
- execute actions;
- manage scheduling.

Whenever the runtime state changes, a new Runtime instance SHALL be created.

Existing Runtime instances SHALL remain unchanged.

The Runtime represents state only.

Behavior belongs to dedicated runtime services implemented in later milestones.

---

# Consequences

## Positive

- Preserves strict separation between state and behavior.
- Simplifies reasoning about runtime state.
- Enables deterministic snapshots.
- Supports reproducible experiments.
- Simplifies serialization.
- Reduces hidden side effects.

## Negative

- Runtime instances are recreated whenever the runtime state changes.
- Additional object creation may introduce minor overhead.

For the MIND-Lite prototype, this trade-off is considered acceptable.

---

# Relationship to Existing ADRs

This decision extends the architectural principles established by ADR-001.

Architecture hierarchy:

Observation
    ↓
Belief
    ↓
Runtime

All three runtime state objects are immutable.

Behavior is implemented by dedicated runtime components rather than embedded within the state models.

---

# Implementation Notes

The Runtime implementation is expected to:

- use `@dataclass(frozen=True)`;
- provide only data representation and serialization interfaces;
- expose no inference-related methods;
- expose no policy-related methods;
- expose no action-related methods.

Serialization should follow the same design principles established by Observation and Belief.

---

# Future Considerations

Future milestones may introduce dedicated runtime services, including:

- RuntimeController
- RuntimeScheduler
- RuntimeExecutor

These components are responsible for runtime behavior.

They SHALL operate on immutable Runtime instances instead of modifying Runtime objects directly.

This ADR intentionally limits the responsibility of Runtime to immutable state representation.
