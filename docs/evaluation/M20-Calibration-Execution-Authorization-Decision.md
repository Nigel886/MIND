# M20 Calibration Execution Authorization Decision

## Decision

**PROVIDER EXECUTION BLOCKED.**

Baseline: `8dd781053b1faf4068aaac2dea9eb62be1394848`. Manifest `m20_calibration_manifest_v1` is valid at `31ce468ca217e7ea8ddc813c5740def250baa99f31871102b786f6bcbb2a71d8`; case source, provider hash, ceiling identity, ordering, parity, retry/replacement contract, and readiness checks pass.

Credential readiness is **CREDENTIAL NOT READY**: no required OpenAI API credential mechanism is available in the future execution environment. No secret was read, printed, or committed, and no API request was made. Because this predicate is mandatory, provider execution cannot be partially authorized.

Provider calls, pilot, calibration, formal, and nuisance estimates remain `0/0/0/0/NONE`. The frozen contrast, 5 pp margin, logical-provider endpoint, 0.25 MRE, alpha, power, gatekeeping, evaluator, and comparator contracts are unchanged.
