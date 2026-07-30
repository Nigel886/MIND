# ADR-010 - Controlled Inference Strategy Registry

**Status:** Accepted

## Context

InferenceStrategy is immutable data describing an available controlled strategy.
MetaInferenceDecision records a selection outcome. M9 needs a local runtime
configuration boundary that can explicitly resolve a stable strategy name to
both its descriptor and a controlled inference implementation without allowing
dynamic discovery, global state, or strategy selection.

## Decision

Introduce an instance-scoped mutable InferenceStrategyRegistry in
src/core/inference_registry.py. It keeps separate private mappings from exact
strategy name to immutable InferenceStrategy and to an associated
InferenceStrategyImplementation Protocol object. The public descriptor never
contains, serializes, or mutates an executable implementation.

The minimum public API is:

- register(strategy: InferenceStrategy, implementation: InferenceStrategyImplementation) -> None
- get(name: str) -> InferenceStrategy
- get_implementation(name: str) -> InferenceStrategyImplementation
- contains(name: str) -> bool
- list_names() -> tuple[str, ...]

The Protocol describes the existing inference operation shape:
infer(observation: Observation, belief: Belief) -> Belief. The Registry never
calls it. This controlled association enables a future MetaInferenceEngine to
retrieve an approved descriptor and implementation without defining selection
or execution behavior here.

Registration is explicit, exact-name, and additive. Duplicate names raise
ValueError; replacement, merge, versioning, unregister, discovery, reflection,
dynamic import, plugins, and singleton/global registries are excluded. Invalid
types raise TypeError; invalid names/registration raise ValueError; a missing
exact-name lookup raises LookupError. Registry state is not serializable because
it contains runtime implementation association; callers serialize descriptors
individually when needed. Thread safety is deferred for the single-process
prototype.

## Alternatives

1. Store descriptors only and defer every implementation association.
2. Store descriptor and callable together.
3. Store descriptor and class/type reference.
4. Use independent descriptor and implementation registries.
5. Use an explicit instance registry with separate internal mappings and a
   minimal Protocol association.

Alternative 5 is selected. It preserves data/executable separation while giving
the future engine one controlled, testable resolution point.

## Consequences

Issue #31 owns registration and lookup only. Issue #32 owns strategy selection,
ranking, scoring, ties, confidence, uncertainty, evidence generation, and
invocation policy. Issue #33 owns Agent construction and integration. Existing
InferenceEngine remains unchanged; this registry neither replaces nor wraps it.

ToolRegistry is analogous in explicit registration, local isolation, exact
lookup, and duplicate rejection. It differs because ToolRegistry stores
executable Tools as its domain, whereas this Registry preserves the public
InferenceStrategy descriptor as pure data and exposes implementation retrieval
as a separate controlled operation.
