# DR-M18 Power Calibration Execution Bridge

## #199 blocker

Issue #199 stopped because calibration provenance had no committed path from a logical ID to an executable corrected-adapter episode and carried only a provider configuration label.

## Implementation

`M18PowerCalibrationPlan.bridge` now resolves all 480 frozen logical identities to `M18PowerCalibrationEpisode` values. Each binding carries the original provenance, a deterministic held-out `M18V3Case`, exact corrected adapter class (`M18V3MINDAdapter` or `M18V3DirectAdapter`), and the frozen shared-provider configuration hash. `resolve` performs the inverse identity check before execution.

`M18PowerCalibrationRunner.preflight` requires the full bridge and a canonical `M18SharedProviderConfiguration` whose hash equals `0f251e14722603e6e39416374467a3598cd72e1d28673e60daf8440dd6115ee2`. `execute` invokes the provider only with the resolved executable episode, so fake lifecycle coverage traverses the same bridge. Identity provenance uses the frozen hash, and the closed record parser/admission path rejects incompatible provenance.

## Provider-free validation

Focused tests resolve 480 expected/480 unique bridge bindings, retain 240 MIND and 240 Direct bindings, round-trip identities, exercise fake full lifecycle through the bridge, and reject an exact-hash mismatch. Existing #197 guards continue to pass. Canonical calibration records and formal records remain zero; no provider call occurred.
