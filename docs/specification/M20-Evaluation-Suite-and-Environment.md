# M20 Evaluation Suite and Environment

## 1. Purpose

**SPECIFICATION / SUITE-DEFINITION** — This document freezes the non-empirical M20 task-suite and environment contract. It implements no suite, runner, provider adapter, pilot, calibration, formal evaluation, or statistical test. It is normative with [the M20 research question](M20-Evaluation-Question-and-Allowable-Claims.md) and [the M20 comparator contract](M20-Experimental-Conditions-and-Comparator-Contracts.md).

The suite measures whether the sole primary independent variable—adaptive versus fixed deliberation control—changes task quality and resource use under matched conditions. It contains situations in which completion, information acquisition, unnecessary action, recovery, answer timing, and finite resources can matter; it is not designed to guarantee an adaptive advantage.

## 2. Cohort Taxonomy

Each eligible case has exactly one primary cohort; optional cross-cutting tags do not alter cohort identity or scoring.

| Cohort | Scientific purpose / public state | Valid action and terminal structure | Exposed behavior and bias control |
| --- | --- | --- | --- |
| `multi_step_stateful` | Ordered, visible state transitions; state, progress, and legal actions are public. | More than one valid transition is necessary; evaluator accepts only the target terminal state or answer. | Premature answer versus continuation; include trajectory shapes that do not favor one fixed depth. |
| `information_acquisition` | A needed observable fact; public state names observations, schemas, and feedback. | Valid observation precedes valid action/answer; result becomes public after admission. | OBSERVE/continue choices; no hidden metadata identifies the observation. |
| `distractor_unnecessary_action` | Sufficient public information or irrelevant actions. | Answer may be valid without distractor; deterministic distractor feedback. | Unnecessary tool/reasoning; no undisclosed preconditions. |
| `recovery_replanning` | Publicly observable failed/invalidated route. | A plausible route can fail; public feedback preserves valid recovery. | REPLAN/recovery; failures are condition-neutral. |
| `answer_ready_early_stop` | Initial public state is sufficient. | A valid answer needs no further action. | ANSWER/STOP behavior; no required fact/action is hidden. |
| `resource_constrained` | Public finite ceilings. | A success witness fits the allocation; continuation can exhaust it. | Value-sensitive stopping; ceilings are shared and outcome-independent. |

## 3. Task Case Schema

A future suite artifact validates each canonical case against a versioned typed schema containing at least:

```text
case_id, cohort, public_task_description, initial_public_state,
available_actions_or_tools, action_tool_schemas, environment_id,
evaluator_id, task_payload_digest, public_contract_id,
private_evaluator_state, reference_witness_id, generation_or_authorship_identity
```

`case_id` and `task_payload_digest` are unique within a suite. The canonical payload is immutable after freeze. `private_evaluator_state` is held only by suite generation/evaluation and never serialized into comparator input.

## 4. Public State

At every interaction point, public state includes every datum needed to make a legal interaction: current state/value and progress; stable action/tool IDs; exact parameter schemas; availability flags; permitted capabilities; admitted exposed resource state; and observable feedback. A rejection predicate depending only on operational metadata must expose that metadata. A valid comparator is therefore never required to infer hidden task configuration, addressing the M18 defect.

## 5. Private Evaluator State

Private material is limited to reference trajectories, target terminal state or answer, evaluator success predicate, and validation/generation metadata. It must not appear in task text, state, schema, feedback, provenance, or condition-specific prompts. Target answers, target sequences, success flags, future state/trajectory, and comparator-specific hints are prohibited.

## 6. Environment Transition Model

The condition-independent environment defines `E(s_t, a_t) -> (s_(t+1), o_(t+1), status)`. Each action family declares preconditions, typed parameter validation, deterministic mutation, observable feedback, failure result, repeated/duplicate behavior, and terminal effects. Invalid or unavailable interactions do not silently mutate state.

The default environment is deterministic and replayable. If a later case needs stochasticity, its seed, generator, draw schedule, and paired control must be frozen in its payload and manifest; otherwise it is ineligible.

