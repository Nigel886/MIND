# MIND

## Cognitive Runtime Foundation and Goal-Directed Agent

MIND is a specification-driven research prototype for an inference-centric
agent architecture. M8 is complete: the repository now contains a validated,
bounded Goal-Directed Agent for narrow deterministic structured tasks.

## Status

- Completed: M1–M8, including the Cognitive Runtime Foundation and the
  Goal-Directed Agent.
- Next: M9 — Meta-Inference Layer (planned, not started).
- The current implementation is not a general-purpose Agent or a claim of
  reasoning superiority.

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
runtime. It is not an Agent-quality, reasoning-quality, or comparative
evaluation benchmark; comparative evaluation belongs to M10.

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

## Current capabilities and limitations

The system validates immutable state transitions, deterministic inference,
controlled local calculation, explicit task outcomes, and bounded deterministic
task execution. It does not provide arbitrary natural-language understanding,
general planning, unrestricted Tool use, network/browser/search/API/shell/file
access, LLM integration, memory, Meta-Inference, multi-agent behavior, or a
comparative baseline. M8 therefore does not establish general-purpose Agent
intelligence.

## Repository structure

```text
src/core/       immutable models, runtime, policy, tools, completion, Agent
src/tools/      controlled concrete local Tools
examples/       finite public-API demonstrations
tests/          unit, integration, and end-to-end validation
benchmark/      M7 runtime engineering benchmark
docs/           SRS, SAS, ADRs, RFCs, and development guidance
```

## Architecture roadmap

M8 is complete. M9 will add Meta-Inference architecture; M10 will conduct
comparative evaluation; M11 will consolidate documentation and release
materials. These future milestones are not implemented by the current code.

See [ROADMAP.md](ROADMAP.md), the
[SRS](docs/srs/SRS-MIND-Lite-v1.0.md), the
[SAS](docs/architecture/Software-Architecture-Specification-v1.0.md), and
accepted ADRs under `docs/architecture/adr/` for the authoritative contracts.
