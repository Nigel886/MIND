# DR-M18 Power Calibration Execution

## Completed calibration

Issue #199 executed the authorized native M18 power-calibration condition on
`ff0083f87b457d8535e904932cca8e62097496d1`. Initial preflight was
`480/0/480/0/0/0`; final disk reconciliation was `480/480/0/0/0/0`.
The 480 admitted records cover 48 clusters, 240 complete MIND/Direct paired
cells, and 240 runs per comparator. The canonical digest is
`872edfe1d9032cd5e92270cd6893f2fa6d88243050395919f6a50be91f2dd558`.
Authorization followed Issue #205's independent native-harness verification.

All records are `answer_submitted` / `success`. No provider failure or
systematic provider stop was persisted. The record schema does not retain
logical calls, transport attempts, retries, token use, latency, returned
model, or cache telemetry; these are UNAVAILABLE rather than zero.

## Frozen power mapping

Calibration-only estimates are MIND `1.0`, Direct `1.0`, `p10=0.0`, and
`p01=0.0`, with all empirical covariance components zero and correlations
undefined. The mandatory zero-discordance fallback gives a 97.5% Wilson upper
total-discordance bound of `0.01575391994155881` over 240 pairs. Since this is
incompatible with the frozen +0.10 MRE under the degenerate marginal bounds,
the prescribed scenario envelope is empty. The mechanical mapping therefore
fails closed: no formal N is selected and no simulation is run.

The power-mapping input package is complete as a fail-closed package. Formal
execution remains unauthorized. Historical evidence is unchanged and formal
records remain zero.

## Lifecycle correction and final validation

Issue #206 resolved the stale phase-specific test expectation by retaining an
explicit temporary empty-store guard and adding exact completed-store
reconciliation. It did not invoke the provider or rerun a calibration ID.
Focused validation passed 11 tests in 112.446s; full unittest passed 715 tests
in 710.461s; pytest passed 715 tests in 428.13s; and `git diff --check`
passed.
