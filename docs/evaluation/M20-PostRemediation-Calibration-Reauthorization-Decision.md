# M20 Post-Remediation Calibration Reauthorization Decision

## Decision

**POST-REMEDIATION CALIBRATION EXECUTION AUTHORIZED.**

The independently regenerated `m20_calibration_manifest_v3` identity and the
v3 fail-closed execution gate satisfy the authorization contract.  The live
artifact in `M20-PostRemediation-Calibration-LiveAuthorization.json` is the
exact canonical payload accepted by the v3 runner.  It binds the frozen
protocol, namespace/path, version and complete manifest digest, runtime and
ordering identities, exact 60 pair IDs and 120 work IDs, case source, provider,
ceiling, and statistical protocol.

## Findings

- Frozen generation: `m20_calibration_postremediation_v1`, complete digest
  `0d1faac7d3543041c4873e5dab5f6acbdd198206b663b88853d898e34ad3e91b`.
- Membership regenerated exactly: 12 cases, five repetitions, 60 pairs, 120
  work IDs (60 Adaptive / 60 Fixed), and 30/30 counterbalancing.
- The v3 runner rejects v2 and any altered/partial/expanded authorization
  binding before transport.  With the exact synthetic artifact and fake
  transport, the full 120-work lifecycle completed canonically; replay made
  zero further fake calls.
- Canonical persistence, partial resume, corruption fail-close, retry/resource
  accounting, replacement limits, terminal-pair reconstruction, envelope
  normalization, telemetry, and evaluator-owned outcome remain on the native
  shared harness path.
- Credential readiness is **CREDENTIAL READY**, checked non-network without
  exposing credential material.

## Boundaries

No DeepSeek call occurred during this audit.  Real v3 calibration, pilot, and
formal records are zero.  #250 remains immutable historical v2 evidence at
120 records / 60 pairs; diagnostic v1-v5 remains excluded.

This authorization is limited to a separate execution issue running exactly
the frozen 60-pair / 120-condition v3 calibration through the artifact-bound
runner.  It does not authorize formal evaluation.
