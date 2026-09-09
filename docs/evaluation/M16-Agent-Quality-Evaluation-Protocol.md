# M16 Agent Quality Evaluation Protocol

**Execution protocol version:** 1.2.0
**Status:** Pre-execution correction; benchmark not executed

## Pre-Execution Completion-Semantics Revision (v1.2.0)

Protocol 1.1.0 froze and generated the Cohort A suite. Protocol 1.2.0 changes
only execution and judging semantics before any formal run: `direct_answer`
uses `agent_final_answer`, while `calculator` uses
`evaluator_tool_outcome`. The latter measures correct calculator selection,
operation, and operands; it does not measure post-tool answer synthesis. Both
MIND-Lite and Direct terminate after the same correct evaluator-owned tool
outcome. Suite content, membership, suite hash, and split hash remain frozen.

Version 1.1.0 corrects a benchmark-validity boundary discovered before any
formal suite, provider integration, or benchmark execution. MIND-Lite v1.0.0
remains the immutable evaluated artifact; this correction does not alter its
core implementation. Its frozen GoalAwarePolicy recognizes legacy task schemas
by the presence of `expected_answer`, while formal M16 tasks must not disclose
their expected answer to an agent.

M16 therefore uses an evaluation-only private compatibility projection for the
two eligible public schemas. A public direct task is exactly
`{"value": <JSON value>}`; a public calculator task is exactly
`{"operation": "add" | "multiply", "operands": [<int>, <int>]}`. Only on
the private MIND evaluation path, the projection constructs a detached legacy
Task copy with the fixed `"expected_answer": null` sentinel. The sentinel is
always `null`, is never benchmark truth, and is not read, computed, derived, or
revealed from evaluator-private truth. The Direct Tool-Calling baseline always
receives the original public Task.

Expected answers, judge configuration, formal membership, and private
environment configuration remain in evaluator-private M16 structures. M16
does not reuse M14 `completion_context`: that historic path emits completion
context in public reset feedback. The M16 path instead uses a private
environment boundary and deterministic exact evaluator-owned judge. No LLM
judge is permitted.

### Held-Out Regression-Test Clarification

"Held-out" prohibits using formal cases for provider-adapter debugging, prompt
or schema tuning, model/output-cap/retry selection, Agent dry runs, smoke tests,
benchmark execution, or task-level performance feedback before the formal run.
It does not prohibit repository regression tests that perform only static suite
integrity and contract checks: count/distribution, schema/privacy boundaries,
canonical serialization and hashes, fixture separation, and static
environment/judge compatibility. Such tests must not invoke MIND-Lite or Direct
benchmark Agents on formal cases, call a real or fake LLM with formal data,
export task contents for development, or inspect comparative outcomes.

## Purpose

This protocol freezes the research design for M16 evaluation of MIND-Lite
v1.0.0. It precedes formal task construction, provider
integration, and benchmark execution. It defines a fair restricted comparison
and separate capability-boundary analysis; it does not assume MIND-Lite is
superior.

## Evaluation Subject

The immutable subject is **MIND-Lite v1.0.0**, Git tag `v1.0.0`. Core behavior
must not change to improve benchmark results. Evaluation-side adapters may use
public contracts only and must preserve the frozen architecture.

## Comparability Assessment

**Protocol status: PARTIALLY COMPARABLE.** MIND-Lite uses an LLM for untrusted
task interpretation, deterministic validation, and one-time Meta-Inference
admission. Its existing GoalAwarePolicy remains the execution authority. Fully
LLM-driven ReAct and Plan-and-Execute agents generate execution actions,
planning, and recovery behavior through the model. A single aggregate ranking
would confound those execution capabilities with architecture effects and is
forbidden.

## Research Questions

- **RQ1 — Comparable Task Effectiveness:** within eligible Cohort A tasks, how
  do MIND-Lite and a schema-matched Direct Tool-Calling baseline compare in
  evaluator-owned completion?
- **RQ2 — Robustness:** under equivalent declared tool/environment failures
  within each architecture's eligible execution contract, what occurs?
- **RQ3 — Resource Efficiency:** what observable public resources are consumed?
- **RQ4 — Recovery Boundary:** where recovery is contract-compatible, what
  recovery behavior is observable?
- **RQ5 — Capability Boundary:** which planning, multi-step, and recovery tasks
  are outside the frozen MIND-Lite execution capability?

## Cohort A — Fair Comparative Benchmark

Cohort A is the sole primary comparative benchmark.

