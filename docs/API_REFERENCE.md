# Public API Reference and Example Navigation

This reference describes the public, implemented MIND APIs for developers.
It is an orientation document, not a replacement for the SRS, SAS, or accepted
ADRs. Import values from their concrete modules under src.core and evaluation.
The APIs described here are bounded deterministic prototype interfaces; they do
not provide general intelligence, autonomous learning, or reasoning superiority.

## 1. Architecture Overview

The architecture preserves a separation between immutable runtime state and
task-level Agent execution:

    Observation
          |
          v
        Belief
          |
          v
     RuntimeState
          |
          v
  GoalDirectedAgent
          |
          v
      AgentResult

An Observation is incorporated into a new Belief and RuntimeState through the
runtime APIs. GoalDirectedAgent begins from a Task, uses the approved runtime
path, optionally selects a Meta-Inference strategy descriptor, applies
goal-aware decision data, and returns one terminal AgentResult.

The Agent does not place Task or Goal in RuntimeState as state fields, does not
retain a trajectory, and does not make the low-level RuntimeController a task
orchestration component.

## 2. Core Data Models

All public data models below are immutable value objects with to_dict() and
from_dict() serialization where applicable. Their nested structured data is
defensively copied or frozen by the implementation.

### Observation

Module: src.core.observation

Observation represents one immutable runtime input or externally produced event.
It has an id, timezone-aware timestamp, source, and structured content.
Inference consumes an Observation; it does not represent the complete user task.

### Belief

Module: src.core.belief

Belief is an immutable collection of BeliefRecord values plus confidence and a
version. It is the runtime's current information state. InferenceEngine.infer()
returns a new Belief rather than changing an existing one.

### RuntimeState

Module: src.core.runtime

RuntimeState is the immutable snapshot used by the runtime. Its fields remain
observation, belief, and metadata. It does not own Task, Goal, Policy,
AgentResult, a ToolRegistry, or execution history.

RuntimeController is stateless and exposes initialize(), update(),
apply_inference(), apply_decision(), run_cycle(), and run(). These APIs retain
the M1-M7 runtime boundary; the high-level Agent does not replace them.

### Goal

Module: src.core.task

Goal represents a desired outcome. It contains a required non-empty description,
an ordered non-empty sequence of success_criteria, and optional metadata. Goal
does not have a separate identity in the delivered M8 model.

### Task

Module: src.core.task

Task is the immutable user-level request. It owns exactly one Goal and has a
stable UUID id, structured input, optional context, constraints, and metadata.
Task input is distinct from an initial Observation created when Agent execution
begins.

The delivered direct-value and Calculator task schemas are documented in the
README. Unsupported schemas produce the bounded unsupported-task result.

### AgentResult

Module: src.core.result

AgentResult is the immutable terminal output of GoalDirectedAgent.run(). It
links to task_id and records status, answer where applicable, final_state,
termination_reason, cycles_completed, compact evidence, and metadata.

AgentStatus values are completed, failed, and incomplete. TerminationReason
distinguishes goal_satisfied, max_cycles_reached, unsupported_task,
tool_failure, and policy_failure. AgentResult is not an execution trajectory.

## 3. Agent Execution API

### GoalDirectedAgent

Module: src.core.agent

Constructor:

    GoalDirectedAgent(
        tool_registry: ToolRegistry,
        meta_inference_engine: MetaInferenceEngine | None = None,
    )

Execution:

    run(task: Task, max_cycles: int) -> AgentResult

ToolRegistry injection is required and instance-local. Register only the
controlled tools intended for that Agent, such as CalculatorTool. The Agent
uses a Tool only when deterministic GoalAwarePolicyEngine decision data requests
the supported action.

MetaInferenceEngine injection is optional. When present, the Agent asks it for
a MetaInferenceDecision before the existing task-policy flow. A non-selected
decision is preserved as explicit policy-failure semantics; the Agent does not
bypass the engine or execute a registered inference implementation.

GoalDirectedAgent is bounded by max_cycles. It returns a terminal immutable
AgentResult; it does not expose an open-ended background loop, scheduling,
memory, or autonomous retry behavior.

## 4. Meta-Inference API

### InferenceStrategy

Module: src.core.inference_strategy

InferenceStrategy is an immutable descriptor with name, description, ordered
capabilities, configuration, and metadata. It describes a controlled
capability; it is not an executable inference algorithm.

### InferenceStrategyRegistry

Module: src.core.inference_registry

InferenceStrategyRegistry is an explicit instance-local association between an
InferenceStrategy descriptor and an implementation satisfying the controlled
InferenceStrategyImplementation protocol.

Primary methods are:

    register(strategy, implementation) -> None
    get(name) -> InferenceStrategy
    get_implementation(name) -> InferenceStrategyImplementation
    contains(name) -> bool
    list_names() -> tuple[str, ...]

