# M20 Independent Issuer Approval Package

## Frozen authorization request

- Protocol: `m20_task_evaluator_feasibility_v1`
- Manifest: `m20_feasibility_manifest_v1`
- Manifest digest: `61847990519fe37cd578fb295494b586dd6bb22fd64103c7839b1b7c7983cd33`
- Membership digest: `7699951ba6bf967bf4fad4a9cbf16306aa9c5af2219b42746874757ac47f95da`
- Scope: 12 cases × 2 repetitions = 24 original `m20_mind_fixed_v1` works.
- Ceiling: `m20_real_ceiling_v2`; diagnostic:
  `m20_evaluator_failure_diagnostic_v1`.
- Boundary: descriptive feasibility evidence only; no Adaptive work, formal
  inference, protocol amendment, or unlisted replacement.

## Human approval checklist

1. Name the independent issuer and written approval authority.
2. Name the private-key custodian and confirm the private key is external to
   repository and production runtime.
3. Provide authenticated public-key fingerprint and trust-anchor enrollment
   evidence, independently of the requested envelope.
4. Confirm revocation/rotation contacts and approval expiry.
5. Review exact signed payload and record approval provenance.
6. Issue an external signed envelope only after all above items are complete.

All items are currently pending; this document is not an approval.
