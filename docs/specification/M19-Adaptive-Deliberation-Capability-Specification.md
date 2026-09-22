# M19 — Adaptive Deliberation and Resource-Aware Control

## Status

**SPECIFICATION** — Issue #209 freezes the capability contract only. It does
not introduce runtime code, a provider call, a benchmark, calibration, formal
execution, or a claim of performance, equivalence, or superiority.

## Purpose and Architectural Position

M19 specifies a deliberation-control layer that decides whether the runtime
should continue reasoning, perform a semantic action, seek observation,
replan, answer, or stop. It extends neither the meaning nor the mutability of
the existing `Observation`, `Belief`, and `RuntimeState` values. It consumes a
sanitized, immutable projection of their current state and returns a typed,
non-executing decision.

The capability sits between inference/state admission and policy or execution
admission. It is distinct from Meta-Inference: M9 selects a capability under
deterministic validation, whereas M19 controls the next deliberation step for
an already admitted runtime. It is also distinct from evaluation: evaluator
truth, private scoring data, and benchmark completion labels are never inputs.

## Capability Contract

The future control contract is:

```text
current immutable runtime state + epistemic state + resource state
    -> typed deliberation decision + compact provenance
```

The decision is pure: it makes no tool, provider, environment, calibration, or
formal-execution call; it does not mutate `Belief`, `RuntimeState`, a budget,
or a failure history. Execution remains owned by the existing policy/action or
environment boundary. A controller may admit a decision and then separately
ask the appropriate existing component to execute it.

### Semantic decisions

The decision vocabulary is closed for the initial contract:

| Decision | Meaning | Execution implication |
| --- | --- | --- |
| `CONTINUE_REASONING` | Another bounded internal reasoning transition has sufficient expected value. | No external action is implied. |
| `ACT` | A policy-owned semantic action should be considered for separate execution. | Does not execute a tool or provider. |
| `OBSERVE` | Additional admissible external information is required. | Requests observation through the existing environment boundary. |
| `REPLAN` | Current action framing is insufficient and a new bounded plan/policy framing is required. | Does not itself create or execute a plan. |
| `ANSWER` | The runtime should submit a terminal answer according to the existing answer contract. | Submission is separate; it is not a correctness claim. |
| `STOP` | Further progress is not admitted under the current state and resource constraints. | Requires explicit terminal classification. |

These are semantics, not prescribed Python class or module names. Later issues
may select representations only if they preserve this contract.

### Deliberation signals

The contract recognizes these signal categories:

- **Observable or runtime-derived:** belief version/stability evidence,
  admitted observations, completed transitions, resource counters, resource
  limits, and typed environment/failure outcomes.
- **Model estimates:** uncertainty, expected information gain, expected
  action or task value, and estimated resource cost. Estimates must identify
  their source and be finite, typed, and bounded by the receiving contract.
- **Failure and recovery history:** admitted unavailable-tool, invalid-action,
  recoverable-failure, unrecoverable-failure, policy-failure, and recovery
  attempts. This is compact event state, not hidden reasoning.

A free-form LLM confidence statement is never sufficient epistemic state.
Provider/model output, if later admitted, remains untrusted until deterministic
validation projects it into a permitted signal representation.

## Resource Accounting

M19 defines a provider-neutral resource abstraction. A resource state records
at least consumed and remaining quantities for bounded steps, tool attempts,
and provider interactions, plus extensible typed metadata. It may also contain
the limits from which remaining quantities were derived. It does not assign
monetary cost or optimize money.

Resource ownership is explicit:

- an execution/controller boundary owns admission and incrementing of consumed
  counters after the corresponding admitted event;
- the deliberation policy reads an immutable resource projection and returns no
  mutated budget;
- a decision cannot restore, increase, or make negative an exhausted resource;
- separately owned counters retain their own semantics rather than being
  silently collapsed into a single step count.

Hard resource exhaustion is a controller/termination constraint, not a soft
model preference. It preempts a decision that would require unavailable
resources.

## Stopping and Recovery Semantics

Adaptive stopping may select `STOP` or another safe non-executing transition
when the projected state indicates low expected information gain, stable belief
without sufficient expected action value, resource exhaustion, repeated
failure, failed recovery, or diminishing expected value relative to estimated
resource cost. Its reason code must distinguish the condition that admitted
the decision.

Hard stops remain separate from adaptive stopping. Examples include a terminal
session state, a non-positive applicable limit, an unrecoverable environment
outcome, an invalid contract, or a controller-enforced exhaustion condition.
They cannot be overridden by an estimated value signal.

## Decision Provenance

Every committed decision requires compact, serializable provenance containing:

- the typed decision and explicit terminal classification where applicable;
- the admitted epistemic signal values or stable references to them;
- the resource/budget projection used for the decision;
- a stable reason code;
- the transition identity and contract version.

Provenance must be deterministically serialized for equal deterministic inputs.
It must not contain chain-of-thought, hidden reasoning, private prompts,
credentials, evaluator ground truth, or raw provider exception/traceback data.

## Required Invariants

1. Existing `Observation`, `Belief`, and `RuntimeState` semantics remain
   immutable and unchanged.
2. Contract values and provenance have deterministic serialization.
3. Resource quantities are non-negative; a decision cannot resurrect an
   exhausted resource.
4. Every result is one member of the typed decision vocabulary, and terminal
   decisions have an explicit terminal classification.
5. Decision computation is side-effect free; decision admission and execution
   are distinct transitions.
6. Equal deterministic input projections produce reproducible decisions and
   provenance.
7. A committed decision has exactly one required provenance record.

## Failure Handling

The capability fails closed. Missing required signals, malformed or non-finite
numeric estimates, exhausted resources, an unavailable tool, repeated recovery
failure, policy exception, or malformed provider/model output must not invent
an action, budget, observation, success condition, or confidence value.

The receiving controller must return a typed safe fallback or explicit terminal
outcome appropriate to its existing contract, record a compact reason code,
and preserve the already admitted immutable state. Exceptions and provider
payloads are not exposed through public provenance.

## Non-Goals

M19 does not implement planning, tools, providers, benchmarks, calibration,
formal execution, online learning, autonomous self-modification, external
agent comparison, performance claims, policy equivalence, reasoning
superiority, or monetary-cost optimization. It does not make the existing
policy directly execute actions, nor does it redefine evaluator authority.

## Downstream Delivery Boundary

This specification freezes the scope for the following independently reviewed
work; none is delivered by Issue #209.

| Issue | Planned responsibility |
| --- | --- |
| #210 | Adaptive Deliberation Formalism |
| #211 | Deliberation / Epistemic State |
| #212 | Resource Accounting |
| #213 | Meta-Control Policy |
| #214 | Runtime Integration |
| #215 | Decision Provenance and Telemetry |
| #216 | M19 Validation and Closure |

Implementation may begin only through those approved follow-on issues and
must preserve the contracts and boundaries stated here.
