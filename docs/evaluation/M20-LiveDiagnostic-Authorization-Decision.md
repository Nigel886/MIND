# M20 Live Diagnostic Authorization Decision

## Verdict

**REAL-PROVIDER CONTRACT DIAGNOSTIC AUTHORIZED**

The authorization artifact is [M20-LiveDiagnostic-Authorization-Artifact.json](M20-LiveDiagnostic-Authorization-Artifact.json). Its deterministic identity is `f3ea49c6b7886b9ce42e81da29246d1e4d226612993ddc328913793f0d1956df`.

## Authorized future scope

Only `m20_real_provider_diagnostic_v1` may execute, at `evaluation/results/m20_real_provider_diagnostic_v1`, for `m20.real.multi_step_stateful.01` / `multi_step_stateful` / `b977a2170893e1c1cfc7d7571e275df3f47d95259b29415e2d1bdea1202069be`: exactly one MIND-Adaptive and one MIND-Fixed work item, two total, no repetition or additional case.

## Conditions verified

The live gate is default-deny and rejects absent, mismatched, or altered authorization before transport. It binds the frozen case source (`m20_real_case_source_v1`, digest `4a00cb4128ef747419c601ed6696dd042cba7d4b45d09407e3fb68eb2a42ca12`), provider hash (`522fcf28714e168ce9854069468c51d3d3cb565404d7bdad3317e4fcc8f199ad`), and ceiling (`m20_real_ceiling_v1:6d497729bdb5d5fd87639a690b3d35064f8588e56268770ccbbecf143f5d1423`).

The provider contract remains DeepSeek / `deepseek-flash` / `DeepSeek-V4.1-Flash`, maximum 512 tokens, 60-second timeout, provider-client retry ownership, two retries after the initial attempt, and three physical attempts maximum. **CREDENTIAL READY** was confirmed by presence only.

The future path is the existing live transport gate, production M20 DeepSeek bridge and parser, #252 structural telemetry, and isolated diagnostic persistence. It contains no alternate parser or response interpretation. Raw responses, credentials, evaluator-private values, and hidden reasoning remain excluded. Fake admission/lifecycle tests pass, and #250 remains 120 calibration records / 60 pairs / 120 generic classifications.

## Boundary

This decision made zero provider calls and created zero real diagnostic, pilot, calibration, or formal records. It authorizes only a separate execution issue to perform the two frozen diagnostic work items.
