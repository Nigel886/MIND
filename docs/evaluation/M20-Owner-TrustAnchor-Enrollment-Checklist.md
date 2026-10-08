# M20 Owner Trust-Anchor Enrollment Checklist

## Verifier-compatible representation

The external JSON anchor consumed by the verifier must have schema
`m20_feasibility_issuer_trust_anchor_v1` and an `issuers` mapping. For a future
owner issuer ID, the required entry is:

```json
{"schema":"m20_feasibility_issuer_trust_anchor_v1","issuers":{"OWNER_ISSUER_ID":{"algorithm":"Ed25519","public_key_b64":"BASE64_OF_32_RAW_PUBLIC_KEY_BYTES"}}}
```

The issuer ID is owner-chosen, stable, nonempty, and recorded with governance
provenance. The authorization envelope never supplies a public key; only the
separately authenticated anchor is trusted.

## Enrollment checklist

- [ ] Separate explicit owner permission for enrollment exists.
- [ ] Owner identity and issuer ID are recorded.
- [ ] Raw public-key length is verified as 32 bytes after strict Base64 decode.
- [ ] SHA-256 fingerprint is independently compared through an owner-controlled
  out-of-band channel.
- [ ] Anchor path is external to repository and authorization submission.
- [ ] Anchor file ACLs permit verifier read access but prohibit ordinary runner
  modification.
- [ ] Revocation contact, rotation procedure, effective date, and audit record
  are documented.
- [ ] A non-network synthetic envelope signed by an isolated test key is
  verified against an isolated test anchor; it is then discarded.
- [ ] No production authority or provider transport is invoked.

Any failed checklist item blocks enrollment and execution.
