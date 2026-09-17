# M18 v2 Budget Diagnostic Results

> **NON-CANONICAL DIAGNOSTIC EVIDENCE**  
> **NOT PERFORMANCE EVIDENCE**

## Execution condition

Condition: `m18_v2_budget_diagnostic_v1`. The frozen universe comprised 18
pilot source cases, four comparator conditions, and one diagnostic repetition:
72 admitted diagnostic records. These records are mechanism telemetry only and
must not be used for comparator ranking or canonical performance aggregation.

Result-set digest: `2c2f3f52dfde996fba8b91e491297b7fdc7cc2f09425d3ba51595a06a0bbf0e2`.

## Terminal and exhaustion mechanisms

| Measure | Count |
| --- | ---: |
| `invalid_action_limit` | 71 |
| `none` | 1 |
| `action_cycle_limit` | 0 |
| `tool_attempt_limit` | 0 |
| `logical_provider_call_limit` | 0 |
| `recoverable_failure_limit` | 0 |
| `budget_exhausted` terminal | 71 |
| `answer_submitted` terminal | 1 |

The single non-exhausted record belonged to the MIND condition; every Direct,
ReAct, and Plan record terminated with `invalid_action_limit`.

## Completion and answer behavior

No record reached the final public state before termination: **0/72**. Thus
there is no direct prospective evidence in this tranche that an agent commonly
reaches the final public state and then continues acting instead of emitting an
answer. Answer was emitted in 1/72 records; decoder failures and provider
failures were both 0/72.

## Breakdown

| Cohort | `invalid_action_limit` | `none` |
| --- | ---: | ---: |
| multi-step | 23 | 1 |
| distractor selection | 24 | 0 |
| recovery/correction | 24 | 0 |

## Provider telemetry

The runner observed 182 logical provider calls and 182 transport attempts.
Prompt tokens, completion tokens, cached tokens, total tokens, and latency
were unavailable in the admitted diagnostic schema and are intentionally not
backfilled.

## Integrity and limitations

The canonical pilot remains separate and unchanged: 360 records with digest
`50caa6c9afaaf3712e10c5f75f397bb1f8306ebe12b0fd305a8f076a4a79473c`.
No formal records were created. This prospective diagnostic does not explain
historical canonical outcomes retrospectively and makes no intelligence,
quality, or performance claim.
