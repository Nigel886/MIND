# M18 Comparative Statistical Analysis Protocol

## Status and Authority

**M18 COMPARATIVE STATISTICAL PROTOCOL FROZEN.** This prospective, specification-only protocol completes Issue #188 using the #189 population and power design. It authorizes neither a corrected-pilot provider call nor formal execution. Original M18 v3 pilot evidence is immutable, descriptive, domain-separated historical evidence. It cannot select this protocol's population, endpoint, threshold, or conclusion.

## Analysis Universe and Unit

The analysis universe is the new held-out formal suite. Every primary case must be marked primary_eligible: true and carry a machine-checkable proof that it satisfies dependent_stateful_composition. Existing v3 labels multi_step, distractor_selection, and recovery_correction are not remapped to A/E; they are source metadata or descriptive subgroup variables only.

A run-level outcome is one admitted terminal episode for a formal case, condition, and repetition. Each primary case has five MIND and five Direct repetitions. The paired case × repetition cell shares the public fixture, environment seed/fault schedule, evaluator, provider configuration, and external budgets; each episode uses fresh agent/environment instances. Comparator order is manifest-counterbalanced.

The inferential cluster is the case. For each case, MIND and Direct are each represented by their five-repetition success proportion. The primary effect is the equal-case-weighted mean MIND-minus-Direct proportion. Individual repetitions are never independent inferential observations; all five outcomes for both conditions remain together in every resampling operation.

## Primary Endpoint and Invalid-Run Policy

The evaluator-owned binary endpoint is success = 1; every comparator-originated non-success is 0.

| Result | Classification |
| --- | --- |
| evaluator outcome success | SUCCESS (1) |
| wrong_answer; malformed_answer; interaction_incomplete | COMPARATOR TASK FAILURE (0) |
| agent_failure or agent_internal_failure | COMPARATOR TASK FAILURE (0) |
| budget_exhausted | COMPARATOR TASK FAILURE (0) |
| invalid_action_exhausted or invalid_action_threshold_reached | COMPARATOR TASK FAILURE (0) |
| recoverable_failure_exhausted or recoverable_failure_threshold_reached | COMPARATOR TASK FAILURE (0) |
| timeout caused by the frozen episode wall-clock budget | COMPARATOR TASK FAILURE (0) |
| provider_failure, including provider transport timeout | INFRASTRUCTURE-INVALID; rerun required |
| provenance-invalid, schema/integrity failure, duplicate/conflicting identity, missing declared tool response | INFRASTRUCTURE-INVALID; rerun required |
| missing expected run | NON-ANALYZABLE; rerun required |

The future corrected schema must carry a closed invalidity reason/failure origin, making this classification mechanical before results exist. Infrastructure-invalid or missing records enter neither numerator nor denominator. They are rerun using the same frozen identity. Formal analysis requires one unique, admitted terminal record for every expected primary identity; unresolved invalid/missing records block analysis and closeout.

## Contrasts and Multiplicity

MIND-Lite versus Direct Tool Calling is the sole confirmatory contrast. ReAct and Plan-and-Execute are secondary/descriptive only: report their rates, intervals, and terminal-category counts separately, without confirmatory p-values or ranking.

If a later independently reviewed amendment authorizes inferential MIND-versus-ReAct and MIND-versus-Plan claims, all three contrasts form one family and use Holm adjustment. That amendment cannot alter the MIND-versus-Direct primary conclusion. Cohort, family, difficulty, source-category, repetition-wise, and interaction analyses are exploratory and have no confirmatory p-values.

## Confirmatory Inference

Use a two-sided paired complete-five-vector label-permutation test at alpha = 0.05. For each case, swap the complete MIND and Direct five-outcome vectors or leave both unchanged. Compute the mean case-level paired difference. Never independently swap repetitions.

Use 100,000 Monte Carlo permutations with Python random.Random seed 189000002. Canonical order is ascending manifest case ID, then repetitions 1 through 5. The finite-simulation-corrected p-value is (1 + number of absolute statistics at least the observed absolute statistic) / 100001.

If the observed paired effect is zero, report p = 1. If every matched case has zero discordance, report p = 1 and the exact zero-discordance condition; do not substitute an odds ratio or unpaired test. Exact enumeration may replace Monte Carlo only if feasible and recorded in the analysis manifest; otherwise the frozen Monte Carlo procedure applies.

## Effects and Confidence Intervals

