# ADR-017 - LLM Task Interpretation Contracts

**Status:** Proposed

## Context

ADR-015 scopes LLM use to task interpretation, and ADR-016 places it in a
separate integration layer. MIND currently has immutable, serializable value
model conventions, a controlled `InferenceStrategy.capabilities` vocabulary,
and a deterministic `MetaInferenceEngine.select(task, runtime_state)` API. The
current engine reads Task metadata directly and must not receive raw provider
output.

This ADR freezes conceptual interface contracts for a future M13 implementation
without changing any existing public API or authorizing code.

## Contract 1: TaskInterpretationProposal

`TaskInterpretationProposal` is an immutable, serializable, untrusted value
object produced by the Task Interpretation layer. Its contract is:

```text
TaskInterpretationProposal(
    intent: str,
    requested_capabilities: tuple[str, ...],
    constraints: Mapping[str, JSON-compatible value],
    evidence: InterpretationEvidence,
)
```

- `intent` is a non-empty, normalized interpretation label, not a strategy name
  or execution instruction.
- `requested_capabilities` preserves proposal order, rejects empty/whitespace
  values and duplicates, and is not trusted merely because it is well-formed.
- `constraints` contains only interpretation-level data and is recursively
  defensively frozen; it is not Task constraints, Policy parameters, or Tool
  input.
- `evidence` is compact interpretation evidence. It must not contain hidden
  reasoning traces, provider implementation objects, runtime snapshots, tool
  objects, or execution results.

The exact `InterpretationEvidence` field shape is deferred, but it must use the
existing project conventions: immutable, serializable, JSON-compatible data and
fresh ordinary containers from `to_dict()`.

The proposal MUST NOT select strategies, execute tools, modify Task or
RuntimeState, create an Observation, generate Policy, or enter Agent execution
directly. Equality compares only its immutable semantic values; it has no UUID
or timestamp, so equivalent deterministic mock inputs can be compared without
unstable fields.

## Contract 2: ValidatedRequirement

`ValidatedRequirement` is the trusted, immutable, serializable projection of
one proposal after deterministic validation:

```text
ValidatedRequirement(
    required_capabilities: tuple[str, ...],
    normalized_constraints: Mapping[str, JSON-compatible value],
    validation_evidence: ValidationEvidence,
)
```

- `required_capabilities` is ordered, non-empty only when the frozen selection
  policy requires a capability, contains no duplicates, and contains only
  controlled vocabulary members.
- `normalized_constraints` contains only validator-approved values. It is not
  a mutable alias of proposal or Task data.
- `validation_evidence` records the compact validation/projection outcome. It
  is neither provider interpretation evidence nor Meta-Inference decision
  evidence.

### Constraint validation clarification

Constraint validation is deterministic and domain-agnostic. Proposal
construction accepts JSON-compatible constraint mappings as untrusted input;
the validator approves a mapping only when every mapping key, at every nested
level, is a non-empty string without leading or trailing whitespace. Values
must remain JSON-compatible values already supported by the immutable model
contract. This is a structural rule only: it does not assign task-specific
meaning to a constraint key or value. A structurally invalid mapping returns
`ValidationFailure(invalid_constraint)` through the normal public validation
flow, without mutating a Proposal or relying on a private object mutation.

The relationship is one-way:

```text
untrusted TaskInterpretationProposal
              -> deterministic validation / projection
              -> trusted ValidatedRequirement
```

Validation never mutates a proposal or its source Task. Rejected output creates
an explicit validation failure; it does not produce a partial requirement,
default capability, fallback strategy, or Tool instruction.

## Contract 3: Capability Vocabulary

The controlled capability vocabulary is owned by the registered
`InferenceStrategy.capabilities` descriptors and the frozen registry supplied
to the selection environment. M13 introduces no global mutable vocabulary and
no dynamic capability registration.

Validation rules are:

1. a capability is a string with no leading/trailing whitespace;
2. empty values and duplicates are rejected;
3. proposed capability names must belong to the allowed vocabulary established
   before the interpretation attempt;
