# MIND

## MIND-Lite v1.0 Bounded Cognitive-Agent Prototype

MIND-Lite v1.0 is a specification-driven research prototype for an
inference-centric cognitive-agent architecture. It combines immutable
Observation, Belief, and RuntimeState models; deterministic inference and
goal-aware Policy boundaries; bounded GoalDirectedAgent compatibility;
deterministic Meta-Inference; and controlled LLM-assisted session admission.

## Status

- Completed: M1–M15, including the immutable runtime foundation, bounded
  GoalDirectedAgent compatibility path, deterministic Meta-Inference, M13
  provider-neutral interpretation and validation, M14 evaluation foundation,
  and the M15 observation-aware cognitive session runtime.
- M14 Phase 2 Agent Quality Benchmark Evaluation has not been executed.
- The implementation is not a general-purpose Agent and makes no intelligence,
  reasoning-superiority, benchmark-superiority, or real-provider-performance
  claim.

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
Execution steps and reproducibility boundaries are in
[REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md). A developer-oriented component
map is available in [API_REFERENCE.md](docs/API_REFERENCE.md).

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

## M13/M15 LLM-assisted cognitive session

M13 treats LLM output as untrusted structured interpretation only:

```text
Task -> LLMProvider -> TaskInterpreter -> deterministic validation
     -> MetaInferenceAdapter -> IntegrationSelected
```

M15 admits that selected context into a bounded `CognitiveAgentSession` through
an optional keyword-only `admission_resolver`. The session first creates its
canonical private initial RuntimeState, invokes the resolver exactly once, and
admits only `IntegrationSelected`. Provider, interpreter, validation, and
integration failures produce a bounded public `failed` session result without
leaking private state or provider data.

```text
Session.step() -> CognitiveActionRequest -> external tool/environment
               -> Observation(source="agent_environment")
               -> Session.observe() -> RuntimeController.apply_inference()
               -> next policy request or explicit termination
```

`CognitiveExecutionLoopController` is an internal session implementation
component, not a supported public API. It applies accepted feedback through the
canonical immutable RuntimeController path, classifies completion/failure, and
uses the existing GoalAwarePolicyEngine. Neither the session nor the controller
executes tools, calls providers, or exposes RuntimeState, Belief, Policy, or
chain-of-thought.

## Current capabilities and limitations

The system validates immutable state transitions, deterministic inference,
controlled local calculation, explicit task outcomes, bounded deterministic
task execution, and a FakeLLMProvider-validated interpretation/admission path.
It does not provide real-provider performance validation, arbitrary
natural-language task solving, open-domain planning, unrestricted Tool use,
network/browser/search/API/shell/file access, long-term memory, dynamic strategy
switching, online learning, or multi-agent behavior. M10/M14 do not establish
general-purpose Agent intelligence or comparative superiority.

## Repository structure

```text
src/core/       immutable models, runtime, policy, tools, Agent, Meta-Inference, Session
src/integration/ provider-neutral LLM interpretation, validation admission, and adapter boundary
src/tools/      controlled concrete local Tools
evaluation/     frozen scenarios, runner, metrics, and compact experiment results
examples/       finite public-API demonstrations
tests/          unit, integration, and end-to-end validation
benchmark/      M7 runtime engineering benchmark
docs/           SRS, SAS, ADRs, RFCs, and development guidance
```

## Architecture roadmap

MIND-Lite v1.0 architecture closure is complete. Future work remains separate
Full MIND research, including M14 Phase 2 Agent Quality Benchmark Evaluation.

See [ROADMAP.md](ROADMAP.md), the
[SRS](docs/srs/SRS-MIND-Lite-v1.0.md), the
[SAS](docs/architecture/Software-Architecture-Specification-v1.0.md), and
accepted ADRs under `docs/architecture/adr/` for the authoritative contracts.
