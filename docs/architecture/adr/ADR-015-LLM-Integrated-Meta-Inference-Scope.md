# ADR-015 - LLM-Integrated Meta-Inference Scope

**Status:** Proposed

## Context

MIND's completed Meta-Inference layer deterministically selects registered
inference strategies from explicit task capability requirements. The current
`MetaInferenceEngine.select(task, runtime_state)` API is intentionally bounded:
it selects a strategy but neither executes it nor changes runtime state. The
optional `MetaInferenceEngine` used by `GoalDirectedAgent` preserves the M8
execution path when it is absent.

M13 explores whether an LLM can help interpret a user-level Task before the
existing deterministic selection flow. It must not make an LLM an implicit
authority over strategy selection, policy generation, tool use, or execution.

## Decision Drivers

- Preserve immutable Task, Goal, Belief, and RuntimeState boundaries.
- Preserve deterministic registry and MetaInferenceEngine semantics.
- Keep untrusted model output outside Agent and Tool execution boundaries.
- Make malformed, unavailable, and ambiguous requests explicit and auditable.
- Permit controlled, reproducible research evaluation without unsupported
  intelligence or capability claims.

## Considered Alternatives

### A. Strategy proposal generator

The LLM proposes concrete strategies or registry entries. This is rejected for
the first increment because it blurs registry governance and can make an LLM
output appear executable.

### B. Task interpreter with deterministic capability projection

The LLM proposes structured capability requirements for a Task. A deterministic
validator accepts only known, schema-valid capabilities and projects them into
the existing Meta-Inference selection boundary. This is the recommended scope.

### C. Meta-Inference decision assistant

The LLM recommends a final MetaInferenceDecision. This is deferred because it
duplicates the deterministic engine's authority and requires conflict-resolution
semantics that have not been justified.

## Proposed Decision

M13 will investigate **Option B** only:

```text
Task
  -> LLM task interpreter
  -> immutable interpretation proposal
  -> deterministic proposal validator / capability projection
  -> MetaInferenceEngine
  -> MetaInferenceDecision
  -> existing GoalDirectedAgent decision-consumption path
```

The proposal may contain a bounded, structured set of candidate required
capabilities and a compact user-visible rationale. The deterministic validator
is the trust boundary: it validates schema and allowed capability vocabulary,
then produces a transient selection-scoped capability projection. It does not
mutate or replace the original Task, assign new identity, or store data in
RuntimeState. `MetaInferenceEngine` remains the sole selector and retains its
existing SELECTED, UNAVAILABLE, and REJECTED semantics.

The LLM output must never be passed directly to Tool execution, Policy,
RuntimeController, a strategy implementation, or an AgentResult constructor.
No hidden chain-of-thought is requested, retained, or exposed; any rationale is
compact, structured, and suitable for existing evidence boundaries.

## Failure Semantics

Malformed proposals, unknown capabilities, duplicate or over-budget requests,
provider/schema failures, and unavailable models are explicit validation
failures. The design provides no silent fallback, provider switching, retry
loop, default capability insertion, dynamic registry mutation, or tool fallback.
The exact public API and error representation are deferred until a subsequent
implementation review.

## Consequences

- A future implementation may add an interpreter, immutable proposal model, and
  deterministic validator without changing the existing selection authority.
- LLM variability is constrained at a schema and vocabulary boundary, but is
  not removed; provider version drift, availability, latency, cost, privacy,
  and prompt sensitivity remain research risks.
- Agent and runtime APIs remain unchanged in this scope review.

## Evaluation Direction

Any future evaluation must compare the existing deterministic M12 baseline with
an LLM-assisted interpretation condition under identical frozen tasks,
registries, schemas, and failure handling. Valid measures include proposal
validity, rejection handling, decision/evidence consistency, bounded latency,
and bounded cost. It must not claim intelligence, reasoning superiority, or
task-success improvement from this scope alone.

## Deferred Decisions

- provider, authentication, network, and data-retention policy;
- exact proposal schema, capability vocabulary, and prompt format;
- public APIs and dependency-injection surface;
- retry, timeout, and observability policy;
- evaluation dataset, budget, and reproducibility record;
- any integration with selected-strategy execution, LLM tools, learning, or
  future milestones.

## Compatibility

This proposal leaves Task, RuntimeState, RuntimeController,
MetaInferenceEngine, InferenceStrategyRegistry, GoalDirectedAgent, Policy, and
Tool architecture unchanged. No implementation is authorized by this ADR.
