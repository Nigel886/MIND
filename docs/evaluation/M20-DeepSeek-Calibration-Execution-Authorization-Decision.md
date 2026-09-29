# M20 DeepSeek Calibration Execution Authorization Decision

## Decision

**PROVIDER EXECUTION AUTHORIZED**

This is a final pre-execution authorization for a future, separately initiated M20 calibration issue only. It does not itself call DeepSeek, create any empirical record, execute pilot, calibration, formal evaluation, or run statistical testing.

## Identity verification

- Baseline: `2e01969a9d5d5b7eaad8ffa7673b4e7bf688b2b3`.
- Manifest: `m20_calibration_manifest_v2`, digest `ce129d8ee968c4bd6ddb6fa2573934f5da1fa2a8b408845e61c38275427da158`.
- Case source: `m20_real_case_source_v1`, digest `4a00cb4128ef747419c601ed6696dd042cba7d4b45d09407e3fb68eb2a42ca12`; 12 eligible cases, five repetitions per case, 60 paired units, and `m20_pair_counterbalance_v1` ordering.
- Provider: DeepSeek official API; `deepseek-flash`; `DeepSeek-V4.1-Flash`; configuration hash `522fcf28714e168ce9854069468c51d3d3cb565404d7bdad3317e4fcc8f199ad`; credential source `DEEPSEEK_API_KEY`.
- Credential readiness: `CREDENTIAL READY` by non-network presence check. The credential was neither printed, hashed, nor serialized.
- Shared ceiling: `m20_real_ceiling_v1:6d497729bdb5d5fd87639a690b3d35064f8588e56268770ccbbecf143f5d1423`, identically bound to Adaptive and Fixed.

The DeepSeek contract is max output 512, timeout 60 seconds, provider-client retry ownership, and two retries after the initial attempt (three physical attempts maximum). A retry remains part of one logical provider operation and cannot increment the logical-provider-interaction endpoint again.

## Parity, readiness, and scientific contract

Adaptive and Fixed share provider identity/configuration, ceiling, environment, evaluator, public action surface, retry semantics, failure semantics, and replacement rules. Only their frozen deliberation-control strategy differs. Focused non-empirical validation covered native Adaptive binding, Fixed scheduling, paired lifecycle, retry accounting, partial/resume lifecycle, evidence integrity, statistical-input reconstruction, completed-reinvocation idempotence, evaluator ownership, resource reconciliation, and manifest binding.

The scientific contract is unchanged: Adaptive versus Fixed; 5 percentage-point quality non-inferiority margin; logical-provider-interactions endpoint; MRE 0.25; one-sided alpha 0.025; joint power at least 0.90; quality-first/resource-second gatekeeping; frozen comparator semantics; and frozen evaluator semantics.

## Boundary and rationale

At authorization time, provider calls, pilot records, calibration records, and formal records are all `0`; nuisance estimates remain absent. Every required immutable identity, credential-readiness check, parity constraint, non-empirical harness check, and full regression passed. A new execution issue may make the first real DeepSeek calibration provider calls only under this exact v2 manifest and its frozen contract.
