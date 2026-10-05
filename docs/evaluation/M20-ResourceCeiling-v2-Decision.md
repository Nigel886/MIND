# M20 Resource Ceiling v2 Decision

## Prospective amendment

The completed v3 calibration universally exhausted the shared v1 provider and
tool ceilings before an evaluator outcome: 60/60 Adaptive and 60/60 Fixed at
both limits, with no parser, evaluator, infrastructure, persistent provider, or
persistence explanation. `m20_real_ceiling_v1`
(`6d497729bdb5d5fd87639a690b3d35064f8588e56268770ccbbecf143f5d1423`) is
preserved unchanged as **HISTORICAL / INADEQUATE FOR CALIBRATION**.

## Frozen v2 identity

- Version: `m20_real_ceiling_v2`
- Canonical digest: `6b4537f6d7e688f30517307cfd2019d99ad20380f76110f8f5515d400bfa08e0`
- Identity: `m20_real_ceiling_v2:6b4537f6d7e688f30517307cfd2019d99ad20380f76110f8f5515d400bfa08e0`

| Resource | v1 | v2 | Prospective structural rationale |
| --- | ---: | ---: | --- |
| Reasoning steps | 8 | 16 | Fixed uses one reason per admitted cycle plus a recovery replan after each recoverable transition; eight cycles can require eight reasons and up to seven replans. |
| Tool attempts | 4 | 8 | One public action may dispatch per non-answer cycle; eight matches the bounded cycle horizon and removes the observed four-action censoring. |
| Logical provider interactions | 4 | 8 | One logical proposal per admitted decision cycle; eight removes the known four-request boundary while retaining a finite bound. |
| Decision cycles | 8 | 8 | Eight is already the bounded episode horizon; it was not binding in v3 and prevents an immediate replacement bottleneck. |

The real cases have witnesses of at most three actions plus an answer, but
public transitions permit nonterminal progress/distractor behavior. The v2
values therefore make room for bounded recovery/acquisition/distractor paths
without selecting a ceiling for favorable quality or resource separation.

## Parity and fail-closed binding

Adaptive and Fixed bind the same v2 provider, ceiling, environment, evaluator,
and case-source identities. Deterministic validators reject v1, altered values,
wrong digest, and mixed condition bindings. No condition receives an override.

## Scientific and historical preservation

The contrast, quality estimand and 0.05 margin, logical-provider-interaction
endpoint and -0.25 MRE, gatekeeping, alpha, power, and case-cluster bootstrap
are unchanged. #250 and #282 evidence, manifest v2/v3, and diagnostic v1-v5
remain immutable historical evidence. Provider calls, new calibration, pilot,
and formal records are zero under this design freeze.

## Required future progression

A future calibration must use a new protocol, namespace, manifest, pair/work
identities, and current runtime binding tied to v2. It must not reuse
`m20_calibration_manifest_v3` or `m20_calibration_postremediation_v1`, and it
requires fresh independent authorization before any provider execution.