Registration order is preserved for listing. Duplicate exact names and unknown
lookups are rejected explicitly.

### MetaInferenceDecision

Module: src.core.meta_inference

MetaInferenceDecision is an immutable selection-only result. Its status is one
of selected, unavailable, or rejected; a selected result names exactly one
strategy and includes one or more immutable DecisionEvidence values.

Decision evidence explains the capability-match, unavailable-capability, or
ambiguity outcome using compact public data. It does not contain a runtime dump,
execution trajectory, or implementation object.

### MetaInferenceEngine

Module: src.core.meta_engine

Constructor:

    MetaInferenceEngine(registry: InferenceStrategyRegistry)

Selection:

    select(task: Task, runtime_state: RuntimeState) -> MetaInferenceDecision

The engine reads required_inference_capabilities from Task metadata and matches
them against registered descriptors:

    Task + RuntimeState
            |
            v
    MetaInferenceEngine.select()
            |
            v
    selected | unavailable | rejected decision

One matching descriptor is selected, no match is unavailable, and more than one
match is rejected. The engine does not execute strategies, mutate Task or
RuntimeState, modify RuntimeController, perform learning, or switch inference
implementations.

## 5. Evaluation API

The M10 evaluation layer remains separate from runtime and Agent architecture.
It uses immutable public Task and AgentResult-based values and retains compact
summaries only.

### EvaluationScenario

Module: evaluation.tasks.evaluation_task

EvaluationScenario owns an EvaluationTask, a stable scenario name and
description, expected behavior/outcome, and metadata. Frozen fixtures are
provided by:

    evaluation.tasks.fixtures.get_default_evaluation_scenarios()

The delivered fixture set has ten ordered local scenarios.

### EvaluationRunner

Module: evaluation.runner.evaluation_runner

Constructor:

    EvaluationRunner(
        baseline_a: GoalDirectedAgent,
        baseline_b: GoalDirectedAgent,
    )

Execution:

    run(
        scenario: EvaluationScenario,
        max_cycles: int,
    ) -> tuple[EvaluationRunResult, EvaluationRunResult]

The runner executes Baseline A then Baseline B and returns compact immutable
EvaluationRunResult values. It clones task data for each baseline run and does
not retain RuntimeState, Agent, Tool, strategy implementation, or trajectory.

### EvaluationMetrics

Module: evaluation.metrics.evaluation_metrics

EvaluationMetrics is an immutable aggregate derived by:

    calculate_metrics(results) -> EvaluationMetrics

It records total runs, success/failure counts and rates, strategy-selection,
unavailable, ambiguity-rejection, semantic-determinism, and
evidence-consistency measures. The metrics are protocol measures only; they are
not claims of intelligence, general reasoning quality, or superiority.

### M10 Evaluation Pipeline

    Frozen EvaluationScenario
            |
            v
    EvaluationRunner (A: M8 Agent; B: same Agent + Meta-Inference)
            |
            v
    EvaluationRunResult values
            |
            v
    EvaluationMetrics
            |
            v
    ComparativeExperimentResult and M10 report

The existing frozen-protocol function is
evaluation.results.comparative_experiments.execute_comparative_experiments().
It runs ten scenarios, three repetitions per baseline, and yields compact
ComparativeExperimentResult values.

## 6. Examples and Navigation

- [Runtime demonstration](../src/main.py): run python -m src.main.
- [Goal-Directed Agent demonstration](../examples/goal_directed_agent_demo.py):
  run python -m examples.goal_directed_agent_demo; it demonstrates 17 * 23 = 391.
- [Runtime benchmark](../benchmark/runtime_benchmark.py): run
  python -m benchmark.runtime_benchmark. It is an engineering benchmark, not a
  quality or intelligence benchmark.
- [Frozen M10 fixtures](../evaluation/tasks/fixtures.py) and
  [comparative execution](../evaluation/results/comparative_experiments.py):
  use the evaluation workflow in [REPRODUCIBILITY.md](REPRODUCIBILITY.md).
- [M10 Comparative Evaluation Report](evaluation/M10-Comparative-Evaluation-Report.md):
  read the observed protocol outcomes and limitations.
- [SRS](srs/SRS-MIND-Lite-v1.0.md),
  [SAS](architecture/Software-Architecture-Specification-v1.0.md), and
  [accepted ADRs](architecture/adr/): consult these for authoritative
  requirements, architecture decisions, and constraints.

## 7. Scope Boundaries

Only implemented interfaces are listed here. The repository does not expose
LLM integration, network access, browser/search/API/shell/file tools, online
learning, adaptive strategy execution, general planning, multi-agent execution,
or claims of general AI capability. Extend the artifact only through a new
approved specification and architecture review.