- **A:** MIND-Lite v1.0.
- **B:** Direct Tool-Calling Agent.
- Eligible families: schema-matched direct task execution and controlled
  single-tool execution.
- Both agents receive the same serialized task, public tool names/schema,
  environment state, feedback semantics, failure injection, evaluator-owned
  CompletionJudge, and visible hard budget.

Cohort A excludes planning, open-ended tool selection, multi-step dependency,
and recovery cases unless a pre-execution review proves equivalent execution
contracts. Its primary metric is evaluator-owned Task Completion Success Rate.
The constant-null legacy schema projection is evaluation compatibility only,
not a new MIND-Lite capability or source of task truth.

## Cohort B — Capability Boundary Analysis

Cohort B is labelled **CAPABILITY BOUNDARY ANALYSIS**, not an overall quality
ranking. It may include MIND-Lite, Direct Tool-Calling, ReAct, and
Plan-and-Execute conditions for planning, multi-step reasoning, and controlled
failure recovery. For intentional Lite capability absences, report eligibility,
observable behavior if attempted, failure mode, and architecture reason. Do not
pool these cases into Cohort A or transform safe failure into success.

## Task-Suite Design Rules

Freeze comparable families and architecture-neutral difficulty definitions:
easy, medium, and hard. Direct-answer strata may vary only by public `value`
JSON structure (primitive, flat structured value, or nested structured value).
Calculator strata may vary only by `add`/`multiply`, finite integer magnitude,
and sign pattern. No added instruction keys, prose extraction, planning,
recovery, multiple tools, or multi-step arithmetic may be used to manufacture
difficulty. Difficulty must arise from these predeclared public properties, not
from what is harder for MIND. The target remains at least 96 held-out Cohort A
cases: two comparable families × three difficulties × approximately 16 cases.
This is a design target, not proof of statistical sufficiency. Development and
formal held-out cases must be separated; formal cases are prohibited from prompt
tuning, implementation/debugging, baseline debugging, and judge development.

## Model and Provider Contract

Before formal execution, freeze provider; exact model identifier and revision
(never `latest`); API/version date; temperature; top_p where applicable; maximum
output tokens; structured-output mode; tool-calling settings; seed behavior;
timeout; rate-limit handling; retry policy; and privacy/retention conditions.
One exact model/provider configuration is sufficient for Cohort A. A second
model is a separately reported robustness/generalizability analysis, not a
post-hoc aggregate. A production provider and equivalent public action-provider
boundary require independent review before use.

## Frozen Gemini Provider Configuration

Before formal execution, the earlier OpenAI candidate was superseded by Google
Gemini **before any formal benchmark run**. The frozen primary provider path is
raw Gemini REST `generateContent` with exact stable model identifier
`gemini-2.5-flash`; no `latest` alias is permitted. The tracked configuration
manifest is `evaluation/config/m16_gemini_flash_v1.json` and freezes
`temperature=0`, `topP=1`, `candidateCount=1`, `seed=16001`,
`maxOutputTokens=512`, `responseMimeType=application/json`, and
`responseJsonSchema` output.

This is formally **STOCHASTIC**: every eligible formal case/baseline/
configuration unit requires five repetitions, regardless of the accepted seed
or zero temperature. The MIND and Direct conditions use distinct versioned,
hash-pinned architecture-specific prompts. MIND makes an interpretation call
followed by deterministic admission; Direct makes one public-action decision per
step. Their model-call patterns are therefore recorded separately, not treated
as equalized computation. Gemini thinking tokens, when returned, are recorded
separately from candidate/output tokens. No formal benchmark has run under this
configuration.

## Prompt Contract

Every LLM-driven condition requires a versioned prompt/configuration. Freeze
prompt text, version, and canonical content hash before execution. Store prompt
text separately from public result records and retain only the hash in the
manifest/result envelope. Architecture-specific instructions are permitted;
task-specific solution hints, hidden demonstrations, extra context, and
post-result prompt tuning are prohibited.

## Tool and Environment Contract

Reuse compatible M14 `EvaluationAction`, `EvaluationFeedback`,
`EvaluationBudget`, deterministic environment, and evaluator-owned judge.
Freeze a versioned manifest for tool names/schemas, simulated public behavior,
environment state, fault schedule, and feedback mapping. Provider adapters may
translate native tool-call format only at the boundary; no agent may own or
alter benchmark truth or alter common tool semantics.

## Resource Budget Contract

