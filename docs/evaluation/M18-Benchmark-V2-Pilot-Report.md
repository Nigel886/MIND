# M18 Benchmark v2 Pilot Report

## Scope and Evidence Boundary

This report records the completed, authorized `m18_suite_v2` pilot execution.
It is descriptive evidence only. It does not establish comparative task
performance, superiority, inferiority, or a root cause for terminal outcomes.
Formal execution remains unauthorized.

The canonical evidence namespace is
`evaluation/m18/results/v2/pilot/m18_suite_v2`. Its admitted record-set digest
is `50caa6c9afaaf3712e10c5f75f397bb1f8306ebe12b0fd305a8f076a4a79473c`.

## Frozen Conditions

| Field | Value |
| --- | --- |
| Execution baseline | `59506751b66f22bed5106db68a51b1089975c419` |
| Suite identity | `m18_suite_v2` |
| Suite manifest hash | `ef8ac7edb2ac049d9152e7d0cb9d2d3c18a91be08ce41075a2d9808ee412ef09` |
| Split manifest hash | `af8b52a395f9e0400f68f3ef32982b9eb2657694d76910fa7383020659176c25` |
| Provider configuration hash | `0f251e14722603e6e39416374467a3598cd72e1d28673e60daf8440dd6115ee2` |
| Environment / evaluator / budget | `m18_environment_v2` / `m18_evaluator_v2` / `m18_budget_v2` |
| Runtime | `m18_shared_execution_runtime_v2` |

## Universe and Pairing Reconciliation

- Expected, admitted, and valid records: `360`; missing, duplicate, invalid,
  and unexpected records: `0`.
- Each comparator has `90` records: MIND-Lite, Direct Tool Calling, ReAct, and
  Plan-and-Execute.
- Repetitions 1–5 each contain `72` records.
- Cohorts `multi_step`, `distractor_selection`, and `recovery_correction` each
  contain `120` records; each of the 18 cases has `20` records.
- All 90 paired case/repetition cells contain all four comparator conditions.

## Terminal Outcome Reconciliation

| Outcome | Count |
| --- | ---: |
| `budget_exhausted` | 359 |
| `malformed_answer` | 1 |
| `success`, `wrong_answer`, `invalid_action_exhausted`, `recoverable_failure_exhausted`, `provider_failure`, `agent_internal_failure`, `timeout`, and other categories | 0 |

| Dimension | `budget_exhausted` | `malformed_answer` |
| --- | ---: | ---: |
| `multi_step` | 120 | 0 |
| `distractor_selection` | 120 | 0 |
| `recovery_correction` | 119 | 1 |
| `easy` | 119 | 1 |
| `medium` | 120 | 0 |
| `hard` | 120 | 0 |
| repetition 1 | 72 | 0 |
| repetition 2 | 71 | 1 |
| repetitions 3–5, each | 72 | 0 |

The single `malformed_answer` record is
`2ec15ed8a61d85fc3f0b1fda12c7ad8c930a8668be13ee639c77a6de16ede3b9`:
case `pilot.recovery_correction.easy.21012.0`, MIND-Lite, repetition 2,
recovery-correction/easy, with one logical provider call and one transport
attempt. No terminal diagnostic/reason is persisted.

## Provider Accounting

| Comparator | Records | Logical calls | Transport attempts | Outcomes |
| --- | ---: | ---: | ---: | --- |
| MIND-Lite | 90 | 183 | 183 | 89 `budget_exhausted`, 1 `malformed_answer` |
| Direct Tool Calling | 90 | 185 | 185 | 90 `budget_exhausted` |
| ReAct | 90 | 185 | 185 | 90 `budget_exhausted` |
| Plan-and-Execute | 90 | 360 | 360 | 90 `budget_exhausted` |
| **Total** | **360** | **913** | **913** | **359 `budget_exhausted`, 1 `malformed_answer`** |

Prompt tokens, completion tokens, cached tokens, total tokens, and latency are
not persisted: `token_latency_telemetry` is `null` for all 360 records. These
values are therefore reported as unavailable, not zero.

## Budget-Evidence Limitation

All 359 `budget_exhausted` records retain only their terminal taxonomy and
logical-provider/transport-attempt counters. The v2 result-record schema does
not persist action-cycle count, tool-attempt count, invalid-action count,
recoverable-failure count, last submitted action type, or a specific exhausted
limit. It is consequently not possible to mechanically determine which frozen
budget limit each record reached from the canonical evidence.

The available logical-call distribution is: Direct `2:85, 3:5`; MIND-Lite
`2:85, 3:4`; ReAct `2:85, 3:5`; Plan-and-Execute `4:90`. Transport attempts
match those logical-call counts. No further runtime-budget fields are
available.

This 359/360 budget-exhaustion concentration requires independent
post-execution validity investigation before any task-performance conclusion.
No configuration, runtime, comparator, provider, budget, or canonical record
was changed by this report.

## Formal and Historical Boundary

Formal v2 records remain `0`. Historical M18 v1, repaired Plan, and M16
evidence are outside this pilot namespace and were not modified.

## Lifecycle-Aware Validation

The v2 suite-freeze regression now distinguishes a clean pre-execution checkout
from a post-execution repository. Before authorized execution, the reserved
pilot namespace is absent. After execution, the test performs no writes and
permits the namespace only when its store manifest and every record pass the
frozen admission contract; it also requires zero formal records. This is an
evidence-lifecycle correction, not an experimental-condition change.
