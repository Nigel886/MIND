# M14 Agent Quality Evaluation Protocol

## Status and boundary

This protocol freezes a reproducible methodology for evaluating observable MIND agent behavior. It does not authorize benchmark execution, create a capability, or change the MIND runtime. M14 does not evaluate intelligence, reasoning superiority, general capability, autonomous learning, or benchmark superiority.

## 1. Research Questions

| ID | Question | Permitted conclusion |
| --- | --- | --- |
| RQ1 — Effectiveness | What proportion of eligible frozen tasks reaches its deterministic success predicate? | Observed task success by cohort, category, and difficulty. |
| RQ2 — Robustness | How do outcomes change under declared malformed actions, tool failures, timeouts, and budget conditions? | Controlled failure and recovery behavior. |
| RQ3 — Efficiency | What public resources are consumed under equivalent limits? | Steps, tool calls, model calls/tokens where applicable, wall time, and estimated provider cost. |
| RQ4 — Limitations | Which predeclared task and failure categories are unsupported or terminate incorrectly? | A category-specific failure taxonomy and capability boundary. |

No research question supports a claim about intelligence, reasoning quality, learning, adaptation, real-world performance, or architectural superiority.

## 2. Cohort A and Cohort B

### Cohort A — deterministic local evaluation

Cohort A compares the delivered MIND agent through the M14 evaluation adapter with one preregistered deterministic direct-policy control. Both use the same `EvaluationCase`, `EnvironmentConfig`, action vocabulary, tool schema, completion predicate, and resource budget under Issues #61–#64.

**Cohort A deterministic evaluation is currently allowed**, once frozen fixtures, a CompletionJudge, result storage, and configuration hashes are implemented and reviewed. Its scope is direct tasks, single controlled-tool tasks, unsupported tasks, and controlled failures. It is a local behavioral reference, not an external-agent superiority comparison.

### Cohort B — external LLM baseline comparison

Cohort B is reserved for a separately approved LLM-enabled MIND Agent, Direct Tool Calling, a fixed ReAct implementation, and a fixed Plan-and-Execute implementation. Every eligible configuration must use the same provider, exact model identifier/revision, public tool and action schema, serialized task, completion predicate, maximum steps, tool-call budget, model-call/token limits, wall-clock deadline, retry policy, and cost accounting boundary.

**External LLM baseline comparison is blocked until LLM-enabled MIND Agent execution is independently reviewed.** M13 provides controlled task interpretation and Meta-Inference integration; it does not provide an LLM decision or execution policy for the MIND Agent. No Direct Tool Calling, ReAct, or Plan-and-Execute result may be presented as a fair MIND comparison before that gate is lifted.

## 3. Task Suite Specification

Before execution, register a versioned immutable manifest. Each task record contains the suite identifier/version, task identifier, category, difficulty, `held_out` or `development` status, serialized `EvaluationCase`, `EnvironmentConfig` version/hash, exact `EvaluationBudget`, deterministic completion-rule identifier with JSON-compatible expected data, recovery allowance, and baseline-cohort eligibility.

Publish the manifest hash, ordered case identifiers, completion-rule version, and environment hash. Exclude credentials, raw prompts/provider payloads, hidden reasoning, private runtime state, and agent objects.

The primary suite is balanced across `basic`, `composed`, and `adversarial` difficulty strata, with at least four held-out cases per category/difficulty cell (a minimum 48-case primary suite).

| Category | Deterministic success predicate | Current MIND boundary |
| --- | --- | --- |
| Direct task handling | Exact public answer and valid terminal action. | Narrow direct-value tasks supported. |
| Controlled tool use | Correct permitted tool action/parameters and exact public result. | One controlled calculator call supported. |
| Multi-step/dependency | Public milestones occur in order and final exact predicate passes. | Not delivered; report as a limitation. |
| Failure recovery | Correct result after one declared recoverable fault within fixed limits, or explicit safe failure. | Not delivered; implicit retries receive no credit. |

