# M19 Adaptive Deliberation Formalism

## Status and Authority

**SPECIFICATION / FORMALISM** — This document is the normative source for M19
Issues #211–#215. It refines without altering the frozen [M19 capability
contract](M19-Adaptive-Deliberation-Capability-Specification.md). It defines no
implementation, provider call, benchmark, calibration, or formal run.

Existing `Observation`, `Belief`, and `RuntimeState` remain immutable. Existing
policy produces decisions; existing action and environment boundaries own
execution and outcome admission. M19 evaluation is a pure projection, not a
replacement for those boundaries.

## 1. Notation and State Spaces

At logical time `t`, the formalism consumes immutable input
`X_t = (R_t, E_t, B_t, H_t)` and returns a decision `D_t` with provenance `P_t`.

| Symbol | Meaning | Domain |
| --- | --- | --- |
| `R_t` | Runtime/cognitive projection | Finite, immutable, versioned public projection of admitted state, terminal status, and capabilities. |
| `E_t` | Epistemic state | Typed, finite signals labelled runtime-derived or validated estimate. |
| `B_t` | Resource state | Immutable capacities, consumption, remaining values, and typed cost metadata. |
| `H_t` | Failure/recovery history | Finite ordered compact admitted-outcome categories and counters. |
| `D_t` | Meta-control decision | Exactly one member of the closed set in section 4. |
| `P_t` | Provenance | Compact serializable evidence for a committed decision. |

`R_t` must not contain evaluator truth, private task data, raw provider output,
credentials, or hidden reasoning. A projection identity identifies ordered
input content and contract version without exposing private state.

### Signal domains

The formalism requires ordering and validity, not calibrated probabilities.
Normalized representations use `[0,1]`; another scale must be finite, ordered,
explicitly declared, and versioned.

| Signal | Symbol | Valid representation |
| --- | --- | --- |
| Uncertainty | `u_t` | `UNKNOWN` or finite non-negative; greater means less resolved. |
| Expected information gain | `g_t` | `UNKNOWN` or finite non-negative expected informational benefit. |
| Belief stability | `s_t` | `UNKNOWN` or finite non-negative; greater means more stable. |
| Expected task improvement | `q_t` | `UNKNOWN` or finite signed expected progress change. |
| Expected action value | `a_t` | `UNKNOWN` or finite signed value for an admissible action. |
| Estimated cost | `c_t` | `UNKNOWN` or finite non-negative cost in a declared comparable scale. |

`UNKNOWN` is typed absence, never zero or a default. `NaN`, infinity,
out-of-range values, or an absent scale/version are invalid.

## 2. Epistemic-State Semantics

`E_t` contains either deterministic/runtime-derived signals or validated
estimates. Runtime-derived signals are computed from admitted immutable
observations, beliefs, versions, transitions, and history. Estimated signals
require source class, source/version, input-projection identity, type,
finiteness, range, and scale validation before use.

Uncertainty is unresolved epistemic state under its declared estimator, not an
LLM self-confidence statement or ground truth. Information gain is expected
reduction of declared uncertainty/loss after an admissible information
transition. Stability is a declared comparison of admitted belief projections,
not proof of task completion. Task improvement and action value are expected
change in a declared public progress objective, never evaluator success.

Missing required signals use the fail-closed relation in section 8; no estimate
may be invented.

## 3. Resource and History Semantics

For every required resource kind
`K = {reasoning_steps, tool_attempts, provider_interactions}` and each versioned
extension, resource state contains

```text
b_t(k) = (capacity_t(k), consumed_t(k), remaining_t(k), metadata_t(k))
remaining_t(k) = capacity_t(k) - consumed_t(k).
```

Values are finite non-negative integers or non-negative declared quanta.
Finite capacity requires `consumed_t(k) <= capacity_t(k)`. An unbounded kind
must be explicit; it cannot be represented by a fabricated finite capacity.
Metadata is typed and versioned, may describe cost units, and never mandates
monetary accounting.

Only the controller/executor admits consumption. For admitted vector
`delta(k) >= 0`, it creates new values:

```text
consumed_(t+1)(k) = consumed_t(k) + delta(k)
remaining_(t+1)(k) = remaining_t(k) - delta(k).
```

The transition is inadmissible if any applicable remaining amount becomes
negative. Evaluation never applies `delta`. Remaining capacity increases only
in an explicitly identified new allocation/context, never within the same
allocation identity.

`H_t` records compact admitted categories/counts: unavailable action/tool,
invalid action, recoverable or unrecoverable failure, policy failure, recovery
attempt, and recovery result. Negative counters, unknown categories,
contradictory terminal outcomes, or malformed order are invalid.

## 4. Decision Space

```text
D = {CONTINUE_REASONING, ACT, OBSERVE, REPLAN, ANSWER, STOP}
```

| Decision | Semantic precondition | Terminal | Requested transition | Later payload | Must not execute |
| --- | --- | --- | --- | --- | --- |
| `CONTINUE_REASONING` | Reasoning resource and positive continuation admission. | No | One bounded internal transition. | None. | State mutation or consumption. |
| `ACT` | Admissible action/capability, resource, and value. | No | Separate action/environment execution. | Validated semantic action reference. | Tool, provider, or environment call. |
| `OBSERVE` | Admissible information source, resource, and information value. | No | Separate acquisition transition. | Validated observation request. | Acquisition or belief mutation. |
| `REPLAN` | Non-terminal revision/recovery is admitted. | No | Separate bounded framing revision. | Revision reference. | Planning, retry, or execution. |
| `ANSWER` | Explicit terminal-answer condition and emission admission. | Yes | Separate answer emission. | Existing answer payload. | Submission or judging. |
| `STOP` | Hard or adaptive stop is admitted. | Yes | No-further-action terminal transition. | Typed reason. | State mutation or success claim. |

