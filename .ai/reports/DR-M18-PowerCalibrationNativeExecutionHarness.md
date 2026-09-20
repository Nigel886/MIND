# DR-M18 Power Calibration Native Execution Harness

Issue #199 found an arbitrary `provider(episode)` callback could manufacture results. The recovered #204 implementation replaces it with a sealed `provider_client: M18SharedProviderClient` boundary. `M18PowerCalibrationRunner._native_result` owns corrected MIND/Direct wrapper selection, adapter creation, `M18V3SharedExecutionHarness`, evaluator result derivation, and admission persistence.

The shared client remains the sole external transport surface and must match the frozen provider hash. It receives public provider requests and returns transport responses only; it cannot choose evaluator outcomes or result records. Temporary fake-client lifecycle tests traverse the native path. Canonical calibration/formal records remain zero and no real provider call occurred.

## Validation completion

Recovered workspace state was preserved without restarting implementation. Focused native-harness validation passed: exit code 0, 9 tests in 46.145 seconds, including the temporary 480-record lifecycle. Full unittest passed: exit code 0, 713 tests in 182.580 seconds. Full pytest passed: exit code 0, 713 tests in 169.57 seconds, with one non-failing cache-permission warning. `git diff --check` passed. Real calibration records and formal records remain zero.
