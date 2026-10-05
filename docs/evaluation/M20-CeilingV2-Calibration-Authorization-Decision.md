# M20 Ceiling-v2 Calibration Authorization Decision

## Decision

**DESIGN / MANIFEST: PASS**

**EXECUTION AUTHORIZATION: BLOCKED**

## Verified design

The frozen `m20_calibration_manifest_v4` generation is deterministic and
complete: `m20_calibration_ceilingv2_v1` binds the v2 ceiling, current runtime,
provider, case source, ordering, scientific contract, 12 cases, five
repetitions, 60 pairs, and 120 work identities. Counterbalancing is exactly 30
Adaptive-first and 30 Fixed-first. Historical v1/v3 identities reject and
historical empirical evidence remains separate.

## Authorization blocker

No manifest-v4 / ceiling-v2 calibration execution bridge exists. The only
available runner is limited to manifest v3, rejects v4 before transport, and
constructs the historical v1 `8/4/4/8` resource semantics. No exact v4
authorization verifier exists.

As a result, the required v4 fake-transport checks for lifecycle resume,
idempotence, retry/resource accounting, request projection, evaluator
isolation, and live-boundary admission cannot be performed. Execution is
therefore not authorized.

## Boundary and next step

No provider call, v4 calibration record, pilot, or formal record was created.
No authorization JSON artifact exists. #286 is complete as a blocked
independent audit; its blocker transfers to a separate implementation Issue to
create the exact manifest-v4 / ceiling-v2 execution path. That implementation
requires a fresh independent authorization audit before any execution.