`ANSWER` is not a correctness claim. Pure evaluation performs no payload
validation or execution.

## 5. Value and Cost of Further Deliberation

For non-terminal admissible candidate `z`, conceptual net marginal value is

```text
V_t(z) = I_t(z) + Q_t(z) + A_t(z) - C_t(z) - F_t(z).
```

`I_t` is expected information gain, `Q_t` expected task improvement, `A_t`
expected action value, `C_t` resource-adjusted cost, and `F_t` optional finite
failure/recovery penalty derived from `H_t`. A term may be omitted only if the
formalism version explicitly says it is not required; it is not silently zero.
Terms are comparable only under equal scale identity or declared deterministic
conversion. Positive value favours continuation, zero is a tie, and negative
value disfavors it. This is neither calibrated utility nor performance or
monetary optimization.

With declared finite non-negative threshold `theta_t` and diminishing-return
threshold `epsilon_t`, a candidate may be admitted if `V_t(z) > theta_t`; it
may be diminishing if `V_t(z) <= epsilon_t`. Thresholds are versioned symbolic
parameters, not tuned constants.

## 6. Stopping and Deterministic Precedence

Hard stopping dominates all estimates: invalid required input/invariant,
exhausted applicable resource, unrecoverable failure, or already committed
terminal state. A valid already-answer-terminal state returns `ANSWER`; every
other hard condition returns typed `STOP`.

Adaptive stopping is considered only after hard checks. It may select `STOP`
for low information gain, sufficient stability with no better action,
diminishing value for every candidate, or repeated unproductive recovery. It
cannot override hard stops.

The deterministic reference relation `rho_v(X_t)` is a future test oracle, not
production code. It evaluates exactly in this order:

1. Invalid `X_t` (including missing mandatory resource/history) → `STOP(invalid_input)`.
2. Committed answer terminal state → `ANSWER(terminal_answer_state)`; other terminal state → `STOP(already_terminal)`.
3. Unrecoverable history or every legal transition hard-blocked → `STOP(hard_stop)`.
4. Admitted repeated unproductive recovery/current-framing failure → `REPLAN(recovery_required)`.
5. Explicit valid answer condition → `ANSWER(answer_condition)`.
6. Strictly greatest positive-valued observation with positive gain → `OBSERVE(value_information)`.
7. Strictly greatest positive-valued action → `ACT(value_action)`.
8. Positive-valued or positive-gain reasoning → `CONTINUE_REASONING(value_reasoning)`.
9. Established adaptive stop → `STOP(adaptive_stop)`.
10. Otherwise → `STOP(insufficient_admissible_evidence)`.

Equal ranked candidates use `OBSERVE`, then `ACT`, then `CONTINUE_REASONING`.
An answer/non-terminal tie resolves at rule 5 in favour of `ANSWER`; a hard
stop always wins. Provenance records winning rule and tie/fallback state.

## 7. Missing, Invalid, and Unavailable Inputs

| Condition | Deterministic behavior |
| --- | --- |
| Missing resource, inconsistent counters/history, `NaN`/Inf, or out-of-range required input | `STOP(invalid_input)` before comparisons. |
| Missing/invalid estimate required by candidate | Candidate unavailable; it cannot win. |
| Missing uncertainty/gain | No information-seeking or reasoning decision may depend on it. |
| Unavailable action/tool/source | Associated candidate unavailable; only rule-4 recovery may replan. |
| Policy exception or malformed model/provider projection | `STOP(policy_or_model_invalid)`, unless an established controller termination is more specific. |
| Exhausted applicable resource | `STOP(hard_stop)`; no action or budget is invented. |

No numeric default, confidence, action, or resource is silently substituted.

## 8. Transition Intent and Provenance

Evaluation returns `(D_t, P_t)` without mutating `R_t`, `E_t`, `B_t`, or `H_t`.
After commitment, a separate controller may respectively: run one bounded
reasoning transition; submit validated action; request/admit an observation;
request bounded revision; emit an answer; or commit a no-further-action
terminal classification. Consumption occurs only on the associated admitted
execution transition, yielding new immutable values.

Every committed decision has exactly one deterministically serializable `P_t`:

- decision type and terminal classification;
- formalism/policy version;
- input projection identity and state/transition version;
- used epistemic values with availability, source, scale, and version;
- used resource/history projections;
- reason code and winning rule;
- tie-break/fallback indicator; and
- requested transition identity/version.

It must exclude private chain-of-thought, hidden reasoning, private prompts,
credentials, raw provider output, evaluator truth, and exception tracebacks.

## 9. Formal Invariants and Extensions

1. `D_t` is exactly one typed member of `D`.
2. Inputs are immutable; evaluation has no execution, state, resource, or history side effect.
3. Used signals and resources meet finite/range constraints.
4. Remaining resource is never negative or resurrected in one allocation identity.
5. Terminal state/decision semantics are explicit and consistent.
6. Hard-stop precedence and tie order are total and deterministic.
7. Every committed decision has compliant provenance.
8. Equal deterministic inputs and equal formalism/policy versions produce equal decisions and equivalent provenance.

Future learned policies, calibrated uncertainty estimators, and richer
non-monetary cost models may be introduced only through validated versioned
projections. M19 remains testable with `rho_v`; learned behavior is not
required.

## 10. Downstream Boundaries

| Issue | Scope only |
| --- | --- |
| #211 | Deliberation and epistemic state/data structures. |
| #212 | Resource accounting state and consumption. |
| #213 | Meta-control decision policy based on this formalism. |
| #214 | Runtime/execution integration. |
| #215 | Structured provenance and telemetry. |
| #216 | Validation and M19 closure. |

None is implemented by Issue #210.
