# M20 Post-Envelope Diagnostic v2 Authorization Decision

## Verdict

**REAL-PROVIDER CONTRACT DIAGNOSTIC V2 BLOCKED**

The v2 protocol has the correct result path but retains the v1 namespace value
in its identity and in the derived authorization payload.  Consequently, the
required v1/v2 persistence-namespace separation is not proven.

No v2 authorization artifact is issued, and no real-provider execution is
authorized.  A focused remediation must bind the v2 namespace identity to
`evaluation/results/m20_real_provider_diagnostic_v2`, with regression coverage
that rejects cross-generation namespace substitution.  It must then receive a
new independent authorization audit.

This audit made zero provider calls and created zero v2 diagnostic, pilot,
calibration, or formal records.  Historical #250 and #258/v1 evidence remains
unchanged.
