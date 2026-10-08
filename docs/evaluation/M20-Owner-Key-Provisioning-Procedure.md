# M20 Owner Ed25519 Key Provisioning Procedure

## Status and scope

This is a Windows-compatible owner-operated procedure only. It does not grant
permission to generate a key, enroll a trust anchor, sign authorization, or run
an experiment. A separate explicit owner instruction is required at every one
of those boundaries.

## Required key format and custody

Use `cryptography` Ed25519 primitives. Generate a 32-byte Ed25519 private key
only in an owner-controlled, encrypted location outside the repository,
workspace, result namespaces, normal runner account, and cloud-sync folders.
Store the private key in an encrypted password-protected container supported by
the organization/owner; never store raw private bytes, passphrases, or recovery
material in source, environment files, logs, or command history.

The owner alone controls access. Configure restrictive NTFS ACLs, keep an
offline encrypted backup in separately controlled storage, and record only
nonsecret custody metadata. On suspected exposure, stop authorization use,
revoke the anchor, generate a replacement only after new owner approval, and
retain an incident record.

## Future owner-operated procedure

1. Obtain a new explicit owner authorization for key generation.
2. Use Python 3.12 with `cryptography>=46,<47`; generate an Ed25519 key in a
   transient owner-only process.
3. Encrypt and persist the private key outside this repository; securely clear
   transient plaintext according to owner security policy.
4. Export only the 32-byte raw public key and Base64 encode it.
5. Compute a SHA-256 fingerprint over the raw public-key bytes in a separate
   offline verification session; compare it through an out-of-band owner
   channel before enrollment.
6. Do not invoke MIND execution, write authorization JSON, or copy the private
   key to a runner.
