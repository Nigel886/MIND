# DR-M20 Calibration Manifest Freeze

Prerequisites are bound exactly: case source `m20_real_case_source_v1` / `4a00cb4128ef747419c601ed6696dd042cba7d4b45d09407e3fb68eb2a42ca12`; provider hash `910b2b5bf28308d6491af4010e3cc108a38e6dbb49613e27bbc9e4493d41c8f1`; and shared ceiling `m20_real_ceiling_v1:6d497729bdb5d5fd87639a690b3d35064f8588e56268770ccbbecf143f5d1423`.

`m20_calibration_manifest_v1` binds all 12 eligible cases, their payload/cohort/cluster identities, five frozen repetitions each, and 60 deterministic Adaptive/Fixed pairs. Pair-level condition ordering uses deterministic `m20_pair_counterbalance_v1`; the manifest digest is `31ce468ca217e7ea8ddc813c5740def250baa99f31871102b786f6bcbb2a71d8`.

Validation deterministically reconstructs the complete manifest and fails closed on missing/extra cases, payload, provider, ceiling, condition, environment, metric, protocol, or ordering mismatch. Reload equality is validated. Suite/environment/evaluator remain `m20_suite_v1`/`m20_environment_v1`/`m20_evaluator_v1`; metric/protocol remain `m20_resource_metrics_v1`/`m20_statistical_protocol_v1`; retry/replacement identities are bound.

Scientific contrast, 5 pp margin, logical-provider endpoint, 0.25 MRE, alpha, power, gatekeeping, evaluator, and comparator contracts are unchanged. Provider calls, pilot, calibration, formal, and nuisance estimates remain `0/0/0/0/NONE`. Manifest freeze does not authorize provider execution.

## Focused validation

- `python -m unittest tests.test_m20_calibration_manifest tests.test_m20_real_execution_configuration tests.test_m20_real_case_source`: `9 passed in 0.037s`.
- `python -m unittest`: exit `0`; `Ran 767 tests in 130.776s`; `OK`.
- `pytest`: exit `0`; `767 passed in 308.55s (0:05:08)`.
- `git diff --check`: PASS.
