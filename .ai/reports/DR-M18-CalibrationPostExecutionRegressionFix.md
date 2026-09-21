# DR-M18 Calibration Post-Execution Regression Fix

## Stale assertion

The exact failed assertion was in
`tests/test_m18_power_calibration_runner.py`,
`M18PowerCalibrationRunnerTests.test_preflight_and_fake_full_lifecycle_are_temporary`,
line 61. It required the production calibration pilot directory to have zero
JSON records after a temporary fake lifecycle. That was a pre-execution
readiness invariant; after the authorized Issue #199 execution it correctly
conflicted with the completed 480-record production store.

## Lifecycle-aware correction

The temporary lifecycle test now validates only its temporary store. A new
empty-store test requires `480/0/480/0/0/0` before execution and confirms
that a nonempty temporary store fails `require_empty=True`. A separate
production completed-state test requires exact `480/480/0/0/0/0`, 240 MIND,
240 Direct, 48 clusters, 240 complete pairs, formal records 0, and digest
`872edfe1d9032cd5e92270cd6893f2fa6d88243050395919f6a50be91f2dd558`.

## Validation and boundaries

Focused lifecycle tests: 11 passed in 112.446s. Full unittest: 715 passed in
710.461s. Pytest: 715 passed in 428.13s. `git diff --check` passed.

Canonical evidence remains 480 valid records with the same digest and zero
formal records. No provider call or benchmark rerun occurred. Nuisance values
remain MIND/Direct `1.0/1.0`, `p10=0.0`, `p01=0.0`, and Wilson upper total
discordance `0.01575391994155881`; the power mapping remains fail-closed with
no MRE-compatible scenario and no formal N. Formal execution remains
unauthorized.
