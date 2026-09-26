# M20 MIND-Fixed Deliberation Schedule

## 1. Purpose

**SPECIFICATION ONLY** — This document completes the fixed-control detail intentionally deferred by #218. It creates no adapter, harness, provider call, pilot, calibration, formal run, statistical test, or empirical record.

## 2. Specification Gap from #218

#218 reserved the MIND-Fixed primary condition but deferred its schedule/limit parameterization. Consequently #222 cannot bind a real fixed adapter without inventing a control policy. This document supplies that missing condition-specific control contract only.

## 3. Fixed Comparator Design Principles

MIND-Fixed retains canonical MIND state, public input, provider configuration, action/tool interfaces, environment, evaluator, answer schema, resource accounting, retries, failure handling, provenance, and every hard ceiling. It differs solely by replacing M19 adaptive meta-control with the deterministic state machine below. It receives neither less public information nor fewer tool/recovery rights.

The shared action/answer proposal component is still responsible for forming a payload from the public task contract. It is not permitted to read evaluator/private state and does not select the next deliberation-control phase. The fixed controller owns phase selection.

## 4. Exact Control Schedule

For every admitted nonterminal public state, MIND-Fixed executes this ordered schedule:

1. Apply shared hard-stop, invariant, terminal, and resource checks.
2. Execute exactly one bounded CONTINUE_REASONING transition.
3. Execute exactly one commit slot using the shared public action/answer proposal interface.
4. If the resulting legal proposal is ACT or OBSERVE, execute it through the shared runtime and environment.
5. If the resulting legal proposal is ANSWER, submit it through the shared evaluator path.
6. After recoverable public feedback, execute exactly one REPLAN transition, then start the next public-state schedule.
7. After non-recoverable feedback, start the next public-state schedule; after terminal feedback, terminate.

A commit slot has no adaptive skip, extension, or reordering. It accepts one typed legal proposal from the shared public interface. An ACT/OBSERVE/ANSWER type is payload content selected by that shared task-solving interface; the fixed controller does not rank uncertainty, information gain, value, quality, or stopping alternatives to decide when to request it.

## 5. Exact Parameter Values

| Parameter | Frozen value |
| --- | --- |
| Schedule identity | m20_fixed_cycle_schedule_v1 |
| Reasoning transitions before each commit slot | 1 |
| Commit slots per admitted public state | 1 |
| Proposal attempts per commit slot | 1 |
| REPLAN transitions after each recoverable public feedback | 1 |
| Independent replan cap | none; only shared hard resource/decision ceilings bound repetition |
| Proactive adaptive stop | disabled |
| Answer admission | only in the commit slot |
| Unavailable/invalid proposal fallback | fail closed; no substitute proposal |

The absence of an independent replan cap is explicit, not a hidden default: every recoverable public feedback receives one fixed REPLAN, and the same hard ceilings that bind Adaptive bound total continuation.

## 6. Six-Decision Behavior

| Decision | Fixed behavior |
| --- | --- |
| CONTINUE_REASONING | Exactly once at the start of every admitted nonterminal public-state schedule, subject to the shared hard limits. |
| ACT | Permitted only as the single legal proposal in the commit slot; payload is validated and executed through the shared runtime/environment. |
| OBSERVE | Permitted only as the single legal proposal in the commit slot; it uses the same public capability/schema/feedback contract as Adaptive. |
| REPLAN | Exactly once immediately after each recoverable public feedback; no expected-value or recovery-value comparison is performed. |
| ANSWER | Permitted only as the single legal proposal in the commit slot and is evaluated only by the official evaluator. |
| STOP | Issued for shared hard stop, terminal stop, no legal proposal, or invalid state; it is never selected from an adaptive estimate. |

## 7. Hard-Limit Behavior

M19 hard precedence always overrides the schedule. Exhausted applicable resources, unrecoverable failure, committed terminal state, unavailable legal continuation, and invariant breach stop or answer according to the delivered M19 runtime semantics. The fixed schedule cannot create capacity, bypass a ceiling, retry outside the shared ownership model, or convert a hard stop into further reasoning.

## 8. Invalid-State Behavior

Missing required public contract fields, malformed proposals, invalid resource state, unavailable capability, or runtime/policy invariant failure fail closed using the established typed outcome. A rejected proposal does not trigger another proposal attempt, a hidden repair, or an adaptive fallback. An invalid interaction remains separate from provider or infrastructure failure.

## 9. Non-Adaptive Guarantee

The controller does not read or compute uncertainty, expected information gain, expected value, task-quality estimate, learned confidence, recovery value, observed M20 performance, or an adaptive stopping rule. Its next phase is determined solely by its fixed position in the schedule and typed public feedback class. M19 hard safety and resource checks remain shared runtime enforcement, not condition-specific adaptation.

## 10. Fairness Rationale

The schedule is a credible fixed-control control rather than a strawman: it grants one bounded reasoning opportunity before every public commitment, permits the same action, observation, answer, and recovery interfaces, and preserves all shared ceilings. One reasoning transition and one commit slot make the comparator simple and reproducible while avoiding arbitrary extra deliberation, fixed-depth task assumptions, tool denial, or lower budgets. The fixed recovery response preserves recovery access without optimizing its expected value.

These values are prospective design choices derived from M19’s bounded transition semantics and M20’s requirement to isolate control strategy. They were not selected from M20 outcomes and may not be retuned from pilot/calibration/formal evidence.

## 11. Condition Identity and Version

The completed condition identity is m20_mind_fixed_v1 with schedule identity m20_fixed_cycle_schedule_v1. The companion primary condition remains m20_mind_adaptive_v1. Any material schedule change after empirical collection requires a new fixed-condition identity and result namespace; prior evidence remains immutable.

## 12. Relationship to #217–#221

This schedule preserves the primary contrast, binary quality endpoint, absolute 0.05 preservation margin, provider-interaction primary resource endpoint, MRE of 0.25 interactions per attempted episode, alpha, power, gatekeeping, pairing, missingness, and rerun rules. It changes none of the scientific contracts; it only supplies the missing executable fixed-control configuration.

## 13. #222 Unblock Criterion

#222 is unblocked to implement a MIND-Fixed adapter only if it binds this exact schedule identity and all declared values, uses the delivered M19/shared runtime boundaries, and rejects absent or mismatched fixed-control configuration. It must not add a default, callback, or alternate fixed policy.

## 14. Explicit Exclusions

This contract does not authorize implementation, provider execution, a fake or empirical suite run, parameter tuning, endpoint changes, M19 modification, comparator retuning, pilot/calibration, formal execution, or statistical analysis.
