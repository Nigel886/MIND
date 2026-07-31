# MIND

## Cognitive Runtime, Goal-Directed Agent, and Meta-Inference Evaluation

MIND is a specification-driven research prototype for an inference-centric
agent architecture. M1-M10 are complete: the repository contains a validated
bounded Goal-Directed Agent, a deterministic Meta-Inference selection layer,
and a frozen local comparative-evaluation artifact.

## Status

- Completed: M1–M10, including the Cognitive Runtime Foundation,
  Goal-Directed Agent, deterministic Meta-Inference layer, and local
  comparative-evaluation artifact.
- Current: M11 — Framework Consolidation and Research Artifact Finalization.
- The current implementation is not a general-purpose Agent or a claim of
  reasoning superiority.

The completed M1-M10 scope includes the Cognitive Runtime Foundation, the
Goal-Directed Agent, deterministic Meta-Inference selection, and a frozen local
comparative-evaluation artifact. M11 is the current consolidation milestone.

## Quick start

Requires Python 3.11 or later.

```bash
python -m unittest
python -m src.main
python -m examples.goal_directed_agent_demo
python -m benchmark.runtime_benchmark
```

`python -m src.main` demonstrates the bounded M7 Cognitive Runtime Foundation
and prints a serialized `RuntimeState`. `python -m
examples.goal_directed_agent_demo` demonstrates bounded M8 task execution and
prints a serialized `AgentResult` for `17 * 23 = 391`.

The runtime benchmark is a machine-local engineering measurement of the M7
runtime. It is not an Agent-quality or reasoning-quality benchmark. The frozen
M10 evaluation artifact is documented in
[M10-Comparative-Evaluation-Report.md](docs/evaluation/M10-Comparative-Evaluation-Report.md).

## M8 Goal-Directed Agent

M8 separates user-level task execution from the low-level immutable runtime.

```text
Task + Goal
  -> GoalAwarePolicyEngine
  -> produce_answer | call_tool | fail_task
  -> optional ToolRegistry / CalculatorTool
  -> ToolResult -> Observation -> RuntimeController.apply_inference()
  -> CompletionEvaluator
  -> AgentResult
```

### Public M8 components

- `Goal` and `Task`: immutable, serializable value models. A `Task` owns one
  `Goal`, has a stable UUID, and remains outside `RuntimeState`.
- `AgentResult`, `CompletionDecision`, `AgentStatus`, and
  `TerminationReason`: immutable task-level completion and failure values.
- `CompletionEvaluator`: stateless deterministic comparison against the
  structured `expected_answer` task input.
- `Tool`, `ToolResult`, and `ToolRegistry`: controlled, explicit local Tool
  boundary. There is no default/global registry.
- `CalculatorTool`: deterministic addition or multiplication for exactly two
  finite non-boolean integer or float operands.
- `GoalAwarePolicyEngine`: deterministic task-schema routing; it only creates
  decision data and never executes a Tool.
- `GoalDirectedAgent`: bounded, behaviorally stateless task orchestrator that
  returns an `AgentResult`; it does not store a trajectory.

### Supported task schemas

Direct value task:

```python
Task(
    goal=Goal("return the value", ("candidate equals expected answer",)),
    input={"value": "ready", "expected_answer": "ready"},
)
```

Calculator task:

```python
Task(
    goal=Goal("calculate the product", ("candidate equals expected answer",)),
    input={
        "operation": "multiply",
        "operands": [17, 23],
        "expected_answer": 391,
    },
)
```

The supported actions are task-level decision identifiers only:
`produce_answer`, `call_tool`, and `fail_task`. Completion remains the
responsibility of `CompletionEvaluator`, not Policy generation.

### Outcomes and boundaries

- Matching direct and Calculator tasks produce `completed` /
  `goal_satisfied` results.
- An unsupported structured task produces `failed` /
  `unsupported_task`.
- A controlled Tool failure produces `failed` / `tool_failure`.
- A direct mismatch returns immediately as `incomplete` /
  `max_cycles_reached`; an unsatisfied Tool task remains bounded by
  `max_cycles`.
- RuntimeState remains an immutable snapshot of only observation, belief, and
  metadata. It is not a Task, Goal, final answer, AgentResult, or trajectory.

## Runtime foundation

The retained M7 runtime flow is:

```text
Observation -> InferenceEngine -> Belief -> PolicyEngine -> ActionExecutor
-> Observation -> new RuntimeState
```

`RuntimeController` remains stateless and exposes `initialize()`, `update()`,
`apply_inference()`, `apply_decision()`, `run_cycle()`, and `run()`. The M8
Agent uses only the approved lower-level initialization and inference path, so
the prototype Policy/Action path remains independent of task orchestration.

## M9 Meta-Inference and M10 evaluation

M9 adds immutable `InferenceStrategy`, `MetaInferenceDecision`, and
`DecisionEvidence` values; an explicit `InferenceStrategyRegistry`; and a
state-free `MetaInferenceEngine`. `GoalDirectedAgent` optionally consumes one
selection decision before its existing task-policy flow. The engine selects only
from explicit capability requirements: one match is selected, no match is
unavailable, and multiple matches are rejected. It does not execute registered
strategy implementations.

M10 adds frozen deterministic scenarios, an evaluation runner, compact result
storage, and pure metrics. The completed protocol compares the M8-style Agent
with the same Agent plus explicit Meta-Inference injection over local,
handcrafted scenarios. It reports observable protocol outcomes only, not
intelligence, reasoning quality, generalization, or superiority.

## Current capabilities and limitations

The system validates immutable state transitions, deterministic inference,
controlled local calculation, explicit task outcomes, and bounded deterministic
task execution. It does not provide arbitrary natural-language understanding,
general planning, unrestricted Tool use, network/browser/search/API/shell/file
access, LLM integration, memory, adaptive strategy execution, online learning,
or multi-agent behavior. The completed M10 evaluation does not establish
general-purpose Agent intelligence or comparative superiority.

## Repository structure

```text
src/core/       immutable models, runtime, policy, tools, Agent, Meta-Inference
src/tools/      controlled concrete local Tools
evaluation/     frozen scenarios, runner, metrics, and compact experiment results
examples/       finite public-API demonstrations
tests/          unit, integration, and end-to-end validation
benchmark/      M7 runtime engineering benchmark
docs/           SRS, SAS, ADRs, RFCs, and development guidance
```

## Architecture roadmap

M1-M10 are complete. M11 consolidates documentation, reproducibility, public
API navigation, and research-artifact readiness; it does not add new cognitive
capabilities.

See [ROADMAP.md](ROADMAP.md), the
[SRS](docs/srs/SRS-MIND-Lite-v1.0.md), the
[SAS](docs/architecture/Software-Architecture-Specification-v1.0.md), and
accepted ADRs under `docs/architecture/adr/` for the authoritative contracts.
