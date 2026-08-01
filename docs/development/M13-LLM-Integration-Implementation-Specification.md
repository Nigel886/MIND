# M13 LLM Integration Implementation Specification

**Status:** Proposed implementation specification

## 1. Purpose and Boundary

This document freezes the implementation-facing contracts for M13 before any
code is authorized. M13 adds a bounded LLM task-interpretation path only. The
LLM proposes untrusted structured requirements; deterministic MIND components
validate them and the existing Meta-Inference engine remains the strategy
decision authority.

```text
Task -> interpreter -> untrusted proposal -> deterministic validation
     -> validated requirement -> adapter -> existing engine -> decision
     -> existing Agent path
```

M13 is opt-in. It does not add LLM calls to `MetaInferenceEngine`, direct LLM
control to `GoalDirectedAgent`, provider-specific code to core, strategy
execution, tools, runtime mutation, or evaluation experiments.

## 2. Proposed Module Structure

### Core: `src/core/`

Core contains architecture-independent, provider-free contracts and deterministic
logic:

- immutable serializable `TaskInterpretationProposal`;
- immutable serializable `ValidatedRequirement`;
- immutable serializable `CapabilitySnapshot`;
- compact immutable interpretation/validation evidence and result models;
- deterministic capability vocabulary validation, constraint normalization, and
  proposal-to-requirement projection.

Core must not import an LLM SDK, initiate network calls, retain provider state,
or depend on an external provider response format.

### Integration: `src/integration/`

Integration contains external-boundary orchestration:

- vendor-neutral `LLMProvider` protocol and bounded provider response contract;
- `TaskInterpreter`, which makes one provider call and parses untrusted output;
- `MetaInferenceAdapter`, which obtains the capability snapshot, coordinates
  validation/projection, creates an internal selection view, and calls the
  existing engine.

External provider adapters may live below `src/integration/` in future. They
must not be imported by core modules.

### Evaluation: `evaluation/`

Evaluation may later contain M13 fixtures, deterministic provider fakes,
validation harnesses, and metrics. It must consume public M13 contracts and
must not implement production provider behavior or alter Agent architecture.

## 3. Frozen Data Models

All M13 value models are frozen dataclasses or equivalent immutable values,
recursively protect nested containers, use JSON-compatible serializations, and
return fresh ordinary containers from `to_dict()`. They have no UUID or
timestamp unless a later approved use case requires one; deterministic semantic
comparison therefore excludes no unstable fields.

### 3.1 `TaskInterpretationProposal`

```text
TaskInterpretationProposal(
    intent: str,
    requested_capabilities: tuple[str, ...],
    constraints: Mapping[str, JSON-compatible value],
    interpretation_evidence: InterpretationEvidence,
)
```

It is immutable, serializable, and untrusted. `intent` is non-empty and is not
a strategy name or instruction. Capability values preserve order and reject
empty, padded, or duplicate strings. Constraints are interpretation-level data,
not Task constraints, Policy parameters, or Tool input. Evidence is compact and
must exclude hidden reasoning, raw provider payloads, runtime snapshots, and
implementation objects.

### 3.2 `ValidatedRequirement`

```text
ValidatedRequirement(
    required_capabilities: tuple[str, ...],
    normalized_constraints: Mapping[str, JSON-compatible value],
    validation_evidence: ValidationEvidence,
)
```

It is immutable, serializable, and trusted only after deterministic validation
against a `CapabilitySnapshot`. Its capabilities contain only allowed names,
with normalized order and no duplicates. Constraints are validator-approved,
recursively immutable data. It never aliases proposal or Task-owned values.

### 3.3 `CapabilitySnapshot`

```text
CapabilitySnapshot(
    strategies: tuple[StrategyCapabilityDescriptor, ...],
    vocabulary: tuple[str, ...],
)
```

The Adapter creates one logical immutable snapshot at the beginning of one
resolution invocation from the configured Registry's descriptors. It owns the
snapshot for that invocation. Validation and the resulting selection call must
use that exact snapshot, in registry order. The snapshot is transient and is
not stored in Task, RuntimeState, AgentResult, provider state, or evaluation
results. It neither registers a capability nor executes a strategy.

## 4. Explicit Result Models

Expected operational outcomes use explicit tagged variants. `None`, a missing
optional payload, and exceptions as ordinary control flow are forbidden.

### 4.1 `InterpretationResult`

```text
InterpretationResult =
    InterpretationSuccess(proposal, interpretation_evidence)
  | InterpretationFailure(category, interpretation_evidence)
```

States: `SUCCESS` and `FAILURE`. The interpreter owns this result. A failure has
no proposal and covers unavailable provider, timeout, transport failure, and
malformed response.

### 4.2 `ValidationResult`

```text
ValidationResult =
    ValidationValid(validated_requirement, validation_evidence)
  | ValidationInvalid(category, validation_evidence)
```

