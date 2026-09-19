# M18 Prospective Nuisance-Estimation Addendum

## Status, Scope, and Historical Boundary

This is a prospective, provider-free specification for a future calibration condition. It defines the only permissible route by which M18 nuisance quantities may be estimated for the frozen #188/#189 power calculation.

The original v3 pilot, v2 evidence, every frozen suite artifact, the corrected comparator implementation, and the completed 360-run corrected pilot are historical or operational evidence only. They contribute **no** nuisance estimate, confidence bound, scenario input, calibration sample-size choice, or formal-N choice. In particular, the completed corrected pilot cannot be retrospectively converted into this calibration condition because this addendum did not exist before its execution.

Nothing here changes the frozen primary endpoint, MIND-versus-Direct contrast, two-sided alpha .05, target power .90, +.10 minimum relevant effect (MRE), eligibility definition, five-repetition structure, case-cluster analysis unit, failure map, permutation/bootstrap procedure, or multiplicity policy.

## Calibration Population and Fixed Construction

The future calibration condition is `m18_power_calibration_v1`. It is a new, held-out sample satisfying the future formal suite's machine-checkable `primary_eligible` contract for `dependent_stateful_composition`:

- at least two public state transitions;
- a later required action whose validity depends on an earlier public outcome;
- evaluator-owned binary task completion; and
- equivalent public task contract and external budget for MIND and Direct.

Exclude a candidate if it lacks any required proof field; has a non-deterministic fixture or evaluator; has no frozen public action contract; cannot be generated from the declared source template; shares a source-seed namespace, case ID, or fixture identity with any historical or future formal case; or would require an outcome-based selection decision. Comparator performance is never an eligibility criterion.

The calibration manifest must contain exactly **48 case clusters**, allocated as eight cases in each cell of the two prospectively declared source-template families by three prospectively declared difficulty strata. The concrete family and stratum labels, eligibility proofs, source/template/environment/order seeds, and all case IDs are deterministically generated and frozen before any provider call. The 48-cluster size and 8-per-cell allocation are fixed design constants, not values selected from corrected-pilot results; no optional expansion, stopping rule, or outcome-driven rebalancing is allowed.

Each case has five fresh paired repetitions for MIND and Direct only. A matched case × repetition cell uses the same frozen case fixture, evaluator, public contract, budget, and provider model/configuration for both comparators. Each episode uses fresh agent/environment state. Comparator order is deterministically counterbalanced by the manifest's frozen order seed, with no order chosen after observing an outcome. Thus the calibration consists of 48 × 5 × 2 = 480 planned logical runs, and the case cluster remains the estimation/resampling unit.

## Identity, Provenance, and Deterministic Manifest

The calibration suite ID is `m18_power_calibration_v1`; its logical-run schema is `m18_power_calibration_v1_logical_run_id_v1`; its required ID prefix is `m18pcv1-`; and its result-record schema is `m18_power_calibration_v1_result_v1`. Records reside only under `evaluation/m18/results/m18_power_calibration_v1/pilot`.

The manifest must be canonical JSON and include its SHA-256 digest. It must bind the suite ID/version, case ID, source family and difficulty stratum, eligibility proof, source/fixture/environment/order seeds, comparator, repetition index, paired-cell key, public prompt/parser/evaluator identities, provider/model/budget configuration, failure-classification schema, logical ID, and result-schema version. The result provenance must repeat and validate those bindings plus the manifest digest. The runner must reject duplicate logical IDs, IDs outside the `m18pcv1-` domain, a mismatched namespace/schema/manifest digest, or any collision with v1/v2/v3, corrected-pilot, corrected-formal, or future formal identities. The manifest's canonical bytes, ordered ID list, and digest must reproduce the same planned universe on a clean rerun.

## Permitted Nuisance Quantities and Estimators

Let K=48, R=5, and let Y(i,c,r) ∈ {0,1} be the frozen evaluator-owned binary outcome for case i, comparator c, repetition r, after all planned records are admitted. `success` maps to 1; every agent-originated wrong, malformed, incomplete, agent-failure, budget, invalid-action, recoverable-failure, or episode-budget-timeout terminal maps to 0. Verified provider failure, provenance/admission failure, a corrupted task or environment/evaluator implementation error, and a missing expected record are infrastructure-invalid and are not an analysis outcome. They require a same-identity rerun before the store can be complete.

