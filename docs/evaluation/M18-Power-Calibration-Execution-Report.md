# M18 Power Calibration Execution Report

## Execution status

The authorized prospective condition `m18_power_calibration_v1` completed on
the committed native execution-harness baseline
`ff0083f87b457d8535e904932cca8e62097496d1`. The condition contains the
frozen 48 clusters, five paired repetitions, and 480 logical runs: 240
`mind_lite_v11` and 240 `direct_tool_calling`. Formal execution was not run.
Real execution was authorized by the independent native-harness verification
in Issue #205; Issue #206 subsequently corrected the phase-specific
post-execution regression invariant without rerunning calibration.

The immediate preflight was `480/0/480/0/0/0` for
expected/valid/missing/duplicates/invalid/unexpected, with zero formal
records. It used the canonical environment `m18_environment_v3`, evaluator
`m18_evaluator_v3`, corrected comparator contract, canonical runtime/budget,
and provider configuration hash
`0f251e14722603e6e39416374467a3598cd72e1d28673e60daf8440dd6115ee2`.

## Disk reconciliation

The authoritative store re-read as `480/480/0/0/0/0`. All 48 clusters are
represented; all 240 case-by-repetition pairs contain exactly one MIND and one
Direct record; and each repetition has 96 records. The deterministic canonical
record-set digest (records sorted by logical run ID) is:

`872edfe1d9032cd5e92270cd6893f2fa6d88243050395919f6a50be91f2dd558`.

No systematic provider stop was persisted. No record was overwritten or
replaced.

## Persisted outcomes

All 480 records have terminal `answer_submitted` and evaluator outcome
`success`. MIND has 240 `answer_submitted` / 240 `success`; Direct has 240
`answer_submitted` / 240 `success`. All 48 clusters are analyzable under the
frozen outcome mapping.

## Frozen nuisance and power-mapping result

Only the admitted calibration store was used. The equal-case-weighted marginal
success estimates are MIND `1.0` and Direct `1.0`; paired `p10` and `p01` are
both `0.0`. Every empirical component of the ordered ten-element case-vector
covariance matrix is `0.0`; correlations are undefined because all marginal
variances are zero.

The prescribed 10,000-draw, seed `189000004` case bootstrap is degenerate at
these point bounds. Following the required zero-discordance fallback, the
97.5% Wilson-score upper bound for total discordance is
`0.01575391994155881` (0 of 240). It is smaller than the frozen +0.10 MRE, so
there is no MRE-compatible, mathematically feasible nuisance scenario in the
required envelope. The addendum therefore fails closed: no candidate formal N
is selected and the 100,000-universe/100,000-permutation simulation is not
run because it would have no retained scenario to evaluate.

The power-mapping input package is complete as a fail-closed decision package:
alpha `0.05`, target power `0.90`, MRE `+0.10`, two-sided MIND-versus-Direct
primary contrast, frozen eligibility/failure/multiplicity rules, canonical
digest, raw estimates, conservative bound, and no-feasible-scenario result.
Formal progression remains prohibited pending a project-owner-approved,
versioned redesign; this report does not authorize formal execution.

## Telemetry and historical integrity

The calibration record schema persists no logical-call, transport-attempt,
retry, token, latency, returned-model, or cache telemetry. Those fields are
therefore **UNAVAILABLE**, not zero. Persisted `provider_failure` outcomes are
zero and structural stops are zero.

Historical evidence remains unchanged: corrected pilot 360 records
`f572f10b3e16cfb4a4d66de9afc1a035fa46af292d24a1d0ad7615e2c113e9ff`;
original v3 360 records
`196b48cec882fd78492f82e6dc6a031da66203dacd84f62b8142e1f4d0f77e78`;
v2 canonical 360 records
`50caa6c9afaaf3712e10c5f75f397bb1f8306ebe12b0fd305a8f076a4a79473c`;
and v2 diagnostic 72 records
`2c2f3f52dfde996fba8b91e491297b7fdc7cc2f09425d3ba51595a06a0bbf0e2`.
Formal records remain zero.

## Delivery validation

Issue #206 separated the temporary pre-execution empty-store guard from the
production completed-store assertion. It preserves fail-closed empty-store
readiness while requiring exact completed reconciliation and the canonical
digest. No calibration identity was rerun during that correction. Its
provider-free final validation passed: focused 11 tests in 112.446s, unittest
715 tests in 710.461s, pytest 715 tests in 428.13s, and `git diff --check`.
