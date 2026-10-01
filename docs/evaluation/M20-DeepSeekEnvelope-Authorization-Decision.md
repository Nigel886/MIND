# M20 DeepSeek Envelope Remediation Authorization Decision

## Verdict

**REAL-PROVIDER CONTRACT DIAGNOSTIC AUTHORIZED**

Following the independent #260 audit, a separate execution issue may rerun
only the already-frozen two-condition real-provider diagnostic.  This decision
does not itself call DeepSeek or create empirical evidence.

## Authorization binding

The live gate requires the unchanged exact artifact
[M20-LiveDiagnostic-Authorization-Artifact.json](M20-LiveDiagnostic-Authorization-Artifact.json),
identity `f3ea49c6b7886b9ce42e81da29246d1e4d226612993ddc328913793f0d1956df`.
It binds `m20_real_provider_diagnostic_v1`, the diagnostic namespace,
`m20.real.multi_step_stateful.01`, payload digest
`b977a2170893e1c1cfc7d7571e275df3f47d95259b29415e2d1bdea1202069be`, and
exactly one MIND-Adaptive plus one MIND-Fixed work item.

The provider remains DeepSeek official API / `deepseek-flash` /
`DeepSeek-V4.1-Flash`, hash
`522fcf28714e168ce9854069468c51d3d3cb565404d7bdad3317e4fcc8f199ad`, with
512 output tokens, 60-second timeout, and two retries after the initial
attempt. Credential presence was verified without network access.

## Audit finding

The #259 change is limited to removal of the standard OpenAI-compatible
top-level transport metadata (`id`, `object`, `created`, optional fingerprint,
and optional service-tier) before the unchanged strict M20 parser.  It does
not transform assistant content, loosen invalid-envelope rejection, or alter
the prompt, schema, action/payload semantics, evaluator, telemetry, or either
condition's policy.  Adaptive and Fixed share the corrected bridge.

Historical evidence remains unchanged: #250 has 120 records / 60 pairs and
#258 has two diagnostic records.  The #260 audit made zero provider calls and
created zero diagnostic, pilot, calibration, or formal records.
