# M18 Confirmatory Population and Power Design

## Status and Scope

**M18 CONFIRMATORY POPULATION AND POWER DESIGN SPECIFIED.** This is a prospective, specification-only design for a future corrected M18 formal experiment. It does not execute a provider call or benchmark case, alter the original v3 pilot or v2 evidence, change the corrected comparator implementation, or modify any existing frozen suite artifact.

The original v3 pilot remains immutable descriptive evidence. The corrected condition (`m18_v3_comparator_contract_v2`) remains domain-separated from it; any future corrected pilot and formal records must use its separate provenance and result namespaces.

## Confirmatory Population

The confirmatory population is a **new prospectively generated eligible formal suite**. A case is eligible only if, before any provider output is obtained, it satisfies every observable, evaluator-verifiable property below:

1. Its primary construct is `dependent_stateful_composition`.
2. Its reference trajectory requires at least two ordered public state transitions before a valid final answer can be submitted.
3. At least one later required action has an executable identifier, admissible parameter, or required value determined by a public outcome from an earlier required transition. A fixed pre-written multi-tool sequence is insufficient.
4. The public task/action contract exposes only the current executable capability and current public parameter schema; it exposes no expected answer, future action, hidden state, difficulty label, or agent-specific routing hint.
5. A deterministic external evaluator owns the terminal completion predicate.
6. MIND and Direct receive the same public task, ordered capabilities, environment feedback/fault schedule, evaluator, external-action/tool/wall-clock budgets, and frozen provider configuration.

Eligibility is determined from generator artifacts, fixtures, reference trajectory, and manifest validation before the first corrected-pilot or formal provider call. It must not depend on success, failure, resource use, failure category, output text, or comparator behavior.

### Exclusions

Exclude a candidate from the primary population if it has no dependent later action; can complete in one public state transition; tests distractor selection or recovery/correction only; exposes hidden truth/future state; gives MIND and Direct non-equivalent public information or execution contracts; needs a known unavailable primary-condition capability; or appears in development, smoke, unit-test, pilot, historical v1/v2/v3, or corrected-pilot material.

The formal manifest must include `primary_eligible: true`, `primary_construct: dependent_stateful_composition`, a machine-checkable eligibility proof/version, and a source-seed namespace. No later label may add or remove a primary-denominator case.

## Contrasts, Endpoint, and Analysis Unit

The sole confirmatory contrast is **MIND-Lite versus Direct Tool Calling**, preserving the prior M18 review. ReAct and Plan-and-Execute may be reported only as secondary/descriptive conditions; they do not enter the primary effect, test, power calculation, or authorization threshold without a separate reviewed protocol.

The primary endpoint is evaluator-owned binary task-completion success: `success = 1`; every agent-originated non-success terminal class = `0`. Exact terminal/failure classes remain separately reported. Only a verified infrastructure-invalid episode is excluded and rerun under a frozen invalid-run rule. The future corrected schema must persist a closed invalidity flag and reason before execution.

The inferential unit is a formal **case cluster**, not a run. Each case has five paired repetitions for each primary condition. The MIND and Direct case values are their five-repetition success proportions; the primary effect is the equal-case-weighted mean of `MIND_i - Direct_i`. Resampling retains all repetitions in their case cluster and never treats 5N rows as independent.

## Relation to Existing v3 Cohorts

`multi_step`, `distractor_selection`, and `recovery_correction` remain frozen v3 source categories. They are not A/E labels and are not remapped by this document. They may inform future generator-template inventory, stratification metadata, or descriptive subgroup tables only after the new generator independently validates the eligibility rule above.

The new suite uses its own `primary_construct` and `primary_eligible` fields. The original v3 pilot and its 162-case formal split are not the confirmatory population.

## Prospective Formal-Suite Construction

Generate only from new formal source-seed namespaces disjoint from development and corrected-pilot namespaces. Use at least two independently specified deterministic template families for `dependent_stateful_composition`. Within each family, generate balanced evaluator-only structural-difficulty strata based on declared dependency depth and public state-transition count. The exact stratum count is a manifest field. Allocate cases equally across family × difficulty strata wherever the power-selected total permits; allocate a remainder by frozen round-robin order.

For every eligible case, schedule MIND and Direct for repetitions 1–5. Each matched case × repetition cell uses the same frozen public case, environment seed/fault schedule, evaluator, and provider configuration, with fresh agent/environment instances. Counterbalance comparator order within case/repetition using a deterministic ordering seed and record the resulting order in the manifest.

