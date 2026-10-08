# M20 Prospective Independent Issuer Verification

`cryptography` 46.0.7 supplies Ed25519 verification. The versioned envelope
contains a canonical JSON payload, issuer, `Ed25519` algorithm label, and
base64 signature. The external trust-anchor file maps issuer identity to a
preconfigured public key; the envelope cannot declare or enroll a key.

`run_live` and replacement admission verify trust, signature, and the complete
frozen scope before adapter construction. Test-only ephemeral keys and isolated
anchors exercise positive fake transport and forgery rejection. No production
private key, issuer enrollment, or usable authorization artifact exists.

Focused: 7 passed in 0.443s, exit 0. Unittest: 847 tests in 109.378s, exit 0.
Pytest: 847 passed, 1 cache warning in 112.55s, exit 0. Diff check: PASS.
