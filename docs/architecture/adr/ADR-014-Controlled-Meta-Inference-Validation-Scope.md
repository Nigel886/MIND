# ADR-014 - Controlled Meta-Inference Validation Scope

**Status:** Proposed

## Context

MIND v0.5.0 delivers a bounded GoalDirectedAgent, deterministic
Meta-Inference strategy selection, compact decision evidence, and a frozen local
comparative-evaluation framework.

The delivered MetaInferenceEngine accepts Task and RuntimeState, reads explicit
required capabilities, and returns a MetaInferenceDecision. It selects one
matching strategy descriptor, returns unavailable when no descriptor matches,
and returns rejected when multiple descriptors match. GoalDirectedAgent records
the decision and continues the existing M8 policy/tool/completion path only
when a decision is selected.

The selected registry implementation is not invoked. Meta-Inference currently
does not modify Policy generation, Tool selection, inference execution, task
solving, answer generation, or the runtime path. Therefore a controlled
evaluation must not represent selection as a causal task-performance
improvement.

M12 requires a research scope that validates delivered behavior without
introducing LLMs, external services, strategy-execution changes, or an
unapproved architecture extension.

## Decision

M12 is named **Controlled Meta-Inference Validation**.

M12 validates only the correctness, determinism, reliability, and auditability
of the delivered selection-only Meta-Inference layer under frozen local
conditions.

The frozen research questions are:

1. Can MIND deterministically select, mark unavailable, or reject ambiguous
   strategies from explicit Task capability requirements?
2. Can MIND produce deterministic and consistent compact decision evidence?
3. Does optional Meta-Inference preserve existing M8 GoalDirectedAgent task and
   failure semantics when selection succeeds or is omitted?
4. How do explicit Meta-Inference selection semantics compare with a separately
   specified deterministic fixed-strategy baseline under equal inputs, tools,
   budgets, descriptors, and result schemas?

M12 may use only local deterministic execution, controlled Tasks, explicit
capabilities, local tools, and the existing Agent framework.

M12 excludes LLMs, external APIs, network access, external benchmarks,
autonomous learning, strategy execution changes, multi-step planning,
open-domain reasoning, multi-tool optimization, WebArena/AgentBench-style
benchmarks, and any task-success-improvement claim.

Baseline definitions are:

- **Baseline A:** M8 GoalDirectedAgent with no MetaInferenceEngine.
- **Baseline B:** a deterministic fixed-strategy selection baseline whose exact
  mapping and unavailable/ambiguity behavior are frozen before implementation.
- **Baseline C:** GoalDirectedAgent with MetaInferenceEngine and an explicit
  InferenceStrategyRegistry.

All baseline comparisons must use equivalent serialized Tasks, ToolRegistry
configuration, capability vocabulary, registered descriptors where applicable,
cycle budget, environment, and public result schema.

M12 metrics are limited to selection accuracy, unavailable correctness,
ambiguity rejection correctness, semantic determinism, evidence consistency,
and M8 behavior preservation. Evidence completeness is an auditability metric;
it is not evidence-aware execution.

For M12, the valid contrasts are Full MIND, the fixed-strategy baseline, and an
evidence-recording audit condition. Removing the Goal-directed Agent or
CompletionEvaluator is invalid because it changes task semantics. Removing the
registry is invalid because MetaInferenceEngine requires it; Baseline B replaces
that contrast with a specified static selector.

## Consequences

M12 can make bounded claims about selection correctness, explicit failure
semantics, compact evidence consistency, reproducibility, and M8 compatibility.

M12 cannot claim that Meta-Inference improves task success, reasoning,
intelligence, controllability, general capability, or benchmark superiority.
Repeated deterministic executions establish semantic reproducibility; they are
not independent statistical samples.

A future causal task-performance study requires a separate accepted
architecture decision that specifies how a selected strategy has an observable,
fairness-preserving effect on execution. Such an extension must not be included
in M12 evaluation implementation.

## Alternatives Considered

### A. Evaluate task-success improvement with current Meta-Inference

Rejected. Selected strategies are not executed and do not alter current task
execution, so this would create an unsupported causal claim.

### B. Add LLMs or external benchmarks to M12

Rejected. This would confound delivered architecture semantics with external
models, services, and nondeterministic variables. LLM integration is separate
future work.

### C. Validate only the released selection semantics

Accepted. This isolates the existing deterministic contribution and preserves
the v0.5.0 architecture boundary.

## Compatibility

This decision introduces no production API, model, Tool, runtime, Agent,
inference, policy, evaluation-methodology, or M10 artifact change. M12
evaluation implementation, fixtures, and tests require separate approval.

## Deferred Decisions

- The exact fixed-strategy mapping for Baseline B.
- The versioned M12 fixture schema, coverage counts, and evidence-completeness
  rubric.
- Any selected-strategy execution contract.
- LLM, external benchmark, multi-tool, planning, and multi-step evaluation.
