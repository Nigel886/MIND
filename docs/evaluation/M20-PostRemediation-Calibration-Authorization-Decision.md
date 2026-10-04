# M20 Post-Remediation Calibration Authorization Decision

## Verdict

**POST-REMEDIATION CALIBRATION EXECUTION BLOCKED.**

The frozen v3 generation is valid and reproducible, but there is no
manifest-v3-bound calibration execution bridge or authorization gate.  The
only existing `M20DeepSeekCalibrationRunner` validates
`m20_calibration_manifest_v2` and rejects the v3 manifest before any supplied
fake transport can be reached.  Consequently, this audit cannot demonstrate
that a valid v3 authorization admits only its 120 work IDs, nor that stale
identities are rejected at a v3 live-calibration gate.  A deterministic
authorization artifact is deliberately not created: no current production
gate consumes or validates one, so it would be inert and could not provide
authorization.

## Verified frozen design

- Protocol / namespace: `m20_calibration_postremediation_v1`
- Result path: `evaluation/results/m20_calibration_postremediation_v1`
- Version: `m20_calibration_manifest_v3`
- Complete digest: `0d1faac7d3543041c4873e5dab5f6acbdd198206b663b88853d898e34ad3e91b`
- Pair/work binding digest: `75a0756826aba183f31acf45799988265cf358f6fe3f42b799c9047759f5b2a5`
- Runtime identity: `2f24111f2dfacd5f875cf9b7a1eb534ef7642948a16d32d512c9e3034ac003bb`
- Ordering: `m20_pair_counterbalance_v2` /
  `03ba5c6d3bcffd194a562060883197371247623a241da1d651e842592d88ba31`

Independent regeneration matched exactly.  The source is
`m20_real_case_source_v1` with digest
`4a00cb4128ef747419c601ed6696dd042cba7d4b45d09407e3fb68eb2a42ca12`:
12 eligible cases, five repetitions each, 60 unique pairs, 120 unique work
IDs (60 per condition), and deterministic 30/30 counterbalancing.

The frozen scientific contract remains Adaptive vs Fixed; quality NI margin
0.05; logical-provider-interactions endpoint; MRE -0.25; quality then
resource gatekeeping; paired case-cluster bootstrap; one-sided 0.025 per gate;
and joint power target at least 0.90.  Runtime identity binds the #259 envelope
normalization, #269 retry persistence, #273 pre-transport resource admission,
#252 structural telemetry, canonical evidence validation, harness, and public
proposal contract.  The provider hash is
`522fcf28714e168ce9854069468c51d3d3cb565404d7bdad3317e4fcc8f199ad`
for `deepseek-flash` / `DeepSeek-V4.1-Flash`, 512 output tokens, 60 seconds,
and two retries after initial; the shared ceiling is
`m20_real_ceiling_v1:6d497729bdb5d5fd87639a690b3d35064f8588e56268770ccbbecf143f5d1423`.

## Preserved boundaries

The v3 namespace is absent and contains zero real records.  The credential was
checked present without network access or exposure.  No provider call, pilot,
new calibration, or formal execution occurred in this audit.  #250 remains
immutable historical evidence (120 records / 60 pairs under
`m20_calibration_manifest_v2`) and is not executable.  Diagnostic v1-v5
records remain diagnostic-only and cannot satisfy v3 calibration identities.

## Required follow-up

A separate implementation issue must add a native v3 calibration runner and a
fail-closed authorization-gate contract which consumes a deterministic artifact
bound to the protocol, namespace, complete manifest, runtime and ordering
identities, all 60 pair IDs and 120 work IDs, source digest, provider hash,
ceiling, and statistical protocol.  It must prove with fake transport that
only exact v3 work IDs reach transport and that old calibration/diagnostic IDs
and altered identities are rejected before transport.  That implementation
requires a fresh independent authorization audit before any real execution.
