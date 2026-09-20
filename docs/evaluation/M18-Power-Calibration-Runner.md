# M18 Power-Calibration Runner

The prepared condition is `m18_power_calibration_v1`, as frozen in the prospective nuisance-estimation addendum. It creates a deterministic held-out universe of 48 clusters: eight cases in each of two source-template families and three difficulty strata. Each cluster has five paired MIND/Direct repetitions, for 480 unique `m18pcv1-` logical IDs (240 per comparator).

Records are admitted only beneath `evaluation/m18/results/m18_power_calibration_v1/pilot`, bind the design/version, manifest digest, condition, cluster, comparator, repetition, evaluator/runtime/environment/budget/action-contract identities, and provider configuration. Atomic create, re-read admission, tamper detection, missing-only scheduling, and typed systematic-provider-stop persistence are enforced. The runner admits only the corrected comparator contract (`m18_v3_comparator_contract_v2`) for MIND and Direct.

The CLI is preflight-only. It has no execution option and accepts only the calibration condition. Real calibration execution requires a separately authorized caller to inject a provider through the API; formal execution has no code path. The runner does not calculate power or modify alpha, target power, MRE, endpoint, eligibility, failure mapping, or multiplicity policy.

Provider-free lifecycle validation must use a temporary result root. Production calibration evidence remains zero before explicit authorization.

## Execution guards

Before an execution call, the runner requires explicit MIND and Direct dispatch bindings carrying the corrected comparator-contract ID and a strict-integer answer contract. It rejects stale or permissive bindings. It also performs deterministic logical-ID collision comparison against defined historical and formal identity artifacts; it never reads outcomes for this check.

Initial execution fails closed unless the canonical calibration namespace is empty, the formal namespace is empty, no persistent systematic stop exists, and the 480-ID preflight is complete. Resume schedules only IDs absent from the admitted canonical store, which preserves the before/after durable-admission crash boundary. Typed provider diagnostics remain outside result artifacts; only the existing typed systematic-stop event may persist.

## Executable bridge and provider provenance

Every logical ID resolves deterministically to one `M18V3Case`, its corrected MIND or Direct adapter class, and the frozen shared-provider configuration hash `0f251e14722603e6e39416374467a3598cd72e1d28673e60daf8440dd6115ee2`. The bridge is one-to-one over all 480 IDs and exposes a round-trip identity projection. Initial execution validates all bridge bindings and rejects any effective configuration whose canonical hash differs before scheduling a provider call. Result provenance repeats that hash through `provider_config_id`; admission rejects a missing or mismatched value.

The bridge takes environment, evaluator, runtime, and budget identifiers from the executable M18 v3 constants (`m18_environment_v3`, `m18_evaluator_v3`, `m18_shared_execution_runtime_v3`, and `m18_budget_v3`). Episode construction compares declared provenance to the resolved executable identity and fails closed on any mismatch.
