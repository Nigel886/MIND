# ADR-016 - Task Interpretation Layer Architecture

**Status:** Proposed

## Context

MIND's delivered Meta-Inference layer is deterministic and selection-only.
`MetaInferenceEngine.select(task, runtime_state)` reads explicit Task capability
requirements, queries the controlled registry, and returns a
`MetaInferenceDecision`. It does not execute a strategy or alter runtime state.
`GoalDirectedAgent` optionally consumes that decision but continues its existing
execution path only after a selected result.

Natural-language requests may not contain the explicit, normalized capability
requirements expected by the existing engine. Directly connecting an LLM to
strategy selection, Agent control, runtime state, policy generation, or tools
would collapse the established control boundary and make provider output
implicitly executable. M13 therefore needs a separate interpretation boundary.

## Decision

Adopt a distinct, **integration-layer Task Interpretation architecture**. It is
not a `src/core` responsibility: core models and deterministic selection remain
provider-independent and free of external-model concerns.

```text
Natural-language Task
  -> TaskInterpreter (provider-facing adapter)
  -> TaskInterpretationProposal (immutable, untrusted)
  -> ProposalValidator / RequirementProjector (deterministic trust boundary)
  -> ValidatedRequirement (transient, immutable selection input)
  -> existing MetaInferenceEngine
  -> existing MetaInferenceDecision
  -> existing GoalDirectedAgent decision-consumption path
```

### Task interpretation layer

The TaskInterpreter converts Task-level natural-language material into a
structured proposal. It may ask an abstract LLM provider for an interpretation,
but it must not select or execute strategies, invoke tools, construct
Observations, generate Policy, modify Task, or modify RuntimeState.

### Proposal model

`TaskInterpretationProposal` is a future immutable, serializable value model.
Its minimum conceptual fields are:

- `intent`: a bounded, descriptive interpretation label;
- `required_capabilities`: an ordered immutable collection of proposed
  capability names;
- `constraints`: structured interpretation constraints, separate from Task
  constraints;
- `evidence`: compact interpretation evidence suitable for audit.

The proposal is untrusted and has no execution behavior, strategy identity,
runtime object, tool reference, UUID, timestamp, or authority to control the
Agent. Its exact public API and serialized schema remain deferred.

### Validation and projection

`ProposalValidator` and `RequirementProjector` form the deterministic trust
boundary. They validate proposal shape, vocabulary membership, ordering,
duplicates, limits, and constraint compatibility against a frozen policy. Only
a valid projection may be supplied to Meta-Inference. The projection is
selection-scoped and transient: it does not mutate the original Task, replace
its ID, or persist in RuntimeState metadata.

The existing MetaInferenceEngine must not accept raw LLM output. A future
adapter may construct an equivalent validated selection input, but it cannot
change the engine's decision authority or its SELECTED, UNAVAILABLE, and
REJECTED semantics.

### Provider boundary

Define a future provider-independent LLM provider abstraction at the integration
boundary. It must be replaceable and support a deterministic mock provider for
tests. It must not bind MIND core to OpenAI, Anthropic, Google, or any other
vendor SDK. Provider configuration, credentials, networking, timeout, retry,
logging, and data-retention decisions are deferred.

### Evidence separation

Three evidence domains remain separate:

1. interpretation evidence explains the bounded proposal and validation result;
2. Meta-Inference decision evidence explains registry capability selection;
3. Agent execution evidence explains policy, tool, completion, and termination
   behavior.

Evidence must remain compact and serializable. No hidden reasoning trace,
runtime dump, provider implementation object, or tool object may cross these
boundaries.

## Failure Handling

Malformed provider output, unavailable provider, schema failure, invalid or
unknown capability, conflicting constraints, and ambiguous interpretation are
explicit interpretation/validation failures. They cannot be silently converted
to a default capability, fallback strategy, tool call, or ordinary Agent
execution. There is no automatic provider switching, unconstrained retry loop,
dynamic registry update, or direct LLM policy control.

How future public APIs expose an interpretation failure is deferred, but it
must preserve the distinction between interpretation evidence, selection
evidence, and execution evidence.

## Alternatives Considered

### A. Direct LLM strategy selection

Rejected. It duplicates MetaInferenceEngine authority, bypasses deterministic
registry matching, and makes model output a decision authority.

### B. LLM-controlled Agent or direct LLM policy control

Rejected. It would allow an external model to affect policy, tools, and
execution without the current bounded Agent contracts.

### C. LLM modifies Task or RuntimeState

Rejected. Task is immutable user input and RuntimeState is immutable runtime
state; either mutation destroys provenance and state-boundary clarity.

### D. Put provider integration in `src/core`

Rejected. Provider/network concerns are integration concerns and must not add
external dependency semantics to deterministic core models or engines.

## Consequences

Benefits include explicit controllability, modular provider replacement,
deterministic validation, separate audit evidence, and isolation of LLM effects
for research evaluation. Risks include interpretation errors, schema mismatch,
provider dependency, model drift, latency, cost, availability, privacy, and
nondeterminism. A validator constrains authority but cannot prove semantic
correctness of an LLM proposal.

## Evaluation Preparation

Future research conditions may include:

- **A:** M12 deterministic Meta-Inference baseline;
- **B:** an LLM-only agent condition, only if separately defined without
  conflating its execution architecture with MIND;
- **C:** LLM Interpreter plus deterministic MIND Meta-Inference.

Interpretation validity, validation/failure handling, decision correctness, and
evidence consistency measure the interpretation-and-control path. Task
completion is an Agent execution outcome and must be reported separately under
matched tasks, registries, budgets, providers, and environments. These
conditions cannot justify claims about intelligence, reasoning superiority, or
general task-solving capability.

## Research Boundary

This architecture excludes autonomous learning, self-modifying agents, online
adaptation, hidden reasoning extraction, uncontrolled tool calling, direct LLM
policy control, strategy execution integration, and changes to core runtime or
Agent behavior.

## Compatibility and Deferred Decisions

This decision changes no current Python API or implementation. Task,
RuntimeState, MetaInferenceEngine, registry, Policy, tools, and GoalDirectedAgent
remain unchanged. Before implementation, a separate review must freeze the
proposal/validated-requirement schemas, allowed capability vocabulary, provider
abstraction API, failure representation, privacy/network policy, deterministic
mock contract, and evaluation protocol.
