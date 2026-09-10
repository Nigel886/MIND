# M16 Agent Quality Evaluation — Final Report

## Executive Summary

M16 produced two separate experimental records. The original frozen DeepSeek restart1 experiment recorded MIND-Lite 0.0% completion and Direct Tool-Calling 89.2%. A later post-hoc diagnostic identified a structured-output contract incompatibility in a new replication, followed by a minimal schema-bearing remediation. The separately frozen repaired post-hoc experiment recorded MIND-Lite 100.0% and Direct 90.0%, with a +10.0 percentage-point paired case-level difference (95% CI [+4.8, +16.2], p=0.000990). These are not pooled or treated as one experiment.

## 1. Research Question

Under frozen M16 Cohort A conditions, what completion outcomes, failure boundaries, and provider-call accounting are observed for MIND-Lite and Direct Tool-Calling? The repaired result addresses a distinct repaired implementation state.

## 2. M16 Evaluation Design

Both experiments use 96 cases, two baselines, five repetitions, evaluator-owned completion, and 96 paired case clusters for inference. Individual 480-run baseline totals are not independent inferential observations.

## 3. Original Frozen Formal Experiment

| Baseline | Success | Rate | Failure taxonomy |
| --- | ---: | ---: | --- |
| MIND-Lite | 0 / 480 | 0.0% | `agent_fail`: 480 |
| Direct Tool-Calling | 428 / 480 | 89.2% | `success`: 428; `wrong_answer`: 52 |

## 4. Original Statistical Analysis

Within the original frozen implementation state, the paired effect was -89.2 percentage points, 95% CI [-94.4, -83.1], paired case-clustered permutation p=0.000010. This result remains authoritative only for that original state.

## 5. Historical Failure Attribution Limitation

Original formal records lacked internal stage telemetry sufficient to identify the causal mechanism for each of the 480 historical `agent_fail` outcomes. The later audit mapped candidate paths but did not retrospectively attribute those failures.

## 6. Post-Hoc Diagnostic v1

All 96 new diagnostic runs followed `provider_request_started → provider_response_received → provider_decode_failure → malformed_structured_output → admission_failure → agent_fail`. None reached proposal construction, semantic validation, Meta-Inference, `IntegrationSelected`, private session, policy, action, or tool execution. This is compatible with the historical visible pattern, not proof of every historical cause.

## 7. Structured-Output Contract Investigation

Canonical M13 top-level fields are `intent`, `required_capabilities`, `constraints`, and `evidence`. The integration investigation found that JSON-object mode alone could permit syntactically valid objects using incompatible fields such as `type`, `capability`, and optional `goal`. This is a provider-integration/request-contract incompatibility, not a categorical provider fault. JSON-object mode ensures syntax, not canonical-schema conformance.

## 8. Schema-Bearing Compatibility Remediation

Repair `5b942df` reused `evaluation/schemas/m16_mind_interpretation_v1.json` (hash `f041d3f276051380edb7e3a7d520aec770592efb5a348616999e8d9197c73ccf`) through `load_schema()`, transmitted deterministic `response_schema` data, preserved JSON-object mode and strict `TaskInterpreter`, and added no aliases or permissive fallback. MIND core, Direct behavior, evaluator, task suite, budget, and completion contract were unchanged. This created a NEW implementation state; it does not rewrite the original experiment.

## 9. Repaired Post-Hoc Evaluation

The contemporaneous repaired evaluation used 96 cases × 2 baselines × 5 repetitions = 960 runs. MIND-Lite completed 480/480 (100.0%). Direct completed 432/480 (90.0%) with 48 `wrong_answer` outcomes. The observed paired difference was +10.0 percentage points.

## 10. Repaired Statistical Analysis

The primary analysis used 96 paired case clusters, 100,000 Monte Carlo complete-vector label permutations (seed `970000001`), and 10,000 paired cluster-bootstrap draws (seed `970000002`). MIND was 100.0%; Direct was 90.0%; difference +10.0 points; bootstrap CI [+4.8, +16.2]; permutation p=0.000990. MIND's perfect rate is a boundary condition; no separation-prone logistic model was used.

## 11. Case-Level Findings

| Paired difference | Cases |
| ---: | ---: |
| 0.0 | 85 |
| +0.2 | 1 |
| +0.8 | 3 |
| +1.0 | 7 |
| Negative | 0 |

Eleven of 96 cases favored MIND, 85 tied, and none favored Direct.

## 12. Family and Difficulty Findings

All following estimates are **EXPLORATORY**.

| Stratum | Cases | MIND | Direct | Difference | 95% CI |
| --- | ---: | ---: | ---: | ---: | --- |
| calculator | 48 | 100.0% | 100.0% | 0.0 pp | [0.0, 0.0] |
| direct_answer | 48 | 100.0% | 80.0% | +20.0 pp | [+9.6, +30.8] |
| easy | 32 | 100.0% | 100.0% | 0.0 pp | [0.0, 0.0] |
| medium | 32 | 100.0% | 100.0% | 0.0 pp | [0.0, 0.0] |
| hard | 32 | 100.0% | 70.0% | +30.0 pp | [+15.6, +45.6] |
| direct_answer × hard | 16 | 100.0% | 40.0% | +60.0 pp | [+37.5, +81.2] |

