# ADR-004 — Task and Goal Representation

**Status:** Accepted

## Context
M8 requires formal user-level requests without expanding RuntimeState or adding
execution state to immutable runtime snapshots.

## Decision drivers
Immutability, serialization, deterministic validation, M9 compatibility, M10
task datasets, and preservation of M2–M7 APIs.

## Alternatives
1. Separate Task and Goal; Task owns one Goal.
2. One Task with objective and criteria.
3. Goal in RuntimeState metadata.

## Proposed decision
Use separate immutable, serializable models in src/core/task.py. Task owns one
Goal and has UUID identity. Goal has no identity or timestamp in M8 v1.
RuntimeState remains observation, belief, metadata only. Neither model stores
execution state, Policy, Tool state, result, or trajectory.

## Consequences
Task input remains distinct from initial runtime Observation. AgentResult can
refer to Task identity later. Metadata is optional and not required semantics.
Task/Goal execution, completion, Tool use, and AgentResult are deferred.

## Compatibility
Existing runtime models, RuntimeController APIs, serialization contracts, and
98 tests remain unchanged.

## Deferred decisions
Exact result/completion/tool/orchestrator APIs; Goal identity if independently
reused; task timestamp; structured criteria beyond ordered strings.