Only the following quantities may be estimated:

1. **Marginal success probabilities.** For comparator c, estimate p-hat(c) as the mean of its five-repetition case means: (1/K) Σ(i) [(1/R) Σ(r) Y(i,c,r)]. Equal case weighting is mandatory.
2. **Paired discordance.** Over the 240 matched case × repetition cells, estimate p-hat(10) as (1/(KR)) Σ(i,r) 1[Y(i,MIND,r)=1 and Y(i,Direct,r)=0], and estimate p-hat(01) analogously with the outcomes reversed.
3. **Repeated-measure and cross-comparator dependence.** Form each case's ordered ten-element binary vector (five MIND then five Direct outcomes). Estimate its equal-case-weighted empirical covariance matrix, including all within-comparator and cross-comparator covariance terms. A correlation is reported only where both marginal sample variances are nonzero; no undefined correlation is imputed.
4. **Operational feasibility.** Report planned/admitted logical-ID completeness, same-identity infrastructure-invalid rerun count, and unresolved-invalid count. These are operational gate quantities, not alternative endpoints.

All uncertainty treatment is case-clustered: the complete ten-element case vectors are resampled together. No repetition is treated as an independent case.

## Frozen Conservative Mapping to Formal Power

After an independently audited, complete calibration store, use a nonparametric case-cluster bootstrap with 10,000 resamples and `random.Random(189000004)` to produce percentile 95% bounds for the two margins, each discordance probability, and every defined covariance component. Canonically order records by case ID, comparator, and repetition before every calculation. The exact bootstrap algorithm, percentile convention (2.5th and 97.5th empirical quantiles using zero-based linear interpolation), and canonical JSON output are frozen by this section.

Construct the nuisance scenario envelope from the Cartesian product of those bounds after rejecting mathematically impossible probability/covariance combinations and retaining only combinations compatible with the frozen +.10 MRE. At a zero or near-zero discordance estimate, do not substitute a point estimate: use the upper 97.5% Wilson-score bound for total discordance together with the directionally least-favorable split between p10 and p01 that remains MRE-compatible. If a covariance or correlation is undefined, include the full Fréchet-feasible covariance range given the applicable marginal bounds. If a bound, covariance matrix, or simulated vector distribution is numerically infeasible, use the feasible boundary that maximizes required formal N; if no feasible construction exists, fail closed.

For each balanced candidate formal N (with equal allocation across the frozen two-family × three-stratum layout), simulate 100,000 complete paired five-repetition case-vector universes for every retained scenario using `random.Random(189000001)`. Apply the already frozen two-sided complete-vector within-case permutation decision rule (100,000 draws, seed `189000002`) to each simulated universe. Estimate power as the success fraction and compute its lower one-sided 95% Wilson-score Monte Carlo bound. Compare unrounded values; a candidate passes only when that bound is at least `0.900000` in every scenario. Select the smallest passing balanced N and record it without rounding other than the required six-stratum allocation. Any numerical comparison is performed in IEEE-754 double precision with a fixed tolerance of `1e-12` only for equality/canonicalization, never to convert a failing bound into a pass.

This is a one-time, mechanical pilot-to-power calculation. Calibration outcomes cannot change a frozen field; they can only determine formal N through the above conservative mapping. If every considered feasible N fails, formal progression stops pending a project-owner-approved, versioned redesign rather than threshold relaxation or historical-data substitution.

## Authorization and Progression

The required order is:

1. Prepare and review a calibration runner that enforces this manifest, provenance, failure boundary, and deterministic identity scheme.
2. Obtain explicit authorization for real calibration execution.
3. Complete the 480-logical-run calibration universe, resolving every infrastructure-invalid record by same-identity rerun.
4. Obtain an independent audit of manifest identity, completeness, provenance, failure handling, and calibration evidence.
5. Perform the frozen mechanical calculation and freeze a pilot-to-power addendum containing the complete inputs, bounds, scenarios, simulations, formal N, and reproducibility digests.
6. Generate a new, held-out formal suite/manifest using the selected N; it must be disjoint from calibration and every historical suite.
7. Obtain independent formal readiness review and explicit formal-execution authorization.

Calibration runner preparation is authorized by this specification. Real calibration execution and formal execution are not authorized.
