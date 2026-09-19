# M18 Corrected Pilot Report

## Status

The authorized corrected-condition pilot completed under m18_v3_comparator_contract_v2. It executed exactly 18 cases × 4 comparators × 5 repetitions = 360 admitted pilot records. Formal execution remains unauthorized.

## Reconciliation

| expected | valid | missing | duplicates | invalid | unexpected |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 360 | 360 | 0 | 0 | 0 | 0 |

Each comparator has 90 records; repetitions 1–5 have 72 records each; all 90 case × repetition cells contain four comparators. Corrected formal records remain 0.

## Outcome Taxonomy

All 360 records have terminal answer_submitted. Evaluator outcomes are success 349 and interaction_incomplete 11.

| Comparator | success | interaction_incomplete |
| --- | ---: | ---: |
| MIND-Lite | 90 | 0 |
| Direct Tool Calling | 90 | 0 |
| ReAct | 89 | 1 |
| Plan-and-Execute | 80 | 10 |

No other persisted terminal/evaluator class was observed. This report makes no comparative ranking or confirmatory inference.

## Corrected-Defect Assessment

Plan completion defect: **NO RECURRENCE EVIDENCE** for the historical exact-length plan_exhausted-before-answer condition: no plan_exhausted terminal was persisted. Ten Plan interaction_incomplete outcomes remain evaluator outcomes, not evidence that the historical cursor/answer-opportunity defect recurred. Because action traces and request phases are not persisted, the exact action-level reason is not recoverable.

Answer-type leniency: **NO RECURRENCE EVIDENCE**. No malformed_answer outcome was persisted. This is bounded outcome evidence only; strict integer decoder behavior remains established by the corrected-contract implementation and tests.

## Telemetry and Nuisance Boundary

The corrected result schema persists terminal outcome and provenance only. Logical calls, transport attempts/retries, tokens, latency, returned model, and cache telemetry are unavailable, not zero. There were no provider_failure outcomes and no persistent systematic provider stop.

Permitted pilot nuisance facts are descriptive only: MIND and Direct each have observed 90/90 success; paired MIND/Direct run-level discordances are n10 = 0 and n01 = 0. The associated dependence estimate is boundary-degenerate/unavailable. A later frozen pilot-to-power addendum must apply the protocol's conservative scenario-envelope rule; these values do not change endpoint, contrast, alpha, sidedness, MRE, eligibility, failure classification, or formal N by themselves.

## Integrity

Corrected admitted-record digest (canonical JSON of records sorted by run ID) is f572f10b3e16cfb4a4d66de9afc1a035fa46af292d24a1d0ad7615e2c113e9ff. Original v3 remains 360 records, digest 196b48cec882fd78492f82e6dc6a031da66203dacd84f62b8142e1f4d0f77e78. V2 canonical remains 360 records, digest 50caa6c9afaaf3712e10c5f75f397bb1f8306ebe12b0fd305a8f076a4a79473c; v2 diagnostic remains 72 records, digest 2c2f3f52dfde996fba8b91e491297b7fdc7cc2f09425d3ba51595a06a0bbf0e2.

## Interpretation Limit

This is corrected-pilot operational/design evidence only. It supports no formal comparative claim, superiority ranking, statistical test, or formal execution authorization.
