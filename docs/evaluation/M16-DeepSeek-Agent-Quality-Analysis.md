# M16 DeepSeek Agent Quality Statistical Analysis

This report is generated from the completed M16 Cohort A DeepSeek restart1 result records. It analyzes only the frozen restart1 dataset and does not include historical Gemini, Flash-Lite, or invalidated first DeepSeek records.

## Executive Summary

Under the frozen M16 Cohort A restart1 setting, MIND-Lite had an observed completion rate of 0.0%, compared with 89.2% for Direct Tool-Calling: an absolute paired difference of -89.2 percentage points (paired cluster-bootstrap 95% CI [-94.4, -83.1]; paired case-clustered permutation p=0.000010, 100,000 Monte Carlo draws). The paired case-clustered analysis is reported in the machine-readable tables and figures under `evaluation/analysis/m16_deepseek_restart1/`. This is a bounded result for the frozen provider configuration, suite, budgets, evaluator, and execution attempt; it is not a claim about general intelligence, reasoning, or performance outside this setting.

## Frozen Experiment Identity

- Execution attempt: `restart1`
- Provider configuration hash: `c074c0e08e6b7be9a93b955a5c5f85da52bb7e9cf83601477ab2e18dad4bc780`
- Manifest hash: `559c5e5dec527d5abffedb409725b89580818bd832846f64adedcd328d081ac9`
- Suite hash: `a450c6fa2955136da5d4db08b892af442ab7be66034412739d91e7cbf076445c`
- Split hash: `a41ca5a326da4f722de1fcca4c7a4b85fcf860767ba1bb0311aa6cc4176aefe3`

## Dataset Integrity

The dataset contains 960 unique terminal run IDs: 96 formal cases, two paired baselines, and five repetitions per baseline per case. It contains zero unresolved, infrastructure-invalid, and interrupted records. No historical Gemini, Flash-Lite, or invalidated first DeepSeek result was included.

## Statistical Unit

The inference unit is the formal case. Each case/baseline pair is represented by its five-repetition mean success proportion; individual repetitions are not treated as independent confirmatory observations.

## Primary Outcome

`success` maps to one and every other terminal category maps to zero for the primary completion outcome. Exact terminal categories remain available separately in the failure taxonomy.

## Primary Effect

The primary estimand is the equal-case-weighted MIND-Lite minus Direct Tool-Calling completion-rate difference. The observed difference is -0.8917 (-89.2 percentage points). The relative ratio is not meaningful because the MIND-Lite rate is zero.

## Primary Permutation Test

The sole confirmatory test is a two-sided paired, case-clustered label-permutation test, swapping complete baseline vectors within cases. It used 100,000 Monte Carlo permutations and frozen seed `913202609`, producing p=0.000010. It is not an unpaired test and does not treat run-level repetitions as independent.

## Bootstrap Confidence Intervals

Percentile 95% confidence intervals were produced by a paired cluster bootstrap over cases, retaining both baselines and all repetitions together, with 10,000 draws and frozen seed `913202610`. MIND-Lite: [0.0%, 0.0%]; Direct Tool-Calling: [83.1%, 94.4%]; paired difference: [-94.4, -83.1] percentage points.

## Case-Level Paired Results

The 96-case machine-readable paired table is `case_level_paired_results.csv`; the paired-difference distribution appears in `case_level_difference_distribution.svg`. The analysis does not select or omit individual cases after observing outcomes.

## Family Analysis

Calculator (48 cases): MIND-Lite 0.0%, Direct 100.0%, difference -100.0 percentage points (95% CI [-100.0, -100.0]). Direct-answer (48 cases): MIND-Lite 0.0%, Direct 78.3%, difference -78.3 percentage points (95% CI [-88.3, -67.1]). Both are exploratory estimates.

## Difficulty Analysis

Easy (32 cases): difference -100.0 percentage points (95% CI [-100.0, -100.0]). Medium (32): -100.0 ([-100.0, -100.0]). Hard (32): -67.5 ([-81.9, -52.5]). These are exploratory estimates.

## Family × Difficulty Analysis

All six cells are exploratory. Calculator easy, medium, and hard each had a -100.0 percentage-point difference. Direct-answer easy and medium each had a -100.0-point difference; direct-answer hard had -35.0 points (95% CI [-53.8, -17.5]). The full estimates and intervals are in `family_difficulty_results.csv`.

## Repetition Sensitivity

Direct completion rates for r1–r5 were 90.6%, 88.5%, 87.5%, 88.5%, and 90.6%; MIND-Lite was 0.0% in each repetition. This is sensitivity/descriptive output only, not five independent confirmatory experiments.

## Failure Taxonomy and Resources

Exact terminal categories are retained in the taxonomy table. MIND-Lite had 480 `agent_fail` records; Direct Tool-Calling had 428 `success` and 52 `wrong_answer` records. Provider request attempts/logical calls were 480/480 for MIND-Lite and 720/720 for Direct Tool-Calling (1.0 and 1.5 per run respectively). Token totals, cached tokens, latency, and returned-model observations were not persisted and are reported as **UNAVAILABLE**, never as observed zero use.

## Missing Telemetry

The persisted request-attempt and logical-model-call counters are complete. Prompt tokens, output tokens, total tokens, cached tokens, latency, and returned-model observations are unavailable in all restart1 records. The analysis neither imputes nor backfills these fields.

## Limitations and Claim Boundary

This analysis has no missing outcomes, unresolved runs, infrastructure-invalid runs, or interrupted runs. It does not impute, censor, or remove terminal outcomes. It does not establish general superiority, general intelligence, a general reasoning advantage, cross-provider performance, or results beyond this frozen task suite and provider configuration. Historical runs included: **NO**. Result-driven tuning: **NO**.

## Publication-Ready Summary

Use the primary table, paired case-level table, and forest plot together. Any prose should say “observed higher/lower completion rate under the frozen M16 Cohort A restart1 setting” and include the reported effect, confidence interval, and prespecified permutation result.