4. unknown names cause a validation failure, not an UNAVAILABLE selection;
5. registry matching remains responsible for returning UNAVAILABLE when a valid
   requirement has no matching strategy and REJECTED when it has multiple
   matches.

This distinction prevents provider vocabulary errors from being misreported as
Meta-Inference behavior.

## Contract 4: Selection Boundary and Compatibility

Raw `TaskInterpretationProposal` values must never be supplied to
`MetaInferenceEngine`. The existing public API remains unchanged:

```text
MetaInferenceEngine.select(task, runtime_state) -> MetaInferenceDecision
```

A future M13 implementation may add a distinct, explicitly named entry point
such as:

```text
MetaInferenceEngine.select_validated(
    task,
    runtime_state,
    validated_requirement,
) -> MetaInferenceDecision
```

That entry point may use Task for identity/provenance and RuntimeState for the
existing call shape, but it must derive selection requirements solely from the
validated requirement. It must not overwrite Task metadata, mutate Task or
RuntimeState, accept a raw proposal, or alter the status contract. The exact
name and whether a narrow adapter owns this boundary require approval before
implementation; no replacement of the existing `select` API is authorized.

## Contract 5: Provider Boundary

Provider concerns belong outside `src/core`. The future integration layer shall
depend on a vendor-neutral provider protocol conceptually equivalent to:

```text
TaskInterpretationProvider.interpret(request) -> provider response
```

`request` is a bounded, serializable interpretation request derived from a Task
without passing RuntimeState, ToolRegistry, Policy, Agent, or strategy objects.
The returned response is untrusted data and must be parsed into a proposal by
the interpreter boundary before validation. A deterministic mock provider must
be substitutable for tests and evaluation. No core contract names or imports an
OpenAI, Anthropic, Google, or vendor-specific SDK.

Provider API details—including authentication, endpoint, request content,
timeout, retry, model version, logging, and data retention—are deliberately
deferred and cannot be hidden behind an implicit fallback.

## Contract 6: Failure Semantics

Failures have disjoint ownership and evidence:

| Category | Examples | Required handling |
| --- | --- | --- |
| Interpreter failure | provider unavailable, timeout, malformed response | explicit interpreter failure; no proposal is trusted |
| Validation failure | invalid schema, unknown capability, invalid constraint | explicit validation failure; no validated requirement is produced |
| Meta-Inference failure | no matching strategy, multiple matching strategies | existing UNAVAILABLE or REJECTED decision after valid projection |

There is no hidden fallback, provider switching, automatic retry loop, default
capability insertion, direct strategy selection, or direct Agent execution.
The eventual public representation of interpreter and validation failure must
be frozen separately and must not reuse a MetaInferenceDecision status merely
for convenience.

## Evidence Boundary

Interpretation evidence, validation evidence, Meta-Inference decision evidence,
and Agent execution evidence are distinct values with distinct owners. A layer
may reference compact public summaries from an earlier layer only where the
future schema explicitly permits it; it must not store another layer's private
evidence object, hidden reasoning, or implementation object. This preserves
auditability without conflating why a task was interpreted, why a strategy was
selected, and what the Agent executed.

## Rejected Alternatives

- **LLM directly selecting strategy:** bypasses MetaInferenceEngine authority.
- **LLM modifying Task:** violates immutable input provenance and auditability.
- **Raw LLM output entering Agent:** removes the validation/projection boundary.
- **Provider-specific core implementation:** couples deterministic core code to
  vendor/network behavior.

## Evaluation Preparation

Future evaluation may measure proposal validity, validation success/failure,
decision correctness, explicit failure handling, and evidence consistency.
Interpretation quality must be evaluated separately from Agent execution
quality. These contracts define no intelligence score, hidden-reasoning metric,
or unrestricted capability claim.

## Consequences and Deferred Decisions

This contract preserves M8/M9 APIs and establishes an auditable path for future
LLM assistance. It also requires a future implementation review to resolve the
exact schema classes, error/outcome model, adapter versus engine entry point,
capability snapshot timing, provider request contract, privacy/network policy,
and deterministic mock fixtures.
