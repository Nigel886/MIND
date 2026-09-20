# DR-M18 Power Calibration Execution

## Authorization check

Issue #199 explicitly authorizes real calibration execution for `m18_power_calibration_v1`. The implementation baseline is `9c4a3956765ee2ff13ab5fdaf96beacc7b271714`; `HEAD` and `origin/main` match it. The canonical provider configuration hash was read without exposing credentials: `0f251e14722603e6e39416374467a3598cd72e1d28673e60daf8440dd6115ee2`.

## Immediate preflight

The runner's preflight returned expected 480, valid 0, missing 480, duplicates 0, invalid 0, unexpected 0, and formal records 0. The provider credential was present. No provider operation was invoked.

## Stop reason

The committed `M18PowerCalibrationRunner.execute` requires an injected provider callable which receives only calibration provenance and returns an already-derived terminal/outcome pair. Its plan produces case IDs and seed strings but no executable `M18V3Case` fixtures, and the runner does not construct the frozen shared-provider client or corrected MIND/Direct adapters. Its identity's `provider_config_id` is a label, not the frozen configuration digest. There is therefore no authorized, reproducible path from a planned logical ID to an actual corrected comparator/evaluator episode. Creating one now would be an in-execution patch prohibited by Issue #199.

## Non-actions and state

- Provider calls: 0
- Calibration records created: 0
- Formal records created: 0
- Calibration result-set digest: unavailable; no admitted records
- Nuisance estimates/power mapping: unavailable; no calibration outcomes
- Formal execution: not authorized

No source, test, runtime, comparator, design, provider configuration, or statistical artifact was changed.
