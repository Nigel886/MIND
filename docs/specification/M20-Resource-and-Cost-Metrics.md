# M20 Resource and Cost Metrics

## 1. Purpose

**SPECIFICATION ONLY** — This document freezes prospective M20 measurement semantics. It creates no instrumentation, execution harness, provider call, pilot, calibration, formal run, statistical test, or empirical record. It is normative with the M20 research question, comparator contract, and suite/environment contract.

M20 measures quality-preserving resource efficiency using condition-neutral primitive counts. No weighted composite score is created here.

## 2. Core Resource Dimensions

The canonical M19 consumable dimensions are reasoning steps, tool attempts, and provider interactions; decision cycles are a distinct episode-level execution count. All counts are non-negative integers, use one runtime/telemetry source of truth, and are subject to identical condition ceilings.

| Dimension | Counting unit and trigger | Ceiling relationship | Source of truth |
| --- | --- | --- | --- |
| Reasoning steps | One admitted bounded internal reasoning or replanning execution. | Shared M19 reasoning allocation. | Admitted runtime resource delta. |
| Tool attempts | One runtime-dispatched tool invocation after availability/schema admission. | Shared tool allocation. | Dispatch/return telemetry reconciled with M19 delta. |
| Provider interactions | One accepted logical request to the bound provider client. | Shared provider allocation. | Provider-client logical-operation record and M19 delta. |
| Decision cycles | One admitted public state observation through committed decision and resulting state/terminal classification. | Separately declared common episode ceiling. | Runtime decision-cycle record. |

## 3. Reasoning-Step Semantics

CONTINUE_REASONING and REPLAN each charge one reasoning step only when their bounded execution begins after admission. Pure deterministic policy evaluation, candidate ranking, provenance construction, and helper operations do not consume a reasoning step. Provider-backed reasoning is one reasoning step for the admitted execution and, independently, one provider interaction for its accepted logical request. A reasoning execution that begins and fails is charged; a precondition, budget, or invariant rejection before it begins is not.

## 4. Tool-Attempt Semantics

A tool attempt is charged at actual runtime dispatch after a request has passed public availability and schema admission. A dispatched call counts whether it succeeds, fails, repeats, or returns an environment-level invalid result. A malformed, unavailable, or schema-invalid request rejected before dispatch does not consume a tool attempt. Retries are separate dispatched attempts only when the tool contract explicitly authorizes retry; each is counted once, with no additional runner-layer charge.

## 5. Provider-Interaction Semantics

One provider interaction is one logical request accepted by the bound provider client. It is charged once, including when its response is malformed, times out, or exhausts retry. A physical transport attempt is not a second logical provider interaction; it is separately recorded as provider transport attempts. Every retry is one additional physical transport attempt owned solely by the provider client. The runner and runtime must not independently retry or charge the same request. Parse failure after a response remains attached to its logical interaction; an unaccepted request is not charged.

## 6. Decision-Cycle Semantics

A decision cycle begins when the runtime admits a public state projection for a next decision and ends when the committed decision has produced its resulting public state or terminal classification. It includes optional execution, but not a new cycle for provider/tool transport retries, policy helpers, or telemetry serialization. A pre-admission invariant rejection creates no cycle; an admitted decision that ends in execution failure completes one cycle with the typed outcome.

## 7. Failure Consumption Table

C means consumed, N not consumed, and — not applicable.

| Event | Reasoning | Tool | Provider | Cycle | Rule |
| --- | --- | --- | --- | --- | --- |
| Successful bounded reasoning | C | — | — / C if provider-backed | C | Provider-backed reasoning charges both primitives. |
| Successful dispatched tool execution | — | C | — | C | One dispatch, one cycle. |
| Successful logical provider interaction | C only if reasoning began | — | C | C | Transport attempts recorded separately. |
| Invalid action rejected before dispatch | N | N | N | C if decision was admitted | Typed invalid interaction. |
| Provider timeout / transport failure | C only if reasoning began | — | C | C | Retries add physical attempts, not logical interactions. |
| Malformed provider response / parse failure | C only if reasoning began | — | C | C | No hidden corrective request. |
| Tool failure after dispatch | — | C | — | C | One dispatched attempt. |
| Exhausted-budget rejection | N | N | N | N | Rejection precedes execution admission. |
| Runtime invariant rejection | N | N | N | N | Fail closed before admission. |

## 8. Retry Attribution

