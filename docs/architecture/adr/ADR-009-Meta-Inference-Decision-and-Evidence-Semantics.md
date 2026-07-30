# ADR-009 - Meta-Inference Decision and Evidence Semantics

**Status:** Accepted

## Context

Issue #29 introduced the immutable InferenceStrategy descriptor, which answers
which controlled strategies may exist. M9 also needs a durable, auditable data
boundary for the result of a future selection: which strategy was selected, or
why no strategy was selected. This boundary must not implement the registry,
selection algorithm, inference execution, runtime transition, or Agent
integration.

## Decision

Adopt three immutable, serializable M9 public types in
src/core/meta_inference.py: MetaInferenceDecisionStatus with selected,
unavailable, and rejected values; DecisionEvidence with evidence_type,
description, and optional data mapping; and MetaInferenceDecision with status,
selected_strategy, ordered evidence, and optional metadata.

Both value models provide to_dict() and from_dict(). DecisionEvidence records
compact deterministic facts that explain a selection result. Its description is
the human-readable rationale; a separate decision-level rationale field is not
introduced. Evidence data and decision metadata are recursively immutable,
JSON-compatible mappings with string keys, and serialization returns fresh
ordinary containers.

selected_strategy is a stable InferenceStrategy.name reference, not an embedded
descriptor. It is required and non-empty only for selected; it must be None for
unavailable and rejected. Every decision requires at least one evidence item.
unavailable means no controlled strategy is available for the selection context;
rejected means the future selector declined that context under its explicit
policy. Neither status represents Tool, inference, runtime, or Agent execution
failure.

Confidence and uncertainty are deferred to Issue #32. Without a defined
selection algorithm or calibrated interpretation, numeric values would imply
unsupported semantics. Evidence items have no identity or timestamp, and they
must not embed RuntimeState, trajectories, Tool history, logs, exceptions, or
executable objects.

## Alternatives

1. Embed the entire InferenceStrategy in every decision.
2. Reference its stable name only.
3. Use unstructured dictionaries for decision and evidence.
4. Reuse AgentResult evidence.
5. Add mandatory confidence and uncertainty now.

The decision selects alternative 2 with dedicated typed data models. This avoids
duplicated strategy configuration, keeps evidence schema explicit, separates
selection rationale from task-execution history, and defers unsupported
probabilistic semantics.

## Consequences

Issue #31 owns controlled registration, lookup, availability, and executable
association. Issue #32 owns deterministic selection, ranking, scoring, ties,
and any calibrated confidence or uncertainty. Issue #33 owns Agent dependency
injection, invocation, state transition, AgentResult evidence, and failure
mapping. Existing M1-M8 APIs and state models remain unchanged.

## Compatibility and deferred decisions

Unknown serialized fields may be ignored for forward compatibility, consistent
with current immutable data models. Future decisions include score/confidence
meaning, uncertainty representation, registry identifiers, richer evidence
taxonomy, strategy versioning, learned routing, and comparative evaluation.
