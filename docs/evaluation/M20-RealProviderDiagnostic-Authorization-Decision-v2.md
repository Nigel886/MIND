# M20 Real-Provider Diagnostic Authorization Decision v2

## Decision

**REAL-PROVIDER CONTRACT DIAGNOSTIC BLOCKED**

## Verified contract

The audit baseline is `e163c175cdc389c6ef0caf73febccb6e2f670e0a`. The isolated diagnostic protocol is `m20_real_provider_diagnostic_v1`, with path `evaluation/results/m20_real_provider_diagnostic_v1`. It binds the single selected case `m20.real.multi_step_stateful.01` in cohort `multi_step_stateful`, payload digest `b977a2170893e1c1cfc7d7571e275df3f47d95259b29415e2d1bdea1202069be`, one Adaptive and one Fixed work item, and zero additional repetitions.

The case-source, provider, and resource identities match their frozen values: `m20_real_case_source_v1` / `4a00cb4128ef747419c601ed6696dd042cba7d4b45d09407e3fb68eb2a42ca12`; `522fcf28714e168ce9854069468c51d3d3cb565404d7bdad3317e4fcc8f199ad`; and `m20_real_ceiling_v1:6d497729bdb5d5fd87639a690b3d35064f8588e56268770ccbbecf143f5d1423`. The provider attempt contract remains `deepseek-flash`, 512 output tokens, 60 seconds, provider-client ownership, two retries after initial request, and three maximum physical attempts. **CREDENTIAL READY** was confirmed without reading or recording the credential.

Fake validation proves the isolated store, production #252 response parser/telemetry binding, retry-attempt reconstruction, lifecycle/idempotence behavior, and secret/private-data exclusion. It also proves the namespace remains distinct from pilot, calibration, and formal. #250 remains 120 calibration records / 60 pairs / 120 generic classifications, unchanged.

## Blocker

The only diagnostic entry point is `run_fake`, which rejects any non-`M20FakeDiagnosticTransport` input before execution. This is a correct fail-closed safety control but leaves no executable live-provider runner for the two frozen diagnostic work items. The audit cannot authorize an execution path that does not exist.

A dedicated implementation issue must add a narrowly gated live runner while retaining the immutable protocol, work enumeration, diagnostic namespace, telemetry, retry semantics, and fail-closed lifecycle. It must then receive a new independent authorization audit.

## Boundary

This audit made zero provider calls and added zero diagnostic, pilot, calibration, or formal records.
