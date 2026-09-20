# DR-M18 Power Calibration Guard Hardening

Issue #197 is a provider-free, narrow hardening pass over the blockers in the final-readiness review.

| #196 gap | Enforcement location | Focused evidence |
| --- | --- | --- |
| Corrected adapter / strict integer was only provenance | `M18PowerCalibrationDispatch` and runner `_validate_dispatches` reject any missing, stale, or non-strict binding | valid MIND/Direct dispatch accepted; stale and permissive bindings rejected |
| Historical ID isolation was audit-only | `historical_calibration_collision_ids` plus strict preflight compares logical IDs from defined historical/formal artifacts | injected collision blocks execution |
| Crash recovery was not runner-verified | `execute` derives each schedule from `store.missing()` and invokes strict empty-state preflight only at initial execution | post-admission interruption leaves 479 IDs missing; resume does not rerun admitted ID |
| Stop safety was not runner-tested | `execute` checks persistent stop before scheduling and persists the existing typed event after repeated structural evidence | stop survives restart; later scheduling halts; timeout does not create stop |
| Diagnostic firewall lacked calibration tests | calibration records contain no provider diagnostic; stop event persists only typed fields | secret-bearing fake diagnostic has zero persisted secret occurrences |
| Formal namespace and stop were report-only | `preflight(require_empty=True)` rejects nonempty formal namespace, collisions, nonempty calibration records, or persistent stop | isolated formal artifact and stop both fail closed |

Focused provider-free tests are `tests/test_m18_power_calibration_runner.py`: PASS (8 tests in 5.263 seconds). `python -B -m unittest`: PASS (712 tests in 149.563 seconds). `pytest -q`: PASS (712 tests in 143.26 seconds; one non-failing pytest cache-permission warning). `git diff --check`: PASS. No real provider was called, no calibration/formal execution occurred, and no canonical calibration evidence was created.