The formal manifest must freeze generator version/hash, template hashes, source/environment/ordering/per-episode seeds, ordered case IDs, eligibility proof, strata, condition identities/commits, prompts/parsers, provider configuration, budgets, evaluator, failure map, repetition count, result schema, and this analysis-plan identity. It must deterministically validate the selected number of complete primary case clusters.

## Power and MDE Framework

The confirmatory design fixes a two-sided alpha of **0.05**, power target of **0.90**, and minimally relevant absolute MIND-minus-Direct improvement of **10 percentage points** in equal-case-weighted success proportion. This MRE is a prospective relevance threshold, not an estimate from pilot or historical M18 outcomes.

The formal primary test is the two-sided complete-five-vector within-case label-permutation test: 100,000 Monte Carlo permutations, seed `189000002`. Report a 95% paired nonparametric case-cluster bootstrap: 10,000 draws, seed `189000003`.

Before formal-suite generation, a power record must state: candidate cluster count and balanced allocation; MIND/Direct marginal assumptions under the MRE; paired discordance probabilities `p10=P(MIND=1,Direct=0)` and `p01=P(MIND=0,Direct=1)`; within-case and between-condition repeated-measure dependence (or a conservative envelope); infrastructure-invalid rerun treatment; simulator/version; scenario grid; and simulation seed `189000001`.

Power is determined by **simulation**, not an independent-row McNemar approximation. For each candidate N, simulate paired five-repetition vectors under every registered nuisance scenario, apply the same permutation decision rule intended for formal analysis, and estimate rejection probability. Select the smallest stratum-balanced N whose lower Monte Carlo confidence bound reaches 0.90 for every registered scenario compatible with the MRE. The power record must predeclare simulation draw count and interval method. A case-level McNemar calculation may be a conservative cross-check only; it cannot replace the clustered simulation.

### Permitted Corrected-Pilot Nuisance Update

The corrected pilot may supply nuisance estimates only after complete, admission-valid, non-overlapping execution. Before the pilot begins, freeze a pilot-to-power addendum specifying pilot cases/size; a formal-fixture-blind extract; estimators for `p10`, `p01`, margins, and dependence; confidence-set construction; scenario-envelope rule; and simulation code/version. The formal power record must choose the **most conservative** N over that predeclared confidence/scenario envelope, not a favorable point estimate, and it may be produced once before formal-suite generation.

The addendum may not change endpoint, contrast, alpha, sidedness, MRE, eligibility, repetitions, success mapping, permutation test, bootstrap, or multiplicity policy. If its envelope cannot yield a feasible N, formal execution is prohibited until the owner approves a new versioned design.

## Corrected-Pilot Role

The corrected pilot may inform operational validity; result admission/provenance; terminal/failure-taxonomy completeness; provider/harness feasibility; the infrastructure-invalid rerun workflow; and only through the pre-execution addendum, nuisance variance/discordance/dependence estimates for conservative formal sizing.

It may not select formal cases, map v3 cohorts to A/E, alter eligibility, endpoint/success mapping, primary contrast, alpha/sidedness/MRE/repetitions, or tune prompt/budget/evaluator/provider from outcomes. It establishes no formal comparative claim and is never pooled with formal records.

## Formal Progression Rule

Formal execution remains prohibited until:

1. An explicitly authorized corrected pilot completes under its isolated condition and passes admission, provenance, and failure/infrastructure-classification checks.
2. The pilot-to-power addendum was frozen before the pilot, and its one-time conservative calculation selects feasible N without changing protected fields.
3. A new formal suite is deterministically generated at N, contains only eligible clusters, and passes held-out separation, balance, pairing, and manifest audits.
4. The formal manifest binds endpoint/failure/invalidation mapping, corrected provenance, analysis hierarchy, resampling seeds/draws, condition identities, provider, prompts, budgets, environment, evaluator, ordering, and result schema.
5. An independent methodology/architecture review confirms this implementation and separately authorizes formal execution.

No prerequisite implicitly authorizes a provider call.

## Claim Boundary

A later frozen formal result can support only a bounded claim about this new eligible dependent-stateful-composition population, the corrected MIND and Direct implementations, provider configuration, and execution contract. It cannot support a claim about general intelligence, general reasoning, all v3 cohorts, ReAct/Plan superiority, or the historical v3 pilot.