The operation hierarchy is logical operation to physical attempt to retry attempt. The provider client owns provider transport retries; the tool executor owns explicitly authorized tool redispatches; neither runner nor policy may add hidden retry. Episode telemetry records logical provider-operation count, provider transport attempts, logical tool-operation count where applicable, and dispatched tool-attempt count, allowing reconstruction without double charging.

## 9. Endpoint-Role Rules

The primary quality-preserving efficiency framing remains fixed by #217. This issue freezes all primitive measurements but does not choose a single inferential resource endpoint or hierarchy: #221 must prospectively select it from the frozen primitive set before any execution. It may not select a best-looking metric after outcomes. Tokens, monetary cost, latency, derived metrics, and diagnostics are not primary merely by being recorded.

## 10. Primitive and Derived Metrics

Primitive episode counts are reasoning steps, tool attempts, provider interactions, and decision cycles. Allowed derived quantities, when explicitly named later, are resource divided by attempted episodes; resource divided by completed episodes; resource divided by successful episodes; resource divided by fixed ceiling; and paired difference adaptive minus fixed. No derived metric is an endpoint unless the later statistical protocol declares it prospectively.

## 11. Normalization

Per-attempt includes every admitted episode. Per-completed excludes infrastructure-incomplete records only under a predeclared handling rule. Per-success is success-conditioned and can induce selection bias when success differs by condition; it cannot be the sole primary efficiency endpoint without #221 justification. Fraction-of-ceiling requires the matched, fixed ceiling source.

## 12. Token Metrics

If stable provider usage telemetry exists under the frozen provider configuration, a record may contain input/prompt, output/completion, and total tokens. Usage is summed across physical attempts when exposed; unavailable failed-call usage remains unavailable, not zero. Token metrics are descriptive unless same-model/provider comparability, field semantics, missingness, and a later endpoint role are prospectively established.

## 13. Monetary Cost

Monetary cost is computable only with a frozen provider pricing source/version, model identity, input/output pricing semantics, retry treatment, timestamp, and pricing-schedule identity. It includes declared physical retry usage. It is secondary/descriptive by default and supports no general real-world cost claim outside its recorded schedule.

## 14. Latency

Provider latency runs from provider-client dispatch through final provider outcome; tool latency from executor dispatch through result; episode wall-clock from first admitted public state through terminal classification. Clock identity and monotonic boundaries must be recorded. Network variance, local load, queueing, and retries make latency descriptive unless a future execution environment establishes adequate control. It is never a primary resource endpoint here.

## 15. Missingness

Missing values are typed, never zero and never silently dropped: TOKEN_USAGE_UNAVAILABLE, COST_NOT_COMPUTABLE, LATENCY_NOT_RELIABLE, and EPISODE_INCOMPLETE. Each optional field has an availability flag and reason. Later analysis receives the indicator, underlying typed outcome, and denominator rule.

## 16. Episode Resource Record

A future canonical record must include execution ID; suite, case, condition, repetition, and cluster IDs; metric schema/version; all four primitive counts; provider transport attempts; resource-ceiling identity; outcome/completion status; optional token, latency, and monetary fields; and availability flags. It also binds #219 suite/environment/evaluator/manifest identities and #218 condition/provider identities. This is a contract, not a runner implementation.

## 17. Pairwise Comparison Semantics

For a matched primary pair, resource delta equals adaptive resource minus fixed resource. Negative means fewer units for MIND-Adaptive; positive means more. Pairs require equal suite, case, repetition/cluster, environment, evaluator, manifest, and ceiling identities. This establishes identity and sign only, not significance.

## 18. Aggregation

Permitted descriptive summaries are total, mean, median, quantiles, distribution, and cohort-stratified summaries, each labeled with metric version and denominator. Formal estimator selection belongs to #221 and cannot follow observed outcomes.

## 19. Metric Versioning

The initial accounting identity is m20_resource_metrics_v1. A material change to counting, retry attribution, normalization, pricing logic, or latency boundaries requires a new metric version after data collection; original records retain their original identity.

## 20. Reconciliation Invariants

Future harness/readiness checks require non-negative counts; no consumption above applicable ceilings unless explicitly invalid; per-decision deltas summing to episode totals; reconciliation of resource deltas with runtime telemetry; no resource resurrection under one allocation identity; unique execution IDs; paired records sharing frozen case/repetition identity; and retry counts reconciling without duplicate ownership.

## 21. Downstream Dependencies

#221 selects inferential estimators/hierarchy from these frozen metrics. #222 records them exactly. #223 independently verifies reconciliation and retry attribution. #224 may estimate only prospectively authorized nuisance parameters. No downstream work may redefine accounting after empirical collection.
