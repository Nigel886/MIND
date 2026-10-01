# M20 DeepSeek Real-Provider Diagnostic Authorization Decision

## Verdict

**REAL-PROVIDER CONTRACT DIAGNOSTIC BLOCKED**

No DeepSeek request is authorized by this decision.

## Verified prerequisites

- Baseline: `9bf92f3aaf44228448961bf429afb52b66e708fb` (`HEAD == origin/main`).
- Manifest: `m20_calibration_manifest_v2`, digest `ce129d8ee968c4bd6ddb6fa2573934f5da1fa2a8b408845e61c38275427da158`.
- Case source: `m20_real_case_source_v1`, digest `4a00cb4128ef747419c601ed6696dd042cba7d4b45d09407e3fb68eb2a42ca12`.
- Provider hash: `522fcf28714e168ce9854069468c51d3d3cb565404d7bdad3317e4fcc8f199ad`.
- Resource ceiling: `m20_real_ceiling_v1:6d497729bdb5d5fd87639a690b3d35064f8588e56268770ccbbecf143f5d1423`.
- Credential readiness: **CREDENTIAL READY** (presence only; no secret was exposed).

The production DeepSeek bridge retains #252 structural response telemetry at the actual parser boundary and excludes raw response content, credentials, evaluator-private data, and hidden reasoning. The frozen request contract remains DeepSeek official API / `deepseek-flash` / `DeepSeek-V4.1-Flash`, 512 tokens, 60 seconds, provider-client retries, two retries after initial request, and three maximum physical attempts per logical operation.

## Deterministic candidate and proposed scope

The first eligible source-order case is `m20.real.multi_step_stateful.01` in cohort `multi_step_stateful`, payload digest `b977a2170893e1c1cfc7d7571e275df3f47d95259b29415e2d1bdea1202069be`. No #250 result informed this selection.

The requested future diagnostic scope is one Adaptive condition execution plus one Fixed condition execution: two total, no repetitions, and no calibration-member consumption. This remains unapproved.

## Blocker

The repository has no dedicated M20 diagnostic evidence namespace/path. `M20Namespace` provides fake, pilot, calibration, and formal only, while the M20 DeepSeek runner binds its work items to calibration. Consequently, a two-condition provider diagnostic cannot currently be proven isolated from calibration, pilot, or formal evidence.

A separate implementation issue must create and validate a manifest-bound, append-only M20 diagnostic namespace/path with explicit exclusion from pilot, calibration, and formal counters. Reauthorization can follow that delivery.

## Preservation and boundary

#250 remains unchanged at 120 calibration records / 60 pairs / 120 generic `malformed_or_illegal_m20_proposal` reasons, with no taxonomy backfill. This review created no provider calls and no diagnostic, pilot, calibration, or formal records.
