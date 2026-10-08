# M20 Prospective Issuer Trust Contract

Algorithm: Ed25519 via `cryptography>=46,<47`. The verifier accepts only a
versioned signed envelope whose canonical payload exactly binds protocol,
manifest and membership digests, Fixed-only work set, provider, runtime,
ceiling, diagnostic, namespace, feasibility purpose, and replacement scope.

Trust anchors are external files with schema
`m20_feasibility_issuer_trust_anchor_v1`, mapping pre-enrolled issuer IDs to
Ed25519 public keys. The payload supplies no public key and cannot enroll one.
Production retains no signing private key. Future real-world approval requires
independent issuer provisioning and a separate authorization audit.
