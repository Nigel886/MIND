# M20 Diagnostic v4 Authorization Decision

**REAL-PROVIDER CONTRACT DIAGNOSTIC V4 AUTHORIZED**

The deterministic live-gate artifact is
[M20-DiagnosticV4-Authorization-Artifact.json](M20-DiagnosticV4-Authorization-Artifact.json),
with identity `4138ac6e4f90737186c546df74236c10851ffc6be914ecb3a57a7ea5a42aa73c`.
It binds only v4 protocol digest
`b714470f7fd8ca25287bddb341346985a6728f395945b0eda85ad5ab54c4dca1`,
namespace, provider hash, resource ceiling, telemetry schema, and the two v4
work IDs. The protocol digest itself canonically binds the selected case,
payload, conditions, and result path. No active v1/v2/v3 execution identity
appears in the artifact.

The audit independently confirmed exact two-work-item scope, cross-generation
fail-closed admission and authorization behavior, the unchanged public prompt,
parser/schema/action semantics, #259 metadata-only envelope normalization,
#252 telemetry, and #269 shared retry persistence. The provider is
`deepseek-flash`, with output ceiling 512, timeout 60 seconds, provider-client
retry ownership, and at most two retries (three physical attempts).

Credential readiness is confirmed non-network. This decision authorizes only a
separate execution issue to invoke exactly the two v4 work IDs. It does not
authorize calibration, pilot, formal evaluation, any extra work item, or any
historical generation.

Focused independent non-network validation passed 38 tests; `git diff --check`
passed. No production code was modified by this audit.