Freeze common hard limits for external actions, tool calls, wall-clock time, and
retry behavior. Identical LLM call/token limits are not automatically fair:
MIND-Lite's model role is interpretation/admission only, while other conditions
may make model calls during execution. Model calls, tokens, estimated cost, and
latency are transparent architecture-level resource observations, not perfectly
normalized computational effort. Apply any outage/rate-limit invalid-run rule
uniformly to all baselines.

## Completion Judge

Success is evaluator-owned. Prefer deterministic exact or state-based judging.
Agents may request termination but may not define benchmark success. Semantic or
LLM judging is allowed only after a separate judge-validity review; it must be
versioned, blinded to baseline, and reported separately from deterministic
primary judging.

The execution-side completion semantics version is `m16_completion_v2`.
The environment executes only an explicit Agent calculator request; the judge
does not execute, select, repair, or synthesize an action. No private truth is
returned to either Agent. The earlier development execution-manifest identity
is superseded before formal execution.

## Metrics

The primary Cohort A metric is:

`success_rate = successful completed cases / all eligible formal cases`

The denominator includes ordinary failures, invalid execution, timeouts, and
budget exhaustion. Exclude a run only under the narrow Invalid Run Policy.
Record secondary metrics separately where measurable: agent steps, tool calls,
model calls, input/output tokens, estimated cost, latency, recovery success,
invalid actions, timeout, budget exhaustion, and normalized failure category.
No composite quality score is permitted; every rate reports numerator and
denominator.

## Repetition Policy

For deterministic configurations, run one formal execution and deterministic
replay verification. For stochastic LLM configurations, run five formal
repetitions per task/baseline/configuration. Retain every repetition in the
formal artifact and never select a best run. Freeze task → baseline → repetition
order and construct fresh agent/environment instances per episode.

## Statistical Reporting

Report overall Cohort A success rate, rates by family and difficulty, absolute
counts and denominators, proportion confidence intervals, secondary resource
distributions, and failure-category counts. Use task-clustered summaries and
task-level bootstrap intervals where sample size permits. Inferential tests are
optional and require justified assumptions; do not use significance testing for
presentation alone. Cohort B receives descriptive boundary reporting only.

## Failure Taxonomy

Freeze evaluator-owned categories: success, incorrect_answer,
unsupported_capability, invalid_action, tool_failure, environment_failure,
provider_failure, admission_or_validation_failure,
meta_inference_nonselection, timeout, budget_exhaustion, and
explicit_agent_failure. Preserve only bounded public subcategories; never store
chain-of-thought, prompts, secrets, RuntimeState, Belief, Policy, credentials,
or provider payloads in result records.

## Invalid Run Policy

Agent-originated invalid action, timeout, failure, and budget exhaustion remain
benchmark outcomes. Only verified evaluator-infrastructure or provider outages
outside the agent execution contract may invalidate a run. Record the reason,
apply a deterministic rerun policy, and never discard a run because its agent
result is unfavorable.

## Reproducibility Manifest

Before execution, freeze and hash MIND tag/version; baseline commits; suite and
held-out split; prompts; provider/model settings; tools; environment; fault
manifest; budgets; judge; repetition count; metrics; taxonomy; and
result-record schema. Result envelopes must carry the applicable identifiers
and hashes plus compact public outcome/trace/resource data.

## Pre-Execution Freeze

No formal execution begins until the complete manifest is reviewed and frozen.
After execution begins, tasks, held-out split, prompts, model, tools,
environment semantics, budgets, judge, repetitions, and metrics may not change
in response to results. A genuine defect stops the run, documents the defect,
increments protocol/suite version, invalidates affected formal runs, and
restarts under the new freeze.

## Researcher Degrees of Freedom

Maintain a dated freeze manifest, predeclare exclusions and run order,
distinguish pilot from formal artifacts, publish all eligible and boundary
strata, and prohibit post-hoc task/prompt/budget/judge/metric changes.

## Claim Boundary

M16 may support claims about performance on frozen comparable Cohort A tasks,
observable robustness within tested conditions, public resource consumption, and
specific capability boundaries. It must not claim general intelligence,
universal agent or reasoning superiority, ReAct/Plan superiority from
non-comparable tasks, Full MIND performance, or broad generalization.

## Deferred Questions

Deferred questions include a production provider choice, direct action-provider
review, final task construction, operational difficulty definitions, final
held-out split, real-provider cost/accounting implementation, comparable
recovery policy, and any future fair ReAct/Plan-and-Execute evaluation.