## 7. Tool and Action Semantics

Stable public IDs bind action/tool schemas. Availability, invalid parameters, repeated actions, duplicate calls, charge/side-effect semantics, and returned feedback are explicit per action family. No behavior is comparator-specific. M19 `ACT` and `OBSERVE` remain intents: the future controller owns execution and M19 resource admission/consumption; this specification creates neither.

## 8. Evaluator Semantics

The independent evaluator returns exactly one of `SUCCESS`, `FAILURE_OR_INCORRECT`, `INCOMPLETE`, `INVALID_ANSWER`, or `INVALID_INTERACTION`. `SUCCESS` requires the stated terminal environment state and/or answer predicate. A nonterminal exhausted episode is `INCOMPLETE`; rejected/malformed answers are `INVALID_ANSWER`; invalid interaction remains distinct from an incorrect valid attempt. Primary task quality is binary: `SUCCESS` versus all non-success outcomes. No partial credit exists unless a future versioned evaluator changes before execution.

## 9. Reachability Requirement

Every frozen template, generated class, and eligible case has a machine-checkable or deterministic private reference witness. Suite validation replays it from the public initial state using only public IDs, schemas, availability, parameters, and feedback, and must obtain `SUCCESS`. Failure excludes the case. The witness establishes `public initial state + publicly valid actions -> successful evaluator state`; it is never available to a comparator.

## 10. Reference Trajectory Rules

Reference trajectories are validation artifacts only: they support reachability, evaluator verification, and generation validation. They are never prompts, runtime hints, injected context, comparator-specific scoring shortcuts, or empirical evidence.

## 11. Pairing

For the primary `MIND-Adaptive` / `MIND-Fixed` contrast, paired executions share case ID, canonical payload, initial state, environment, evaluator, action/tool surface, resource-ceiling source, and repetition/cluster identity. Only frozen condition identity and deliberation-control strategy differ.

## 12. Repetition and Cluster Identity

No sample size is selected here. A future execution identity is `(suite_id, case_id, repetition_id, condition_id)`; stable task-level cluster identity is `(suite_id, case_id, repetition_id)` across paired conditions. Execution IDs are unique and never reused across conditions.

## 13. Suite, Environment, and Evaluator Versioning

Initial future identities are `m20_suite_v1`, `m20_environment_v1`, and `m20_evaluator_v1`; each is independently versioned and content-bound. A material post-execution change requires a new relevant identity and result namespace. Conditions remain separately identified under #218.

## 14. Manifest Contract

A future canonical, machine-readable manifest binds suite/environment/evaluator IDs and versions, eligible case IDs, cohort membership, payload digests, case count, pairing metadata, schema versions, generation/freeze identity, and its manifest digest. The later harness must reject an execution whose manifest or stated identity does not exactly match.

## 15. Inclusion and Exclusion

Eligibility requires schema validity, complete public state, unique IDs, valid action/tool contracts, deterministic evaluator integrity, and passing reference-reachability replay. Exclusion is contract-based only, never comparator-performance-based. After empirical freeze, performance-based removal is prohibited.

## 16. Failure Classification

Task/environment outcomes—`INVALID_INTERACTION`, unavailable/invalid action, malformed answer, evaluator rejection, and incomplete interaction—remain distinct from infrastructure outcomes: provider timeout, transport failure, provider-boundary parse failure, and runner crash. A future harness must preserve both typed layers and cannot collapse them into generic failure.

## 17. Generation and Freeze Rules

Procedural generation is deterministic from a frozen seed/specification and each generated case receives identical validation. Hand-authored cases record authorship and freeze identity and meet the same checks. Population freezes before empirical comparator outcomes and cannot adapt to model strengths or weaknesses.

## 18. Downstream Dependencies

#220 must bind resource/cost metrics to these task and execution identities. #221 must use case/cluster/pairing structure. #222 must enforce manifest binding, condition/environment/evaluator identities, and public/private isolation. #223 must independently verify reachability, uniqueness, manifest integrity, and absence of public-state leakage or omission. None is implemented or authorized here.