`Adversarial` means boundary-valid difficult public inputs, malformed-action conditions, or declared environment faults; it does not authorize unbounded attack testing. A changed task or completion rule requires a new suite version.

## 4. Baseline Protocol

All baselines within a cohort receive the identical serialized task, environment, completion predicate, action/tool schema, and resource budget. Baseline order is balanced by a recorded seed, and every repeat starts with a fresh deterministic environment. Non-applicable cells are declared before execution and reported separately; they are never removed after outcomes are known.

For future LLM runs, method-specific prompts may differ only where required by the frozen baseline definition and must be versioned before execution. No `latest` model alias, hidden fallback model, agent-specific tool, agent-specific retry policy, or unequal budget is allowed.

## 5. Metric Definitions

The primary metric is **task success rate**:

`successful terminal outcomes / all attempted eligible task runs`

Failures, timeouts, invalid executions, and malformed outputs remain in the denominator. Report every category/difficulty cell, macro average across cells, and exact overall numerators and denominators.

Secondary metrics:

- **Action efficiency:** public steps and tool calls per attempted run and per successful run.
- **Resource usage:** model calls, input/output tokens, wall time, and estimated provider cost only where the measurement source is documented.
- **Recovery correctness:** successful recovery divided by declared recoverable-fault attempts; safe explicit failure is reported separately.
- **Failure semantics:** counts/rates for unsupported tasks, invalid actions, tool failures, budget exhaustion, timeouts, provider failures, and judge/configuration failures.
- **Deterministic repeatability:** exact equality of public outcome/action/feedback signatures across Cohort A repeats. Cohort B reports observed semantic agreement only.

Metrics are descriptive. This protocol defines no intelligence, reasoning, capability-improvement, or composite-superiority metric.

## 6. Reproducibility Requirements

Every batch records repository commit and clean/dirty state; Python, OS, and dependency versions; task-manifest/environment/Judge/tool-schema hashes; budgets, failure schedule, and completion-rule version; baseline revision and configuration hash; and execution order/seed.

For LLM runs, additionally record provider, exact model/revision, API/SDK and endpoint, prompt-template hashes, decoding settings, supported seed, timeout/retry/rate-limit policy, and pricing snapshot. Each repeat resets the environment. A task, provider/model, prompt, configuration, or baseline change creates a new batch identifier and may not be merged with previous results.

Store only compact public traces, outcomes, resource counters, and failure categories. Do not store credentials, raw prompts or provider responses, hidden reasoning, private objects, or RuntimeState/Belief dumps.

## 7. Statistical Analysis Plan

- Cohort A runs three repetitions per eligible case/baseline in registered case and balanced-baseline order. Exact public signature agreement is required; disagreement is a reproducibility failure, not an average.
- Cohort B, after the execution gate is lifted, runs five repetitions per eligible case/baseline. Report every repeat and task-level proportion; do not select a best sample.
- Aggregate category × difficulty first, then report macro and overall rates with exact numerators/denominators and bootstrap 95% intervals over task IDs where applicable.
- Preserve paired case-level comparisons and publish the first public terminal category, recovery eligibility, and frozen budget state for every failure.
- Exclude only predeclared infrastructure-invalid runs; list their reason and count separately.

## 8. Current Execution Gates

Before Cohort A execution, freeze and review:

1. versioned task fixtures and manifest;
2. deterministic CompletionJudge schema;
3. preregistered deterministic direct-policy control;
4. compact result-storage schema; and
5. configuration, environment, tool-schema, and completion-rule hashes.

Cohort A may then execute only the delivered capability cells. Unsupported multi-step and recovery cells remain limitation evidence, not authority to add behavior during evaluation.

Before Cohort B execution, independently review and deliver an opt-in LLM-enabled MIND decision/execution path and every external-baseline adapter. The same-model/provider, common-budget, common-tool, and versioned-prompt requirements must be verifiable. Until then, Cohort B is blocked and no external comparison claim is permitted.

## Limitations

This is a controlled local research methodology. It has no external benchmark, no real-provider execution, no claim of agent-quality improvement, and no authority to change MIND architecture or runtime behavior.
