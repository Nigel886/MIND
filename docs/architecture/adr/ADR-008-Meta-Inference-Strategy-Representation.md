# ADR-008 — Meta-Inference Strategy Representation

**Status:** Accepted

## Context

M9 needs stable, immutable data to identify and describe controlled inference
choices before registration, deterministic selection, executable association, or
GoalDirectedAgent integration exists. The current repository has one stateless
`InferenceEngine.infer(observation, belief) -> Belief` implementation and no
formal strategy abstraction.

## Decision drivers

Explicit identity, safe serialization, deep immutability, reproducibility,
controlled future registry lookup, compact future decision evidence, and
preservation of all M1–M8 public contracts.

## Alternatives

1. Store executable callables, class instances, or import paths in a strategy.
2. Use one immutable data descriptor with embedded stable configuration.
3. Use separate public descriptor and configuration models immediately.
4. Create a generic Strategy abstraction shared by Tools and Policy.
5. Keep descriptors data-only and associate executable behavior explicitly in a
   later instance registry.

## Proposed decision

Adopt one public immutable, serializable data descriptor in
`src/core/inference_strategy.py`:

```python
@dataclass(frozen=True)
class InferenceStrategy:
    name: str
    description: str
    capabilities: tuple[str, ...]
    configuration: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InferenceStrategy": ...
```

`name` is a stable, case-sensitive, human-readable registry key; it is not a
generated UUID. `description` is required descriptive text. `capabilities` is a
non-empty, ordered, duplicate-free tuple of explicit strings. Configuration and
metadata are recursively immutable data mappings with string keys; configuration
is stable descriptor data, not a per-run override. The model stores no callable,
class instance, import path, module, registry, runtime object, Tool, Policy,
Agent, exception, or service handle.

Future Issue #31 owns an explicit instance registry that maps `name` to a
controlled executable implementation or configuration application path. No
dynamic imports, discovery, or global registry is allowed. Issues #30 and #32
own decision/selection data and rules; Issue #33 owns Agent integration.

## Immutability and serialization

The model recursively freezes JSON-compatible data values: mappings with string
keys, lists/tuples, and scalar `None`, `bool`, finite `int`/`float`, and `str`.
It exposes immutable mappings and tuples internally and returns fresh ordinary
dict/list containers from `to_dict()`. Unsupported or executable values are
rejected rather than serialized by `repr` or pickle. `from_dict()` requires the
three required fields, accepts omitted default mappings, ignores unknown fields
for current-project forward compatibility, and performs no type coercion.

## Consequences

M9 gains an explicit data boundary without claiming that Meta-Inference,
selection, multiple execution algorithms, or Agent integration already exists.
Two descriptors can later represent meaningful controlled semantics such as
`append_evidence_v1` (the current append/merge behavior) and
`replace_evidence_v1` (a future controlled replacement behavior). They are not
fake aliases; the second requires a later approved execution implementation.

## Compatibility

Observation, Belief, RuntimeState, InferenceEngine, RuntimeController, Policy,
Tools, Task/Goal, AgentResult, CompletionEvaluator, GoalAwarePolicyEngine, and
GoalDirectedAgent remain unchanged. No shared immutable-helper refactor is
introduced.

## Deferred decisions

Registry API and executable association; selection status, score, confidence,
uncertainty, rationale, ties, and compact decision evidence; strategy-specific
configuration semantics; strategy execution; Agent invocation timing; per-run
overrides; migration/versioning; learned routing; and comparative evaluation.
