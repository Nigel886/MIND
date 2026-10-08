# M20 Independent Issuer Governance Plan

## Purpose and boundary

This plan defines the minimum external governance needed to issue a future
authorization for the frozen M20 feasibility study. It does not designate an
issuer, enroll a key, or authorize execution.

## Required independent roles

- **Design owner:** confirms the frozen scientific scope has not changed.
- **Independent issuer:** a named human or body outside application/Codex
  control, authorized in writing to approve the exact scope.
- **Key custodian:** controls the issuer Ed25519 private key outside this
  repository and production runtime.
- **Trust-anchor administrator:** authenticates and enrolls the issuer public
  key by a documented out-of-band procedure.
- **Revocation/rotation owner:** publishes expiry, revocation, and replacement
  procedures and records affected authorization identifiers.

## Minimum governance evidence

Before authorization, retain human-signed records identifying each role,
approval authority, private-key custody controls, public-key fingerprint and
provenance, enrollment approver, revocation channel, rotation cadence, and
incident response contact. No participant may self-approve, self-enroll, and
control the production verifier without independent review.