## 13. Failure Taxonomy

The repaired taxonomy is MIND `success`: 480; Direct `success`: 432 and `wrong_answer`: 48. Categories are preserved rather than collapsed in the derived taxonomy table.

## 14. Provider-Call Resource Analysis

| Baseline | Provider requests | Logical model calls | Calls/run |
| --- | ---: | ---: | ---: |
| MIND-Lite | 480 | 480 | 1.0 |
| Direct Tool-Calling | 720 | 720 | 1.5 |

MIND used fewer logical model calls in this repaired post-hoc setting. Token, latency, cost, cache, energy, and returned-model telemetry were not persisted and are not claimed.

## 15. Original vs Repaired Evidence Boundary

**DESCRIPTIVE CROSS-EXPERIMENT CONTEXT ONLY — DIFFERENT IMPLEMENTATION STATES / EXPERIMENTS.**

| Experiment | MIND | Direct | Paired effect |
| --- | ---: | ---: | ---: |
| Original frozen formal | 0.0% | 89.2% | -89.2 pp |
| Repaired post-hoc | 100.0% | 90.0% | +10.0 pp |

No pooled inference, 0%-to-100% test, or causal treatment-effect claim is made.

## 16. Scientific Claim Boundary

The repaired post-hoc result supports an observed higher completion rate under its frozen setting. It does not support general agent superiority, intelligence, reasoning superiority, arbitrary-task generalization, cross-provider generalization, cheaper/faster operation, lower token use, or a statistically proven 100-point remediation effect.

## 17. Limitations

The task suite, provider configuration, evaluator, budgets, and repaired implementation are narrow and frozen. The original attribution limitation remains. Perfect MIND completion is a boundary rate, and token/latency/cost telemetry is unavailable.

## 18. Reproducibility and Provenance

| Stage | Type | State | Namespace / identity | Interpretation |
| --- | --- | --- | --- | --- |
| Original | frozen formal | pre-repair | restart1 manifest `559c5e5…` | original result only |
| Diagnostic v1 | post-hoc diagnostic | pre-repair | manifest `2170633…` | mechanism replication only |
| Repair | compatibility remediation | `5b942df` | schema-bearing request | new state |
| Repaired | post-hoc paired evaluation | repaired | manifest `7fb0013…` | repaired result only |

MIND-Lite v1.0 commit/tag: `2a3fa4472f5b74690810d9b6fe12f59ad735a9de` / `v1.0.0`. Provider config hash: `c074c0e08e6b7be9a93b955a5c5f85da52bb7e9cf83601477ab2e18dad4bc780`. Suite/split: `a450c6fa…` / `a41ca5a…`. Repaired request/schema/Direct identities: `b1e64996…`, `f041d3f2…`, `db59e367…`. Repaired execution/analysis commits: `155ac3f` / `db072bd`. Relevant issues: #90–#98.

## 19. Publication-Ready Tables

Tables 1–7 are represented by the provenance ledger, original result table, diagnostic/remediation sections, repaired primary table, exploratory strata table, taxonomy table, and resource table above. Machine-readable counterparts are in `evaluation/analysis/m16_deepseek_repaired_posthoc_v1/`.

## 20. Publication-Ready Figures

- `evaluation/analysis/m16_deepseek_repaired_posthoc_v1/forest_plot.svg`
- `evaluation/analysis/m16_deepseek_repaired_posthoc_v1/case_level_difference_distribution.svg`
- `evaluation/analysis/m16_deepseek_repaired_posthoc_v1/repetition_sensitivity.svg` (DESCRIPTIVE / SENSITIVITY)
- `evaluation/analysis/m16_deepseek_repaired_posthoc_v1/direct_error_concentration.svg` (exploratory)

## 21. Recommended Paper Wording

Under the repaired post-hoc M16 setting, MIND-Lite achieved a 100.0% task-completion rate compared with 90.0% for Direct Tool-Calling, corresponding to a paired absolute difference of +10.0 percentage points (95% CI [+4.8, +16.2], paired case-clustered permutation p=0.000990). The observed difference was concentrated in hard direct-answer tasks, while calculator and easy/medium strata had identical completion rates. The original frozen evaluation is separate and is not replaced: a later post-hoc diagnostic identified a structured-output integration incompatibility in a new replication, motivating a minimal schema-bearing request remediation.

## 22. Final Research Conclusion

Under the repaired post-hoc M16 setting, MIND-Lite exhibited a higher observed task-completion rate than Direct Tool-Calling, with the paired effect supported by the prespecified case-clustered analysis. This evidence is specific to the frozen Cohort A task suite, provider configuration, and repaired DeepSeek integration.
