# M20 Diagnostic v5 Authorization Decision

**REAL-PROVIDER CONTRACT DIAGNOSTIC V5 AUTHORIZED**

The deterministic live-gate artifact is
[M20-DiagnosticV5-Authorization-Artifact.json](M20-DiagnosticV5-Authorization-Artifact.json),
with identity `1121c200e57e48f9e1863a2346ed078e8a34d4c43e5f924a2a825a4373e53281`.
It binds only diagnostic v5: protocol and namespace
`m20_real_provider_diagnostic_v5`, digest
`34b3ac97415a30df900956f8065acbd7061ab2682ce18b7b6373abf6dc367aa4`, the
frozen provider and resource-ceiling identities, telemetry schema, and exactly
the Adaptive and Fixed v5 work IDs. The protocol digest binds the single case,
payload, repetition, and result path. No active historical execution identity
appears in the artifact.

The independent offline audit verified cross-generation rejection, the shared
DeepSeek envelope-to-parser telemetry path, provider-client retry persistence,
and pre-transport resource admission for both conditions. A four-operation
exact-budget fake run stops its requested fifth operation before creating a
logical operation, physical attempt, transport call, or logical charge. One-
and two-retry fake runs retain one logical ID and charge while recording physical
attempt indices `0,1` and `0,1,2` respectively; canonical reload passes.

The provider attempt contract remains `deepseek-flash`, 512 output tokens,
60-second timeout, provider-client retry ownership, and two retries after the
initial attempt (three physical attempts maximum). Credential readiness was
checked non-network without reading, serializing, hashing, or logging the
credential material.

This authorizes only a separate execution issue to invoke exactly the two
frozen v5 work IDs. It does not authorize calibration, pilot, formal evaluation,
additional cases, repetitions, historical generations, or any other work item.
No provider request or empirical record was created by this audit.

## Validation

- Independent offline authorization fixture: 15 checks passed.
- Focused provider-free regression: 40 tests in 0.717s, exit 0.
- `git diff --check`: passed.
