# M20 Resource Admission / Persistence Remediation

The #272 Fixed v4 record remains invalid historical diagnostic evidence: a
fifth physical provider operation was persisted after the four-interaction
budget was exhausted, but it was not charged. Canonical reload correctly fails
with `M20IntegrityError: retry/resource accounting mismatch`.

The proven Fixed lifecycle order was transport before provider-resource charge.
The prospective correction adds a shared hard-budget admission gate before any
condition can create an executable provider operation. Fixed now reserves its
single logical interaction before its first physical attempt. An exhausted
budget produces typed `incomplete` with no operation, transport, physical
attempt, or charge. This is not a v4 or condition/work-ID exception.

Offline fixtures cover exact four-operation budget exhaustion, a zero-remaining
next cycle, and preserved provider-client retry identity. Parser, prompt,
schema, envelope normalization, telemetry, provider configuration, resource
ceiling, M19 policy, and Fixed schedule semantics are unchanged. Historical
evidence remains immutable. No real provider execution is authorized by this
remediation; a new prospective diagnostic generation and authorization are
required.

Focused validation passed 39 tests. Full unittest passed 789 tests in 430.204s
(exit 0); pytest passed 789 tests in 423.56s (exit 0); and `git diff --check`
passed.
