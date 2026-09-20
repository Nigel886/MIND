# DR-M18 Power Calibration Exact Identity Binding Fix

Issue #201 identified stale synthetic provenance labels (`m18_v3_environment_v1` and `m18_v3_evaluator_v1`) that differed from the resolved `M18V3Case` identities. The calibration identity now imports its environment, evaluator, runtime, and budget from the same frozen M18 v3 constants used by the executable episode. `M18PowerCalibrationEpisode` compares all declared identity-bearing fields to the resolved episode and fails closed.

Focused provider-free validation resolves 480 expected/480 executable bindings with 480 exact identity matches and zero mismatches; MIND/Direct remain 240/240. Provider hash and corrected-contract checks remain in the same boundary. Existing fake lifecycle and guard tests pass using temporary storage only. Canonical calibration and formal records remain zero; no provider was called.
