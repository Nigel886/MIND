# M13 LLM-Integrated Evaluation Protocol

## 1. Evaluation Objective

M13 validates the controlled architecture that uses an LLM only as an
untrusted task interpreter before deterministic validation and existing
Meta-Inference selection. The protocol evaluates:

- LLM interpretation correctness at the bounded proposal-schema boundary;
- deterministic validation and capability-vocabulary control;
- preservation of existing Meta-Inference decision behavior; and
- consistency of evidence ownership and explicit failure boundaries.

M13 does **not** evaluate or claim intelligence, reasoning ability, task-success
improvement, benchmark superiority, or general Agent capability. Those quality
questions are outside the controlled architecture evaluation and belong to a
future M14 study with separately approved execution and comparison contracts.

## 2. Research Questions

| ID | Research question | Protocol scope |
| --- | --- | --- |
| RQ1 | Can LLM-generated interpretations be transformed into validated requirements? | Provider payload parsing, immutable proposal construction, and deterministic projection. |
| RQ2 | Does deterministic validation preserve control boundaries? | Schema, capability-vocabulary, constraint-normalization, and explicit rejection semantics. |
| RQ3 | Does LLM integration preserve Meta-Inference behavior? | The selected, unavailable, and rejected semantics delegated to the unchanged `MetaInferenceEngine`. |
| RQ4 | What limitations are introduced by LLM interpretation? | Provider, interpreter, validation, snapshot, and task-requirement conflict failures. |

## 3. Controlled Baselines

Every applicable comparison uses equivalent serialized Tasks, a frozen local
registry descriptor set, a fixed capability snapshot, and the same runtime
initialization. Semantic comparisons exclude identifiers and timestamps.

### Baseline A — M12 Deterministic Meta-Inference

An explicit Task capability requirement is supplied directly to the delivered
`MetaInferenceEngine.select(task, runtime_state)` path. This is the M9/M12
selection-semantics reference.

### Baseline B — LLM Interpretation Control

```text
FakeLLMProvider
  -> TaskInterpreter
  -> deterministic validation
```

This condition isolates the untrusted-provider-output to trusted-requirement
boundary. It does not call `MetaInferenceEngine` and is **not an LLM Agent**;
it provides no Agent execution or task-capability comparison.

### Baseline C — Full M13 Controlled Selection Pipeline

```text
FakeLLMProvider
  -> TaskInterpreter
  -> deterministic validation
  -> MetaInferenceAdapter
  -> MetaInferenceEngine
```

The adapter supplies only a short-lived validated selection view and delegates
selection to the existing engine. It neither selects or executes strategies
itself nor alters `GoalDirectedAgent`, `RuntimeState`, Policy, or tools.
Where a validated requirement is equivalent to Baseline A's explicit Task
requirement, the decision status and selected strategy must be semantically
equivalent.

## 4. Metrics

The protocol permits only the following metrics over their applicable frozen
scenario categories:

- **Proposal validity:** correct acceptance or explicit rejection of the
  provider payload under the frozen proposal schema.
- **Validation rejection correctness:** correct explicit handling of invalid
  constraints and unknown capabilities.
- **Decision consistency:** equivalence of Baseline A and Baseline C decision
  status and selected strategy when their trusted requirements are equivalent.
- **Evidence consistency:** equivalent compact evidence semantics for repeated
  equivalent inputs, while preserving evidence ownership by layer.
- **Deterministic repeatability:** equivalent compact semantic outputs for
  repeated runs of the same frozen scenario.
- **Failure-boundary preservation:** provider, interpreter, validation, and
  adapter failures remain explicit and are not conflated with a
  Meta-Inference decision.

The protocol excludes task-success metrics, benchmark scores, intelligence or
reasoning scores, hidden chain-of-thought evaluation, provider latency/cost,
and capability-improvement claims.

## 5. Frozen Scenario Design

Future fixtures must be local, immutable, serializable, versioned, and
deterministically ordered. Each fixture contains a serialized Task, fixed
provider result, capability snapshot, descriptor configuration, and expected
semantic outcome. Required categories are:

| Category | Expected outcome |
| --- | --- |
| Valid interpretation | A schema-valid provider payload becomes a `TaskInterpretationProposal` and a `ValidatedRequirement`. |
| Invalid interpretation | An invalid proposal value produces an explicit interpreter failure. |
| Unsupported capability | Validation returns `unsupported_capability`; the adapter and engine are not invoked. |
| Malformed provider output | Payload-format failure is explicit; no trusted proposal is produced. |
| Successful integration | A valid unique capability reaches the engine and produces the same selection semantics as Baseline A. |
| Failure propagation | Provider failures, invalid constraints, stale snapshots, and Task/requirement conflicts retain their owning failure categories. |

Repeated equivalent scenarios are compared only through compact semantic
signatures: status/category, selected strategy when present, and owner-local
evidence semantics. Runtime objects, tool objects, strategy implementations,
full trajectories, UUIDs, timestamps, provider objects, credentials, and
hidden reasoning are excluded from stored records.

## 6. Provider Strategy and Reproducibility

`FakeLLMProvider` is the default and required provider for this first M13
architecture protocol. It returns fixed immutable results, performs no network
I/O, requires no API key, and allows reproducible deterministic scenarios.

Real LLM providers are a future extension only. They are not a hidden
dependency of M13 validation. Any later real-provider protocol must be
separately approved and record the provider and model version, request schema,
configuration, timeout, supported seed policy, revision, and applicable
privacy/retention conditions. Its observations must remain separate from the
deterministic control results defined here.

Each deterministic scenario is run repeatedly with the same serialized input
and frozen configuration. Repetition demonstrates semantic reproducibility;
it does not create independent statistical samples or support performance
claims.

## 7. Evidence and Failure Boundaries

Evidence ownership is intentionally separated:

- the provider/interpreter owns interpretation and payload-format evidence;
- the validator owns validation and normalization evidence;
- `MetaInferenceEngine` owns `MetaInferenceDecision` evidence;
- the adapter owns snapshot, conflict, and sequencing evidence; and
- Agent execution evidence remains outside this protocol.

No layer copies another layer's private evidence object. There is no implicit
fallback, retry loop, provider switching, default capability insertion,
dynamic registry mutation, direct LLM strategy selection, or strategy/tool
execution.

## 8. Relationship to M12 and M14

M12 remains the deterministic Meta-Inference baseline for decision semantics
and M8 behavioral preservation. M13 adds only an untrusted interpretation and
deterministic validation path before that existing selection authority.

M14 quality evaluation is deferred. It may consider broader task-quality or
external-provider questions only after an explicit architecture decision
defines a fair execution boundary and comparison design. This M13 protocol
does not introduce such a boundary.
