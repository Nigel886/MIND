# M12 Controlled Meta-Inference Validation Protocol

## 1. Motivation

M12 validates the delivered, selection-only Meta-Inference layer under
controlled deterministic conditions. The layer maps an explicit `Task`
capability requirement to a `MetaInferenceDecision`; it does not execute a
selected strategy, modify a Policy, alter execution planning, or directly
improve task-solving capability.

Accordingly, this protocol evaluates explicit decision semantics,
auditability, determinism, and preservation of the existing M8 Agent behavior.
It does not test or claim task-success improvement caused by Meta-Inference.

## 2. Research Questions

| ID | Research question | Frozen metrics |
| --- | --- | --- |
| RQ1 | Can Meta-Inference correctly select a strategy from explicit Task capability requirements? | strategy selection correctness |
| RQ2 | Can Meta-Inference correctly represent unavailable and ambiguous capability situations? | unavailable correctness; ambiguity rejection correctness |
| RQ3 | Can Meta-Inference produce deterministic, complete, and semantically consistent compact evidence? | evidence completeness; evidence consistency; semantic repeatability |
| RQ4 | Does optional Meta-Inference preserve existing `GoalDirectedAgent` behavior? | execution outcome preservation; failure-semantic preservation; deterministic execution |

## 3. Baselines

All baselines use equivalent serialized Tasks, local `ToolRegistry`
configuration, capability vocabulary, registered descriptors where applicable,
cycle budget, environment, and public result schema.

### Baseline A — M8 GoalDirectedAgent

`GoalDirectedAgent(tool_registry)` provides the delivered M8 behavior without a
`MetaInferenceEngine`. It is the reference for RQ4 preservation checks.

### Baseline B — Fixed Strategy Selection

A separately specified deterministic static selector provides a frozen mapping
from explicit capability requirements to the same decision categories:
`SELECTED`, `UNAVAILABLE`, or `REJECTED`. Its exact mapping must be versioned
before the validation harness is implemented. This baseline is limited to
decision-semantics comparison; it must not be interpreted as an independent
Agent or task-solving baseline.

### Baseline C — Full MIND Meta-Inference Agent

`GoalDirectedAgent(tool_registry, meta_inference_engine)` uses the delivered
`MetaInferenceEngine` and an explicit `InferenceStrategyRegistry`. A selected
decision permits the existing M8 policy, tool, and completion path to continue;
the selected strategy implementation is never executed.

## 4. Frozen Scenario Categories

| Category | Required setup | Expected semantic result |
| --- | --- | --- |
| Unique capability match | Exactly one descriptor matches the Task requirement. | `SELECTED` with that descriptor. |
| Unavailable capability | No registered descriptor matches. | `UNAVAILABLE`. |
| Ambiguous capability match | More than one descriptor matches. | `REJECTED`. |
| Evidence consistency | Repeat a fixed decision scenario with identical serialized input. | Equivalent compact evidence after excluding nondeterministic identity and timing data. |
| M8 compatibility | Direct, Calculator, unsupported-task, and controlled-failure Tasks. | The specified M8 outcome and failure semantics are preserved when the comparison is applicable. |

Scenario fixtures must be deterministic, immutable, versioned, local, and
reproducible. Fixture creation belongs to Issue #48 and is not part of this
protocol-definition issue.

## 5. Metrics and Interpretation

Each decision metric is calculated only over fixtures for which that decision
category is the expected outcome:

- **Strategy selection correctness:** proportion of unique-match fixtures whose
  decision is `SELECTED` with the expected strategy identifier.
- **Unavailable correctness:** proportion of unavailable fixtures whose
  decision is `UNAVAILABLE`.
- **Ambiguity rejection correctness:** proportion of ambiguous fixtures whose
  decision is `REJECTED`.
- **Evidence completeness:** proportion of decisions whose compact evidence
  contains the frozen, scenario-relevant explanation fields. It does not
  measure evidence-aware execution.
- **Evidence consistency:** proportion of repeated, equivalent decision inputs
  with equivalent compact evidence semantics.
- **Semantic repeatability:** proportion of repeated runs with equivalent
  decision status, selected strategy (when present), and evidence semantics.
- **Execution outcome preservation:** proportion of applicable M8 compatibility
  comparisons with equivalent public `AgentResult` outcome semantics.
- **Failure-semantic preservation:** proportion of applicable failure cases
  whose public failure status and termination reason match the frozen M8
  expectation.

UUIDs, timestamps, and descriptive elapsed duration are excluded from semantic
equivalence. Repeated deterministic runs demonstrate reproducibility, not
independent statistical samples.

## 6. Experimental Constraints and Reproducibility

M12 execution is constrained to:

- deterministic local execution;
- no network access during evaluation;
- no LLMs;
- no external datasets or benchmarks;
- a recorded fixed environment and implementation revision;
- frozen fixture and baseline versions;
- repeated execution using the same serialized inputs and budgets; and
- compact validation records only, with no RuntimeState dump, Agent object,
  Tool object, strategy implementation, or full execution trajectory retained.

## 7. Causal and Research Limitations

M12 may state that the delivered layer provides deterministic and explicit
strategy-selection semantics, decision transparency, controllability, and M8
behavior preservation within this protocol.

M12 must not claim intelligence improvement, reasoning improvement, general
capability, human preference, task-success improvement, benchmark superiority,
autonomous learning, or selected-strategy execution. Any future study of
task-performance effects requires an accepted architecture decision defining a
fair observable execution effect for selected strategies.
