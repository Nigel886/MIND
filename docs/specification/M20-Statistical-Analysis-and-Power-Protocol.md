# M20 Statistical Analysis and Power Protocol

## 1. Purpose

**STATISTICAL SPECIFICATION ONLY** — This document freezes prospective M20 analysis, power, and progression rules. It creates no provider call, pilot, calibration, formal execution, empirical calculation, or statistical result. It is normative with M20 Issues #217–#220.

Historical M18 material supplies only design lessons: preserve matched identities, respect clustering, bind provenance, and fail closed when no valid formal N exists. It supplies no M20 empirical estimate.

## 2. Statistical Units and Pairing

An execution is one condition-specific episode. A repetition is a matched condition opportunity within one task case. A task case is the inferential cluster; cohorts stratify cases and never create independent observations. The primary pair is the two records with the same suite, case, repetition, environment, evaluator, manifest, and ceiling identities and different primary condition IDs. Repeated pairs within a case are not treated as independent.

The primary analysis first averages paired outcomes within each case across its valid repetitions, then estimates the equal-weight mean of those case-level values across the full eligible population. The resampling unit is the task case, carrying all of its paired repetitions.

## 3. Primary Quality Estimand

Let q be the case-level success proportion and define theta Q as mean(q Adaptive minus q Fixed) across eligible cases. Positive theta Q means higher success probability under MIND-Adaptive. The binary outcome is SUCCESS versus every non-success evaluator outcome, exactly as frozen in #219.

## 4. Quality-Preservation Margin

Quality preservation uses non-inferiority, not vague similarity or equivalence. The frozen absolute degradation margin is Delta Q = 0.05: Adaptive quality is preserved only when the one-sided lower confidence bound for theta Q is strictly greater than -0.05.

Five percentage points is the maximum acceptable primary-quality loss because the M20 objective is efficiency while retaining substantially the same ability to complete independently evaluated tasks; a larger loss would make a resource-saving claim practically misleading at suite resolution. The bound is an absolute task-success tolerance, interpretable across cohorts and provider configurations, selected prospectively from the task-quality safeguard rather than any M20 outcome.

## 5. Quality Hypotheses

The one-sided non-inferiority test is H0: theta Q is less than or equal to -0.05, versus H1: theta Q is greater than -0.05. Rejection requires the prescribed lower confidence bound, not a claim of equal quality.

## 6. Primary Resource Endpoint

The sole primary resource endpoint is logical provider interactions per attempted episode. It is the direct, condition-neutral count of accepted provider work under the #218 provider contract and captures the resource that adaptive deliberation can most directly avoid without assigning arbitrary weights to heterogeneous resources. Reasoning steps, tool attempts, and decision cycles are secondary descriptive metrics and cannot replace this endpoint after results are observed.

## 7. Resource Estimand

For each valid pair, provider difference is logical provider interactions Adaptive minus Fixed. The resource estimand theta R is the equal-weight mean of case-level paired provider differences across eligible cases. Negative theta R means fewer Adaptive interactions.

The minimum resource effect of practical importance is MRE R = -0.25 logical provider interactions per attempted episode. It represents one avoided accepted provider request per four attempted episodes: a concrete reduction in externally mediated model work, while being below the fixed smallest unit only through prospective aggregation. It is independent of provider price, token telemetry, and outcomes.

## 8. Inferential Hierarchy

Gate 1 is quality preservation. Gate 2 is tested only if Gate 1 passes: directional resource efficiency requires the prescribed upper confidence bound for theta R to be strictly below zero. The MRE is the design alternative used for power, not a retrospective threshold for declaring a nonzero reduction. If Gate 1 fails, resource results may be descriptive only and no quality-preserving efficiency claim is permitted. If Gate 2 fails after Gate 1 passes, quality preservation may be reported but resource efficiency is not demonstrated.

## 9. Alpha and Sidedness

Each primary gate uses one-sided alpha = 0.025, implemented as a 97.5 percent one-sided confidence bound. The quality gate is lower-tailed for degradation protection; the resource gate is upper-tailed for a reduction. Directionality is justified by the predeclared efficiency claim, while #217’s neutral wording remains protected by reporting any contrary difference descriptively. There is one primary resource endpoint, so no primary-endpoint multiplicity adjustment is required. Secondary comparators, secondary resources, and cohorts are descriptive only; they receive no uncorrected inferential claims.

## 10. Power

Formal N must deliver at least 0.90 joint probability that both gates pass under the frozen design alternatives: theta Q = -0.025 and theta R = -0.25. The quality alternative is halfway to the unacceptable degradation boundary, preventing a design that assumes perfect quality parity; the resource alternative is exactly the frozen practical effect. Power is not reduced because N is inconvenient.

## 11. Nuisance Parameters

| Quantity | Status | Calibration treatment |
| --- | --- | --- |
| Delta Q, MRE R, alpha, power, primary contrast/endpoint, repetitions | Fixed by design | Never estimated or revised. |
| Paired success joint distribution and within-case dependence | Calibration-eligible | Conservative simultaneous confidence envelope. |
| Case-level variance/correlation of paired provider differences | Calibration-eligible | Upper confidence bound for variance; lower bound for beneficial correlation is not assumed. |
| Cluster heterogeneity and zero inflation | Calibration-eligible | Conservative empirical cluster distribution/envelope. |
| Provider/infrastructure missingness rate | Calibration-eligible | Upper confidence bound used to inflate required cases. |
| Suite identity, pairing, ceilings, metric semantics | Fixed by design | Must match exactly. |

No unknown nuisance value is silently filled. If a required conservative estimate is unavailable or invalid, there is no valid formal N.