States: `VALID` and `INVALID`. The deterministic validator owns this result. An
invalid result has no validated requirement and covers schema, vocabulary,
duplicate, constraint, and source-Task-requirement conflict failures.

### 4.3 `IntegrationResult`

```text
IntegrationResult =
    IntegrationSelected(decision, integration_evidence)
  | IntegrationFailed(category, integration_evidence)
```

States: `SELECTED` and `FAILED`. The Adapter owns integration outcome evidence.
Only an existing `MetaInferenceDecision` with `SELECTED` status may create an
`IntegrationSelected` result. Existing valid-selection `UNAVAILABLE` and
`REJECTED` decisions become `IntegrationFailed` with a compact status reference;
the Adapter does not own or duplicate decision evidence.

Unexpected programmer misuse (for example, wrong Python object type) may remain
a normal contract violation, but expected provider, validation, and selection
outcomes must use the explicit result variants above.

## 5. Adapter Contract

The conceptual API is:

```text
class MetaInferenceAdapter:
    def resolve(
        self,
        task: Task,
        proposal: TaskInterpretationProposal,
        runtime_state: RuntimeState,
    ) -> IntegrationResult
```

`task` is mandatory because the adapter must preserve source identity and reject
a conflict with explicit Task requirements. The Adapter:

1. captures exactly one `CapabilitySnapshot`;
2. validates and projects the proposal deterministically;
3. returns `IntegrationFailed` if validation is invalid;
4. builds an internal immutable selection view from the source Task and the
   validated requirement without mutating or replacing the source Task;
5. calls the unchanged `MetaInferenceEngine.select(selection_view, runtime_state)`;
6. converts only the resulting decision status into its own integration result.

The Adapter must not execute strategies, call tools, generate Policy, modify
RuntimeState, modify `GoalDirectedAgent`, mutate Task, dynamically update a
registry, retry providers, or directly alter Agent execution.

## 6. LLM Provider and Interpreter Contract

The conceptual provider API is:

```text
class LLMProvider(Protocol):
    def interpret(self, task: Task) -> ProviderResponse
```

`ProviderResponse` is bounded, serializable, untrusted response data; it is not
a proposal and carries no MIND execution authority. A `TaskInterpreter` calls
the provider once per interpretation request, converts a response to
`InterpretationResult`, and never passes raw provider output to validation,
engine, or Agent.

There are no retries, fallback providers, hidden memory, provider-specific core
logic, direct Tool access, or provider-originated runtime mutation. The provider
must be vendor-neutral; deterministic fake providers return the same bounded
response for equivalent Task values with no network I/O.

## 7. Error Model and Evidence Ownership

| Failure | Owner | Generated when | Serialization |
| --- | --- | --- | --- |
| `InterpreterFailure` | TaskInterpreter | provider unavailable, timeout, transport or malformed response | compact category and interpretation evidence only |
| `ValidationFailure` | deterministic validator | schema, unknown capability, duplicate, constraint, or Task conflict | compact category and validation evidence only |
| `MetaInferenceFailure` | existing engine then Adapter boundary | valid requirements have no matching or multiple matching strategies | engine retains DecisionEvidence; Adapter stores only compact status/category |

Interpretation evidence is owned by the interpreter; validation evidence by the
validator; decision evidence by MetaInferenceEngine; integration evidence by the
adapter; and execution evidence by the Agent/execution layer. No component
stores another layer's private evidence object. No failure contains raw provider
responses, hidden reasoning, runtime objects, tools, strategies, or Agent
records.

## 8. Future Mock and Testing Strategy

No tests are added by this specification. The future implementation stage must
provide a deterministic fake provider: equivalent Task input maps to one fixed,
serializable response and never performs network I/O.

Required future coverage includes:

- proposal/result schema, immutability, serialization, and deterministic
  equality;
- invalid/unknown capability and constraint rejection;
- provider unavailable, timeout, and malformed-response failure results;
- one-snapshot validation/selection behavior and Task conflict rejection;
- Adapter non-execution and evidence-boundary behavior;
- unchanged M9 `select`, registry behavior, GoalDirectedAgent behavior, and
  M12 compatibility paths.

## 9. Evaluation Preparation

Future evaluation interfaces may consume compact results for interpretation
validity, validation accuracy, decision correctness, explicit failure handling,
and evidence consistency. Interpretation quality is separate from Agent
execution quality and task completion. This specification introduces no
experiment, metric implementation, intelligence score, hidden-reasoning metric,
or broad capability claim.

## 10. Compatibility and Implementation Gate

M13 must preserve `MetaInferenceEngine`, `InferenceStrategyRegistry`, and
`GoalDirectedAgent` public APIs and all existing M9/M12 behavior. Existing users
continue to use the current direct engine/Agent path. M13 provider integration
is opt-in.

Before code begins, the project owner must approve exact module filenames,
concrete schemas/enums, serialization/error messages, provider configuration,
timeout value, privacy/network policy, snapshot mechanics, deterministic mock
fixtures, and the staged implementation/test scope.
