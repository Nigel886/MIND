# M16 DeepSeek Invalidated Execution Provenance

## Status

**INVALIDATED FORMAL EXECUTION — UNRESOLVED CONCURRENT PROVIDER-CALL PROVENANCE**

## Artifact

The immutable, non-resumable artifact is located at:

`evaluation/results/m16_deepseek_v4_flash/`

It contains a 236/960 terminal prefix produced before the concurrency incident was adjudicated. Its records remain auditable but must not be copied, resumed, or included in any replacement experiment denominator.

## Identity

- Provider config hash: `c074c0e08e6b7be9a93b955a5c5f85da52bb7e9cf83601477ab2e18dad4bc780`
- Invalidated manifest hash: `cbdc24689b60f294c6826282b86930ecfb93bd8a1ed5af25cb0d978c8209ca95`
- Invalidation verdict: `INSUFFICIENT EVIDENCE — DO NOT RESUME`

## Replacement Boundary

Any replacement must use a separately frozen execution-attempt identity, manifest hash, run-ID namespace, result directory, and lifecycle ownership guard. It must begin at 0/960 and cannot treat this artifact as completion state.