## 12. Calibration-Eligible Quantities

Issue #224 may estimate only the four nuisance classes in section 11, using case-clustered records, with confidence-bound/envelope estimators stated there. It maps them mechanically into the simulation in section 13. Calibration cannot select or revise margins, MRE, alpha, power, endpoint, contrast, estimator, sidedness, or cohort allocation. Calibration records are not formal hypothesis evidence and cannot be pooled into formal analysis.

## 13. Sample-Size Procedure

The sample-size method is a deterministic paired, case-cluster simulation. For each candidate number of cases, it simulates 20,000 formal experiments under the frozen theta Q and theta R alternatives, five matched repetitions per case, the calibrated conservative nuisance envelope, and the exact Gate 1 then Gate 2 procedure. It preserves all repetitions inside their case cluster and applies the frozen missingness/replacement rule. The simulation seed is deterministically derived from protocol, suite, environment, evaluator, metric, provider, and manifest identities.

The output is either VALID FORMAL N when estimated joint gate-pass probability is at least 0.90 with simulation Monte Carlo uncertainty bounded below 0.005, or NO VALID FORMAL N. It cannot force a finite N.

## 14. Formal N Mapping

N is the number of unique eligible task cases. Candidate N starts at 72 cases, allocated equally as 12 cases in each of six frozen cohorts, with five matched repetitions per condition/case. Search increases N by six cases, adding one case to every cohort, until a valid N is found. The first valid candidate is selected; total intended formal executions are 2 times N times 5. If an eligible cohort cannot supply its allocation, validation fails; if operational capacity cannot support the first valid candidate, no valid formal N is declared rather than loosening parameters. There is no pre-approved finite maximum.

## 15. Paired and Cluster-Aware Analysis

For each primary estimand, use a paired case-cluster percentile bootstrap with 20,000 resamples. Resample task cases with replacement and retain every valid paired repetition belonging to each selected case. Compute case means before the equal-weight across-case mean. This preserves pairing, cohort membership, and within-case dependence; individual executions are never independently bootstrapped.

## 16. Confidence Intervals

The gates use 97.5 percent one-sided case-cluster bootstrap bounds: lower for theta Q and upper for theta R. The final report also gives two-sided 95 percent paired case-cluster percentile intervals for both primary estimates and descriptive secondary metrics, explicitly non-decisional for secondaries.

## 17. Missingness and Exclusion

| Category | Quality / resource inclusion | Rerun and pair treatment |
| --- | --- | --- |
| VALID_ANALYZABLE | Included in both under frozen endpoint rules. | No rerun. |
| VALID_BUT_INCOMPLETE | Quality non-success; observed resource included. | No rerun. |
| INFRASTRUCTURE_FAILURE or PROVIDER_FAILURE | Excluded from primary endpoints. | One replacement run permitted under section 18. |
| CONTRACT_INVALID or EVALUATOR_INVALID | Excluded; contract invalidity triggers readiness/formal stop review. | No replacement as a performance repair. |
| Metric unavailable for primary provider count | Pair is not analyzable. | One replacement only if caused by infrastructure/provider failure. |

A primary pair is analyzable only when both sides have one valid selected record. If either side remains unavailable after allowed replacement, the pair is excluded from both primary estimands and contributes to calibrated/formal missingness accounting. All original records remain immutable.

## 18. Reruns

Only a typed infrastructure or provider failure may receive one replacement for the same logical suite/case/repetition/condition cell. The replacement uses a new execution ID, preserves frozen configuration and all prior evidence, and is linked to the failed record. Wrong answers, high resource use, task failure, incomplete valid interaction, or poor comparator performance never permit rerun. A runner may not retry outside the provider/tool retry ownership frozen in #220.

## 19. Secondary Comparators

Direct, ReAct, and Plan are descriptive secondary comparators only. They cannot modify the primary decision, substitute for either primary condition, or receive inferential claims under this protocol.

## 20. Cohort Analysis

Cohort-stratified outcomes are descriptive only, reported for all frozen cohorts with counts and the same metric identities. No favorable cohort can substitute for the full eligible population or receive a confirmatory claim.

## 21. Pilot, Calibration, and Formal Separation

Pilot work is operational validation only. Calibration estimates only section-11 nuisances. Formal work tests only the frozen gates. A record has exactly one role; calibration cannot become formal evidence or be pooled with formal records.

## 22. Formal Progression Gate

Formal execution is prohibited unless suite/evaluator, comparator, and metric contracts are valid; harness/readiness pass; calibration is valid; every required nuisance parameter is available; a valid formal N exists; the formal namespace has zero existing formal records; and provider/execution identities are frozen. Any failed predicate yields NO FORMAL EXECUTION.

## 23. Stop Conditions

No defensible quality margin or MRE, evaluator invalidity, comparator asymmetry, invalid calibration, no valid formal N, provenance failure, or protocol contradiction are scientific stop conditions. The response is not to weaken the protocol.

## 24. Interpretation Rules

Allowed outcomes are: quality preserved plus resource efficiency demonstrated; quality preserved without demonstrated resource efficiency; quality preservation not demonstrated; or formal progression scientifically unavailable. Failure to demonstrate preservation does not establish Adaptive is worse, and failure to demonstrate resource superiority does not establish equal resource use.

## 25. Protocol Versioning

The identity is m20_statistical_protocol_v1. A material change after empirical execution requires a new protocol identity; all historical evidence remains bound to its original identity.

## 26. Downstream Dependencies

#222 records fields required here. #223 verifies conformance. #224 estimates only authorized nuisances. #225 audits calibration and valid formal N. #226 may execute formal runs only after #225 authorization. #227 independently reproduces the primary analysis.
