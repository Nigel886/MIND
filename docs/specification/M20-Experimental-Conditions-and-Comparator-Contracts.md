# M20 Experimental Conditions and Comparator Contracts

## Purpose

This specification freezes primary-comparator parity for M20. It creates no
adapter, suite, harness, pilot, calibration, provider call, empirical record,
or statistical result.

## Primary Independent Variable

The sole primary independent variable is **deliberation-control strategy**.

- **MIND-Adaptive** uses delivered frozen M19 adaptive meta-control policy and
  runtime semantics.
- **MIND-Fixed** preserves the same underlying MIND architecture wherever
  feasible but uses a prospectively frozen fixed control schedule/limit, not
  adaptive uncertainty/EIG/value-based stopping.

The fixed parameterization is deferred and must be selected before execution,
independently of results. It may not be intentionally weak. Both conditions
remain subject to the same hard safety/resource limits and runtime invariants.
Adaptive MIND may not be retuned, receive M20-only heuristics, alter stopping
post hoc, or receive hidden information.

## Shared Architecture and Fairness

| Field | Status | Requirement |
| --- | --- | --- |
| Core state, belief, runtime, action/tool infrastructure | SAME | Canonical MIND components and transition contracts. |
| Deliberation control | CONDITION-SPECIFIC | Adaptive M19 policy versus frozen fixed schedule only. |
| Tasks, public state, ordering, paired identity | SAME | Same payload and matched case/repetition identity. |
| Environment, evaluator, schemas, failure taxonomy | SAME | External, condition-neutral evaluator. |
| Tools, IDs, parameters, validation, feedback | SAME | Equivalent interface and handling. |
| Provider/configuration, timeout, retry ceiling | SAME | One deterministic configuration identity/hash. |
| Resource ceilings/accounting, provenance, randomness | SAME | Same dimensions/semantics; separate condition identity. |
| Recovery rights | SAME | Fixed condition may obey shared hard limits/feedback, not adaptive value. |

Every later condition-specific difference requires prospective justification,
condition versioning, and readiness-audit approval.

## Public Information and Tool Contract

Every comparator receives enough current public information to construct legal
interaction: case ID, task state/value, available tools/actions, stable IDs,
exact parameter schema, progress/availability, exposed resource state, and
public recovery feedback. No comparator receives target answer, evaluator
success, hidden ground truth, future trajectory, private chain-of-thought, or
condition-specific privileged hints. Public state must be complete for every
runtime rejection predicate that depends only on public information.

Tool IDs, schemas, validation, unavailable-tool/action behavior, result
visibility, and feedback are parity requirements. A comparator without tools
must declare that as a condition property rather than receive a changed
environment.

## Provider, Resources, Attempts, and Failures

Primary conditions share provider, endpoint, model, sampling, output limits,
format, timeout, retry ceiling, and reasoning mode where applicable; exact
values are frozen later. Every run records a deterministic provider
configuration identity/hash.

Common per-episode ceilings cover reasoning steps, tool attempts, provider
interactions, and decision cycles. M19 accounting governs consumption. Future
contracts must declare global/per-episode limits and failed-attempt charging;
they cannot introduce comparator-specific accounting.

Logical attempt, provider attempt, tool attempt, retry, malformed output, and
transport failure each have one declared owner—runner, provider client, or
runtime—so retries cannot occur uncounted at multiple layers. Shared typed
failure semantics cover malformed answer, invalid/unavailable action, budget
exhaustion, provider/transport failure, incomplete interaction, agent failure,
and evaluator rejection. Equivalent events cannot be condition-relabelled.

## Secondary Comparators, Pairing, and Repair

Direct, ReAct, and Plan are secondary only. Later contracts must state their
role, tool access, explicit planning/reasoning, and descriptive/inferential
status. They inherit public-information, provider, environment, evaluator,
provenance, and no-privilege requirements, and cannot redefine primary success.

Primary cases use matched case ID, payload, environment initialization,
evaluator, and repetition/cluster identity wherever feasible. Condition
identity remains separate; conceptual initial identities are
`m20_mind_adaptive_v1` and `m20_mind_fixed_v1`. Any material post-collection
change creates a new condition/result namespace. Original records stay
immutable; a defect requires diagnosis and a separate corrected condition, not
merging repaired and original records.

## Downstream Dependencies

#219 inherits public-state and pairing rules; #220 common accounting; #221
condition identity/pairing; #222 isolation/parity enforcement; #223 executable
conformance audit. None is implemented or authorized here.
