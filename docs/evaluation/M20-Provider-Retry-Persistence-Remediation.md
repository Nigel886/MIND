# M20 Provider Retry Persistence Remediation

## Decision

The #267 Fixed diagnostic-v3 record is immutable historical evidence and
remains invalid: five persisted physical attempts use five logical-operation
IDs while only four logical provider interactions were charged. The canonical
validator correctly fails closed; it was not loosened.

## Prospective correction

The harness now allocates an immutable `M20ProviderOperation` once per logical
provider interaction. Both Adaptive and Fixed pass that operation to the shared
provider-client retry loop. Each physical attempt derives a unique physical ID
and its actual retry index from the same operation. Provider-client retries
therefore reuse the logical ID, retain ownership, and do not add logical
resource charges.

## Offline validation

Deterministic fakes prove four logical operations / five physical attempts /
one retry and one logical operation / three physical attempts / two retries.
Canonical reload succeeds for both. Corruption cases fail closed for a new or
wrong logical ID, reset/duplicate indices, ordering and initial-attempt errors,
duplicate physical IDs, incorrect resource charges, inconsistent counts, and
invalid ownership.

Focused validation passed 22 tests. Full unittest passed 785 tests in 132.593s
(exit 0); pytest passed 785 tests in 133.12s (exit 0); and `git diff --check`
passed.

No provider call, diagnostic, pilot, calibration, or formal execution occurred.
Historical #250 (120 records / 60 pairs), v1 (2), v2 (0), and v3 (2 original
records) are unchanged. This correction does not authorize real-provider
execution: a fresh prospective diagnostic generation requires independent
authorization.