The primary effect is the absolute paired difference in equal-case-weighted success proportion, reported in percentage points. The minimally relevant effect is +10 percentage points for MIND minus Direct. It is a prospective relevance/power threshold, not a post-result significance cutoff.

Report MIND and Direct run-level numerators/denominators and equal-case-weighted means; the paired absolute effect; the primary permutation p-value; paired run-level discordance counts n10 (MIND success/Direct failure) and n01 (MIND failure/Direct success); and terminal-category counts.

Use a 95% percentile paired nonparametric case-cluster bootstrap: 10,000 case resamples with replacement, preserving both complete five-repetition vectors, random.Random seed 189000003, and 2.5th/97.5th empirical percentiles. Produce intervals for MIND, Direct, and their paired difference. Independent-row bootstrap, normal/Wald paired-effect intervals, and separation-prone logistic regression are not primary methods. Report boundary rates and degenerate intervals as observed.

## Corrected-Pilot Nuisance Estimation

The corrected pilot is operational/design evidence only and is never pooled with formal records. Before the first pilot provider call, its pilot-to-power addendum must freeze pilot IDs/size, formal-fixture non-overlap proof, data extract, and the following estimators.

| Quantity | Estimator/data | Formal-N treatment |
| --- | --- | --- |
| Marginal rates | Admitted corrected-pilot MIND/Direct terminal proportions with case clustering | Predeclared conservative confidence/scenario envelope for margins |
| Paired discordance | Empirical p10, p01, and p10 + p01 over matched case × repetition cells | All compatible discordance pairs in the frozen envelope, never a favorable point estimate |
| Repeated-measure dependence | Case-clustered covariance/correlation of five paired outcome vectors; boundary undefined values are unavailable | Conservative dependence envelope |
| Feasibility | Admission completion, invalid/rerun incidence, and harness/manifest counts | Confirms simulator inputs can be instantiated; does not alter thresholds |

Pilot estimates may not alter endpoint, terminal map, contrast, alpha, sidedness, MRE, eligibility, repetitions, test, bootstrap, or multiplicity. Unavailable or degenerate estimates expand the conservative envelope and never justify an unpaired method.

## Pilot-to-Power Addendum

The addendum is a one-time mechanical application, not a redesign. It must contain: pre-pilot frozen IDs and non-overlap proof; exact admitted records, rerun ledger, and digest; frozen estimators/confidence-set method; scenario table for margins, p10, p01, and dependence; Python/software version; canonical ordering; 100,000 power-simulation draws using random.Random seed 189000001; a lower one-sided 95% Monte Carlo confidence-bound method; balanced family × difficulty allocations; and candidate N values.

Select the smallest balanced N whose lower power confidence bound reaches 0.90 for every frozen nuisance scenario compatible with the 10-point MRE. The addendum chooses N only. Infeasible N, incomplete pilot, or an assumption mismatch blocks formal progression and requires a new owner-approved protocol version.

## Formal Progression and Reproducibility

Formal execution remains prohibited until: an explicitly authorized corrected pilot is complete and admission-valid with no recurring corrected-comparator defect; invalid/missing pilot records are resolved; nuisance estimates and addendum pass frozen rules; conservative simulation produces feasible balanced N; a new held-out eligible formal suite exists at N; the formal manifest freezes identities, eligibility proofs, prompts/parsers, provider/configuration, budgets, environment/faults, evaluator, failure map, ordering/seeds, schema, and analysis manifest hash; preflight proves a complete unique valid universe; and an independent methodology/architecture readiness review separately authorizes execution.

Use Python 3.11+ and standard-library random.Random for primary randomization. Canonical JSON uses sorted keys and compact separators. The analysis manifest records the protocol ID, every seed/draw count/procedure, formal-manifest hash, canonical input-record digest, output hashes, Python/software/platform version, and UTC creation time. Identical canonical inputs must reproduce the analysis tables and conclusions.

## Interpretation Limits

Corrected-pilot results may support only operational validity, failure-taxonomy, and power-nuisance statements. Descriptive comparator results may describe observed rates and terminal classes. Confirmatory formal inference may support only a bounded claim about the new eligible dependent-stateful-composition population, corrected MIND and Direct implementations, provider configuration, and execution contract.

No result may claim general intelligence, universal reasoning superiority, coverage of all v3 cohorts, ReAct/Plan superiority, cross-provider generalization, or causal attribution for historical v3 failures. A primary result is always reported with paired effect and confidence interval, never p-value alone.
