# M14 Evaluation Protocol

## Status and phase boundary

M14 has two separate stages. Their evidence, claims, prerequisites, and outputs
must not be combined.

## Stage A — Evaluation Foundation Validation — Completed

Stage A validates evaluation infrastructure for the delivered deterministic MIND
Agent:

- public evaluation contracts;
- controlled task-action-feedback execution;
- deterministic environment and declared failure injection;
- evaluation-only Agent adapter;
- fixture registration, result-artifact schema, and deterministic replay;
- CompletionJudge, public traces, resource counters, and metric aggregation.

Stage A may run only local deterministic fixtures through the MIND adapter and
a deterministic public control. It validates that the evaluation foundation
measures the intended public behavior consistently.

Stage A does **not** measure or claim:

- intelligence;
- reasoning ability or superiority;
- Agent superiority;
- benchmark performance;
- task-capability improvement;
- external-agent comparison;
- LLM-provider performance.

The completed controlled evaluation foundation validates infrastructure only.
It did not execute a benchmark evaluation or draw agent-quality conclusions.

## Stage B — Agent Quality Benchmark Evaluation — Not Executed

Stage B is deferred future work. MIND-Lite v1.0 architecture closure and the
completed M15 LLM-enabled runtime path do not constitute Agent Quality
Benchmark execution.

A Stage B comparison requires:

- comparable baseline agents;
- the same frozen task suite and completion rules;
- the same provider, exact model revision, tools, budgets, retries, and
  resource-accounting rules;
- explicit reproducibility metadata and result storage; and
- an approved benchmark and statistical-analysis protocol.

Until those conditions are met, ReAct, Plan-and-Execute, direct external LLM
agents, and other external baselines remain out of scope.

## Reproducibility boundary

Any Stage A artifact must include only public fixture, environment, execution,
and outcome data. It must exclude chain-of-thought, hidden reasoning, prompts,
credentials, RuntimeState, Belief, Policy, Agent objects, and provider payloads.
A deterministic replay mismatch is a validation failure, not a result to
average.

## Future transition

Completion of Stage A establishes evaluation readiness only. It does not
authorize Stage B, change Agent architecture, or establish a quality benchmark.
