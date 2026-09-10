# M16 Repaired Post-Hoc Statistical Analysis

## Executive Summary

Under the repaired post-hoc M16 setting, MIND-Lite completed 100.0% of tasks (480/480) and Direct Tool-Calling completed 90.0% (432/480). The equal-case-weighted paired difference was +10.0 percentage points (paired cluster-bootstrap 95% CI [+4.8, +16.2] percentage points; paired case-clustered permutation p=0.000990, 100,000 Monte Carlo draws). This is a bounded result for this repaired post-hoc setting, not a claim of general superiority, intelligence, or reasoning ability.

## Post-Hoc Status

This analysis uses only `evaluation/results/m16_deepseek_repaired_posthoc_v1/`. It is a new post-hoc analysis and does not pool, replace, or revise #90/#91/#92/#93 results.

## Frozen Experiment Identity

- Manifest: `7fb0013b2c93f23b6288604e374c9374477c427a14babbb7556454641f4304bb`
- Provider config: `c074c0e08e6b7be9a93b955a5c5f85da52bb7e9cf83601477ab2e18dad4bc780`
- Repaired MIND request / schema: `b1e64996a00eb237b7c26cab21103cdc68c392384b06e19c06b822f16a74edf5` / `f041d3f276051380edb7e3a7d520aec770592efb5a348616999e8d9197c73ccf`
- Direct request: `db59e3676a3fd2c719c7a18eded0db9443c3a83303e3831431b808990ae87078`

## Dataset Integrity

The analysis loaded 960 unique terminal records: 96 paired cases, two baselines, and five repetitions per baseline/case. Historical runs analyzed: NO. Diagnostic v1 runs analyzed: NO.

## Experimental Unit

The inferential unit is the formal case (N=96). Each baseline's five repetitions are aggregated to a case-level success proportion; 480 run-level observations per baseline are not treated as independent.

## Primary Outcome

Evaluator-owned terminal `success` maps to one; every other terminal category maps to zero. Exact categories remain separately reported.

## Primary Effect

MIND case-level mean success was 100.0%; Direct was 90.0%; MIND minus Direct was +10.0 percentage points. A relative ratio is not primary because MIND is at the 100% boundary.

## Perfect-Success Boundary

MIND's bootstrap marginal interval is [100.0%, 100.0%]. The paired effect remains estimable. No ordinary separation-prone logistic model was used.

## Primary Permutation Test

The two-sided primary test swaps complete five-repetition baseline vectors within each of 96 cases. It used 100,000 Monte Carlo permutations with seed `970000001`; p=0.000990. Individual repetitions were never independently permuted.

## Bootstrap Confidence Intervals

A paired 96-case nonparametric bootstrap retained both five-repetition vectors per selected case. It used 10,000 draws with seed `970000002`. MIND: [100.0%, 100.0%]; Direct: [83.8%, 95.2%]; paired difference: [+4.8, +16.2] percentage points.

## Case-Level Paired Results

The 96-case table and difference distribution are in the machine-readable output. Differences are 0.0 for 85 cases, +0.2 for one case, +0.8 for three cases, and +1.0 for seven cases; no negative case difference occurred.

## Family Analysis

Exploratory estimates: calculator (48 cases) was 100.0% versus 100.0%, difference 0.0 points [0.0, 0.0]. Direct-answer (48) was 100.0% versus 80.0%, difference +20.0 points [+9.6, +30.8].

## Difficulty Analysis

Exploratory estimates: easy and medium each had a 0.0-point difference. Hard (32 cases) had +30.0 points [+15.6, +45.6].

## Family × Difficulty Analysis

All six cells are exploratory. The only non-zero cell was direct-answer × hard (16 cases): +60.0 points [+37.5, +81.2].

## Repetition Sensitivity

Descriptive MIND/Direct rates were r1 100.0%/89.6%, r2 100.0%/89.6%, r3 100.0%/90.6%, r4 100.0%/90.6%, and r5 100.0%/89.6%. No repetition-wise hypothesis tests were performed.

## Direct Error Concentration

All 48 Direct `wrong_answer` records were direct-answer × hard. They occurred across 11 formal cases: seven cases had five errors, three had four, and one had one. Repetition counts were 10, 10, 9, 9, and 10. This is descriptive and was not used for tuning.

## Failure Taxonomy

MIND: success 480. Direct: success 432; wrong_answer 48. No other category appears in the authoritative set.

## Resource Analysis

MIND recorded 480 provider requests/logical calls (1.0/run); Direct recorded 720/720 (1.5/run). Token, latency, cache, and returned-model telemetry are UNAVAILABLE because they were not persisted.

## Historical Context

The derived historical-context table is labeled DESCRIPTIVE CROSS-EXPERIMENT CONTEXT ONLY. No pooled original-versus-repaired inference was performed.

## Original-vs-Repaired Boundary

The original MIND 0% result and repaired MIND 100% result concern different implementation states. No p-value or confidence interval compares them.

## Limitations

The provider setting, task suite, budgets, evaluator, and repaired implementation are frozen and narrow. The boundary success rate and missing token/latency telemetry limit interpretation.

## Claim Boundary

The supported wording is “observed higher completion rate under the repaired post-hoc M16 setting,” together with effect, interval, and permutation result. Do not infer broad agent quality or general capability.

## Publication-Ready Statement

Under the repaired post-hoc M16 setting, MIND-Lite achieved 100.0% task completion compared with 90.0% for Direct Tool-Calling, corresponding to an absolute paired difference of +10.0 percentage points (95% CI [+4.8, +16.2], paired case-clustered permutation p=0.000990).
