# M18 Operational Tranche Execution

## Scope

This operational record covers only the authorized M18 diagnostic pilot tranche
`m18_pilot_operational_tranche_v1`:

```text
12 pilot cases × 4 systems × 5 repetitions = 240 identities
```

It does not authorize or report the remaining full-pilot identities, formal
evaluation, statistical comparison, or architecture-superiority claims.

## Frozen Baseline

- Execution baseline: `fbf98fa54c26c9cd8ab3c9cbfa3d550f92e5abac`
- Suite: `m18_suite_v1`
- Tranche manifest hash: `38ca8d5ea1c231e3dfceea0d192709533e16a6e363426d429955df9979a899f1`
- Provider configuration hash:
  `0f251e14722603e6e39416374467a3598cd72e1d28673e60daf8440dd6115ee2`
- Canonical result namespace:
  `evaluation/m18/results/pilot/m18_pilot_v1/`

The frozen run used the shared DeepSeek condition with requested model
`deepseek-flash`, disabled thinking and streaming, temperature `0`, `top_p` of
`1`, a 512-token output cap, and the frozen three-attempt transport ceiling.

## Operational Completion

- Record write interval observed from the canonical atomic result files:
  2026-09-15T23:55:25.7734269+08:00 to
  2026-09-15T23:59:36.2196642+08:00.
- Expected identities: 240.
- Provenance-valid completed identities: 240.
- Missing identities: 0.
- Duplicate identities: 0.
- Extra/non-tranche identities: 0.
- Formal-case identities: 0.
- Operational integrity stop: none.

Every completed record has the frozen provider configuration hash, harness
identity `2350bfdc34132a099a49df6ff065244e1d442d81f2be85d8c2e7bb6f5adb3b39`,
pilot namespace, and tranche ID. Returned-model observations were
`deepseek-flash` whenever a provider response was available; no conflicting
returned model was recorded. Provider-failure records have no returned-model
telemetry by design.

## Operational Telemetry

- Logical provider calls: 409.
- Transport attempts: 409.
- Records with provider token telemetry: 180.
- Token totals: 195,873 prompt; 7,435 completion; 203,308 total; 67,328 cached.
- Records with latency telemetry: 180.
- Aggregate latency: 240,293 ms; observed range: 412–2,817 ms.

Neutral failure-category counts are retained as operational record metadata:

| Category | Count |
| --- | ---: |
| `budget_exhausted` | 38 |
| `invalid_action_exhausted` | 24 |
| `provider_failure` | 60 |
| `wrong_answer` | 118 |

## Integrity Boundary

The result store validated run membership, run ID, suite/provider/harness and
system identities, repetition, pilot namespace, and tranche provenance before
completion. No stop-event artifact is present. The raw records are retained in
the canonical operational namespace and are not included in this documentation
commit.

This document is an execution/provenance record only. It does not compare the
four systems, infer statistical significance, claim agent superiority, or
modify the frozen experiment.
