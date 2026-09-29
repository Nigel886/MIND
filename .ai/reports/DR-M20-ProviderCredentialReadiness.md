# DR-M20 Provider Credential Readiness

The future OpenAI API provider client resolves `OPENAI_API_KEY` from the inherited calibration-process environment. The readiness check is local and non-network: absent or whitespace-only values return `CREDENTIAL NOT READY`; a non-empty value returns `CREDENTIAL READY`. It does not serialize, log, print, hash, persist, or include the credential in exceptions.

The actual execution environment reports **CREDENTIAL NOT READY**. No credential value was read or emitted. The resolver is compatible with the future process because it reads that process's own environment, not an unrelated shell or configuration file.

Manifest digest `31ce468ca217e7ea8ddc813c5740def250baa99f31871102b786f6bcbb2a71d8`, case-source digest, provider hash, ceiling identity, and ordering identity are unchanged. Provider calls, pilot, calibration, and formal remain `0/0/0/0`.

Focused tests: `6 passed in 0.035s`. Provider execution remains unauthorized.

Full unittest: exit `0`; `Ran 768 tests in 436.518s`; `OK`. Pytest: exit `0`; `768 passed in 145.06s`. `git diff --check`: PASS.
