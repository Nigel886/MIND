# Software-Architecture-Specification-v1.0

Project: **MIND-Lite**

Version: **v1.0**

Status: **Architecture Frozen; maintained through completed M10**

---

# 1. Purpose

This document defines the software architecture of the MIND-Lite prototype.

Unlike the Software Requirements Specification (SRS), which defines **what** the system must do, this document defines **how** the system is organized and implemented.

The Software Architecture Specification (SAS) serves as the primary development blueprint for the MIND-Lite prototype.

All implementation decisions should follow this document unless explicitly overridden by a higher-priority specification.

---

# 2. Relationship to Other Documents

The project documentation follows the hierarchy below.

| Priority | Document                                 | Purpose                                            |
| -------- | ---------------------------------------- | -------------------------------------------------- |
| 1        | RFC-000 ~ RFC-003                        | Research theory and formal definitions             |
| 2        | SRS-MIND-Lite-v1.0                       | Functional and non-functional requirements         |
| 3        | Software-Architecture-Specification-v1.0 | Software architecture and implementation blueprint |
| 4        | README                                   | Project overview                                   |

If multiple documents appear to conflict, the document with the higher priority shall take precedence.

---

# 3. Architecture Principles

The MIND-Lite architecture follows the principles below.

## AP-1 Single Responsibility

Each module shall own exactly one primary responsibility.

Business logic shall not be duplicated across modules.

---

## AP-2 Explicit Runtime State

Runtime state shall always be represented explicitly.

Hidden state inside prompts or global variables is prohibited.

---

## AP-3 Interface-Oriented Design

Modules communicate through clearly defined interfaces.

Implementation details must remain encapsulated.

---

## AP-4 Loose Coupling

Modules should depend only on stable interfaces.

Circular dependencies are prohibited.

---

## AP-5 High Cohesion

Responsibilities that naturally belong together shall remain within the same module.

A module should expose only the functionality required by other modules.

---

## AP-6 Extensibility

Future runtime capabilities should be introduced through extension instead of modification whenever practical.

---

## AP-7 Research-Driven Development

Architectural correctness takes priority over implementation convenience.

The purpose of MIND-Lite is to validate the proposed runtime abstraction rather than maximize functionality.

---

# 4. Repository Structure

The repository shall follow the structure below.

```text
MIND/
│
├── docs/
│   ├── architecture/
│   ├── development/
│   ├── math/
│   ├── references/
│   ├── rfc/
│   └── srs/
│
├── src/
│   ├── core/
│   ├── memory/
│   ├── operators/
│   ├── tools/
│   ├── utils/
│   └── main.py
│
├── tests/
├── experiments/
├── benchmark/
├── paper/
├── scripts/
├── configs/
│
├── README.md
├── ROADMAP.md
├── CONTRIBUTING.md
├── LICENSE
└── CITATION.cff
```

Each top-level directory has a dedicated responsibility.

No business logic shall be implemented outside the `src/` directory.

---

# 5. Runtime Architecture

The MIND-Lite runtime is organized around composable, stateless coordination
operations. The complete conceptual lifecycle is shown below; M6 Issue #16
implements one decision-integration transition and does not introduce a
continuous runtime loop.

```text
                Environment
                    │
                    ▼
                Observation
                    │
                    ▼
                InferenceEngine
                    │
                    ▼
                Belief
                    │
                    ▼
                RuntimeController
                    │
                    ▼
                RuntimeState
                    │
                    ▼
                PolicyEngine
                    │
                    ▼
                ActionExecutor
                    │
                    ▼
                Environment
```

The complete lifecycle observes the environment, updates internal beliefs,
derives a policy, and executes an action. In the current prototype,
RuntimeController is the sole orchestration owner: it coordinates individual
operations without owning a loop, scheduler, or persistent state.

---

# 6. Module Dependency

This section defines the dependency relationships between runtime modules.

The dependency graph is considered part of the architecture and shall remain stable throughout Version 1.0.

---

## 6.1 Dependency Graph

```text
RuntimeController
        │
        ├────────► RuntimeState
        │
        ├────────► InferenceEngine
        │
        ├────────► PolicyEngine
        │
        └────────► ActionExecutor

InferenceEngine ─────► Belief

RuntimeState ───────► Observation
RuntimeState ───────► Belief

ActionExecutor ─────► Policy
ActionExecutor ─────► Observation
```

---

## 6.2 Allowed Dependencies

| Module         | Allowed Dependencies                           |
| -------------- | ---------------------------------------------- |
| runtime.py     | observation, belief, inference, policy, action |
| observation.py | None                                           |
| belief.py      | None                                           |
| inference.py   | belief, operators                              |
| policy.py      | belief                                         |
| action.py      | policy, observation                            |
| operators      | None                                           |
| tools          | None                                           |
| memory         | None (reserved for future versions)            |

---

### Policy and Action Dependency Boundary

`policy.py` may depend only on `belief.py`. PolicyEngine consumes Belief and
produces Policy; it does not depend on RuntimeController, ActionExecutor, tools,
Observation, inference, or memory.

`action.py` consumes Policy when action execution is introduced. Policy never
depends on ActionExecutor and never performs execution.

RuntimeController integration of PolicyEngine is deferred to M6.

---

### ActionExecutor Prototype Boundary

`action.py` may depend only on `policy.py` and `observation.py` for this
prototype. ActionExecutor consumes Policy and produces a new Observation; it
does not depend on Belief, RuntimeController, inference, tools, memory, or
external services.

The two approved actions are self-contained result-generation identifiers, so no
separate public Tool interface or example tool is required. Tool abstractions,
registries, discovery, and external integrations remain future extension points.

---

## 6.3 Forbidden Dependencies

The following dependencies are prohibited.

* Observation → Runtime
* Belief → Runtime
* Policy → Runtime
* Action → Runtime
* Belief → Policy
* Belief → Action
* Tool → Runtime
* Operator → Runtime

The RuntimeController is the only component responsible for runtime orchestration.

RuntimeState is a passive runtime data model and shall never perform orchestration.

---

# 7. Core Class Specification

This section freezes the core runtime classes.

No additional core runtime classes shall be introduced in Version 1.0.

---

## 7.1 Observation

### Responsibility

Represents information received from the external environment.

### Attributes

| Attribute | Type     | Description                   |
| --------- | -------- | ----------------------------- |
| id        | UUID     | Unique observation identifier |
| timestamp | datetime | Creation time                 |
| source    | str      | Observation source            |
| content   | Any      | Raw observation content       |

### Responsibilities

* Store external observations.
* Preserve immutability.
* Record metadata.

---

## 7.2 Belief

### Responsibility

Represents the runtime's explicit internal belief state.

### Attributes

| Attribute  | Type | Description           |
| ---------- | ---- | --------------------- |
| state      | dict | World representation  |
| confidence | dict | Confidence scores     |
| version    | int  | Belief version number |

### Responsibilities

* Maintain world state.
* Track uncertainty.
* Support updates.
* Support serialization.

---

## 7.3 InferenceEngine

### Responsibility

Derive a new immutable Belief from the current Observation and the previous Belief.

InferenceEngine is a stateless transformation component.

### Responsibilities

- Construct a new immutable Belief.
- Preserve the previous Belief.
- Execute the inference process.
- Encapsulate belief revision internally.

InferenceEngine SHALL NOT:

- modify RuntimeState;
- perform runtime orchestration;
- generate policies;
- execute actions.

---

## 7.4 Policy and PolicyEngine

### Policy Responsibility

Policy is an immutable decision object produced from the current Belief. It
describes the next action for a future ActionExecutor and never performs action
execution itself.

### Policy Attributes

| Attribute | Type | Description |
| --- | --- | --- |
| action | str | Selected action type. |
| parameters | dict[str, Any] | Data required by a future ActionExecutor. |
| metadata | dict[str, Any] | Non-execution decision information, such as source Belief version or an explanation. |

Policy SHALL NOT include UUIDs, timestamps, utilities, costs, information gain,
expected free energy, tool objects, hidden state, or execution methods.

### PolicyEngine Responsibility

PolicyEngine transforms a Belief into exactly one Policy through deterministic
prototype policy generation.

PolicyEngine is a stateless selection component. It consumes only Belief and
does not modify it.

### Responsibilities

* Select one prototype decision from the current Belief.
* Construct one immutable Policy.
* Preserve separation between decision generation and action execution.

Policy generation must remain deterministic given identical inputs.

PolicyEngine SHALL NOT perform Expected Free Energy optimization, Active
Inference policy selection, reinforcement learning, utility or cost optimization,
candidate-action registry lookup, action search, runtime orchestration, tool
invocation, Observation creation, or action execution.

---

## 7.5 ActionExecutor

### Responsibility

Executes one Policy and represents the result as a new immutable Observation.
ActionExecutor is a stateless execution component and is separate from Policy
generation.

### Responsibilities

* Consume one Policy.
* Produce one new Observation with `source="action_executor"`.
* Implement only deterministic `await_observation` and `maintain_belief`
  prototype semantics.

### Observation Result Structure

Successful execution returns an Observation whose content contains at least:

```python
{
    "action": policy.action,
    "status": "completed",
    "parameters": policy.parameters,
}
```

The Observation model assigns its own identifier and timestamp.

### Unsupported Actions

Unsupported Policy action identifiers raise `ValueError` explicitly in the
prototype. No ActionResult model is introduced.

### Design Rules

- ActionExecutor consumes Policy only and never generates Policy.
- ActionExecutor never accesses or modifies Belief, performs inference, or
  orchestrates RuntimeController.
- ActionExecutor never modifies its Policy input.
- ActionExecutor remains stateless across repeated calls.
- ActionExecutor performs no tool invocation, network access, shell execution,
  arbitrary Python execution, production API access, authentication, retries,
  scheduling, memory access, or multi-agent behavior.
- No Tool interface is required for these two self-contained prototype actions.

ActionExecutor must never modify beliefs directly.

---

## 7.6 Runtime Subsystem

### Architecture

The Runtime Subsystem consists of two components:

* RuntimeState
* RuntimeController

RuntimeState is an immutable passive runtime data model.

RuntimeController is responsible for coordinating RuntimeState and future runtime components.

---

### RuntimeState Responsibilities

* Store the current Observation.
* Store the current Belief.
* Store runtime metadata.
* Support serialization.
* Support deserialization.

RuntimeState SHALL NOT:

* perform inference;
* update beliefs;
* generate policies;
* execute actions;
* manage runtime scheduling.

---

### RuntimeController Responsibilities

RuntimeController is responsible for:

- initializing RuntimeState;
- updating RuntimeState;
- coordinating interactions between RuntimeState and future runtime components.

RuntimeController SHALL remain stateless.

RuntimeController currently provides stateless initialization, immutable update,
inference and decision coordination, one complete cycle, and finite bounded
execution through its documented public APIs.

---

# 8. Object Ownership

The Runtime Subsystem owns the RuntimeState and RuntimeController.

RuntimeState owns the current Observation and Belief.

RuntimeController coordinates runtime operations.

```text
RuntimeSubsystem
│
├── RuntimeState
│   ├── Observation
│   └── Belief
│
└── RuntimeController
```

Ownership relationships are fixed.

Components must communicate through Runtime rather than directly referencing one another whenever orchestration is required.

---

# 9. Public API Specification

This section defines the public interfaces exposed by each runtime component.

Only the interfaces defined in this section are considered public.

Internal helper methods are implementation details and may change without affecting the architecture.

---

# 9.1 Observation

## Public Interface

```python
class Observation:

    @classmethod
    def create(
        source: str,
        content: Any
    ) -> "Observation"

    def to_dict(self) -> dict
```

## Design Rules

* Observation objects are immutable.
* Observation IDs are generated automatically.
* Timestamps are assigned during creation.
* External modules cannot modify observation content after creation.

---

# 9.2 Belief

The `Belief` object represents the immutable runtime belief state.

A Belief object contains no inference logic.

Belief instances are created and evolved exclusively by the Inference Engine.

The Belief object is therefore a passive data model.

```python
class Belief:

    state: dict[str, BeliefRecord]

    confidence: dict[str, float]

    version: int

    def to_dict(self) -> dict:
        ...

    @classmethod
    def from_dict(cls, data: dict) -> "Belief":
        ...
```

The Inference Engine is responsible for constructing a new Belief instance whenever the belief state evolves.

Existing Belief instances shall never be modified.

---

# 9.3 InferenceEngine

## Public Interface

```python
class InferenceEngine:

    @staticmethod
    def infer(
        observation: Observation,
        belief: Belief,
    ) -> Belief:

```

### Design Rules

- InferenceEngine exposes only one public operation.
- infer() never modifies the original Belief.
- infer() always returns a new immutable Belief.
- Belief revision is an internal implementation detail.

---

# 9.4 Policy and PolicyEngine

## Public Interface

```python
@dataclass(frozen=True)
class Policy:
    action: str
    parameters: dict[str, Any]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        ...

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "Policy":
        ...


class PolicyEngine:

    @staticmethod
    def generate(
        belief: Belief
    ) -> Policy
```

## Design Rules

- Policy is immutable and contains decisions only.
- Policy exposes no `execute()` method.
- `Policy.to_dict()` and `Policy.from_dict()` preserve nested parameters and
  metadata.
- PolicyEngine exposes only `generate()` as its public operation.
- PolicyEngine consumes only Belief and returns exactly one Policy.
- PolicyEngine remains stateless and produces no external side effects.
- PolicyEngine never modifies Belief, invokes tools, creates Observations,
  executes actions, or performs runtime orchestration.
- RuntimeController coordinates PolicyEngine only through the M6
  `apply_decision()` orchestration operation; PolicyEngine itself remains
  independent of RuntimeController.

---

# 9.5 ActionExecutor

## Public Interface

```python
class ActionExecutor:

    @staticmethod
    def execute(
        policy: Policy
    ) -> Observation:
        ...
```

## Design Rules

* Every action execution returns a new Observation.
* Successful Observations use `source="action_executor"` and structured content
  containing `action`, `status`, and `parameters`.
* ActionExecutor exposes only `execute()` as its public operation.
* ActionExecutor remains stateless, consumes only Policy, and never updates
  Belief or RuntimeState.
* `await_observation` and `maintain_belief` are the only supported prototype
  action identifiers; unsupported identifiers raise `ValueError`.
* Policy describes execution; ActionExecutor performs execution. Policy itself
  never performs execution.
* Tool interfaces and external integrations are outside this issue's scope.

---

## 9.6 RuntimeState

### Public Interface

```python
class RuntimeState:

    observation: Observation

    belief: Belief

    metadata: dict[str, Any]

    def to_dict(self) -> dict:
        ...

    @classmethod
    def from_dict(cls, data: dict) -> "RuntimeState":
        ...
```

RuntimeState is an immutable passive data model.

It exposes only state representation and serialization interfaces.

Runtime lifecycle management belongs to RuntimeController.

---

## 9.7 RuntimeController

### Public Interface

```python
class RuntimeController:

    @staticmethod
    def initialize(
        observation: Observation | None = None,
        belief: Belief | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeState:
        ...

    @staticmethod
    def update(
        runtime_state: RuntimeState,
        observation: Observation | None = None,
        belief: Belief | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeState:
        ...

    @staticmethod
    def apply_inference(
        runtime_state: RuntimeState,
        observation: Observation,
    ) -> RuntimeState:
        ...

    @staticmethod
    def apply_decision(
        runtime_state: RuntimeState,
    ) -> RuntimeState:
        ...

    @staticmethod
    def run_cycle(
        runtime_state: RuntimeState,
        observation: Observation,
    ) -> RuntimeState:
        ...

    @staticmethod
    def run(
        runtime_state: RuntimeState,
        observation: Observation,
        max_cycles: int,
    ) -> RuntimeState:
        ...
```

### Design Rules

- RuntimeController shall remain stateless.
- RuntimeController shall never own RuntimeState internally.
- RuntimeController shall never mutate RuntimeState.
- RuntimeController shall not implement inference algorithms or belief-revision
  rules. It may coordinate inference by delegating belief transformation to
  InferenceEngine and incorporating the returned Belief into a new RuntimeState.
- RuntimeController shall not implement policy-generation logic or
  action-execution logic. It may orchestrate decision integration by delegating
  to PolicyEngine and ActionExecutor.
- `apply_decision()` shall obtain `runtime_state.belief`, call
  `PolicyEngine.generate()`, call `ActionExecutor.execute()`, and pass the
  returned Observation to `RuntimeController.update()`.
- `apply_decision()` shall preserve the current Belief and the existing
  `update()` metadata semantics, shall not persist Policy, and shall not add
  fields to RuntimeState.
- `apply_decision()` shall perform no inference, loop, tool execution, or error
  suppression. Unsupported-action `ValueError` propagates to the caller.
- `run_cycle()` shall compose exactly one call to `apply_inference()` followed
  by exactly one call to `apply_decision()`. It shall return the final state
  from `apply_decision()` without constructing RuntimeState itself.
- The inferred RuntimeState is an intermediate immutable value. The final state
  retains its inferred Belief and stores the action-result Observation, not the
  incoming inference Observation.
- `run_cycle()` shall not loop, accept cycle limits, evaluate termination,
  persist Policy, alter metadata semantics, invoke tools directly, introduce a
  Runtime class or dependency injection, or suppress component exceptions.
- `run()` shall validate that max_cycles is an int but not bool; invalid types
  raise TypeError and negative integers raise ValueError. Zero returns the exact
  input RuntimeState.
- `run()` shall use a finite iteration driven only by max_cycles and delegate
  only to `run_cycle()`. It shall pass the explicit Observation first, then pass
  each returned state's Observation to the following cycle.
- `run()` shall return only the final RuntimeState, retain no trajectory or
  local state after return, and shall not alter metadata semantics, retry,
  suppress exceptions, or evaluate semantic termination.

---

# 10. Runtime Sequence

The following is the implemented finite lifecycle. `run_cycle()` composes one
inference-decision-action transition; `run()` repeats it only up to explicit
`max_cycles`, using the previous action-result Observation as later input.

```text
Receive Observation

      ↓

InferenceEngine.infer()

      ↓

New Belief

      ↓

RuntimeController.update()

      ↓

RuntimeState

      ↓

PolicyEngine.generate()

      ↓

ActionExecutor.execute()

      ↓

Generate Observation

      ↓

New RuntimeState
```

`run_cycle()` first creates an inferred intermediate RuntimeState through
`apply_inference()`, then calls `apply_decision()` once. `run()` may compose a
finite explicit number of such cycles, chaining the preceding action-result
Observation as the next input; it does not introduce scheduling or an
unbounded loop, semantic termination, trajectory storage, retries, a separate
Runtime class, constructor dependency injection, or external Tool execution.

RuntimeState is a passive immutable internal snapshot of Observation, Belief,
and metadata. It is serializable for tracing, testing, reproducibility, and
future persistence; it is not a final answer, Task, Goal, AgentResult,
trajectory, Policy store, or Meta-Inference model. Policy is transient during
decision integration. The root `benchmark` package is a non-core development
utility that measures local runtime engineering behavior only.

---

# 11. Configuration Management

Configuration management is outside the current prototype scope. M6 Issue #16
introduces neither RuntimeConfig nor configuration ownership; future
configuration design requires an approved architecture decision.

---

# 12. Component Wiring and Dependency Injection

The current prototype has no separate Runtime class and does not use
constructor-based dependency injection. RuntimeController is the orchestration
owner and delegates statelessly through the established static public APIs of
InferenceEngine, PolicyEngine, and ActionExecutor.

Pluggable component instances and constructor-based dependency injection are
deferred to a future architecture revision approved by a separate ADR.

---

# 13. Error Handling Strategy

The runtime shall fail gracefully whenever possible.

Errors should be localized and must not propagate uncontrollably across runtime modules.

---

## 13.1 Error Categories

The prototype defines the following categories.

| Category           | Description                  |
| ------------------ | ---------------------------- |
| RuntimeError       | Runtime lifecycle failures   |
| ObservationError   | Invalid observations         |
| InferenceError     | Inference execution failures |
| BeliefError        | Invalid belief operations    |
| PolicyError        | Policy generation failures   |
| ActionError        | Action execution failures    |
| ConfigurationError | Invalid configuration        |

---

## 13.2 Error Handling Principles

Every runtime component shall:

* Raise meaningful exceptions.
* Never silently ignore errors.
* Preserve runtime consistency.
* Log sufficient debugging information.

---

## 13.3 Recovery Strategy

Version 1.0 adopts a simple recovery strategy.

Recoverable errors:

* Invalid observation
* Tool timeout
* Temporary inference failure

Fatal errors:

* Runtime initialization failure
* Invalid architecture configuration
* Component creation failure

---

# 14. Testing Strategy

Testing is a mandatory component of MIND-Lite.

Every public runtime module shall be covered by automated tests.

---

## 14.1 Test Structure

```text
tests/

├── test_observation.py
├── test_belief.py
├── test_inference.py
├── test_policy.py
├── test_action.py
└── test_runtime.py
```

---

## 14.2 Unit Tests

Each runtime component shall include tests for:

* Object creation
* Normal execution
* Invalid input
* Boundary conditions

---

## 14.3 Integration Tests

Integration tests shall verify:

* M6 Issue #16 decision integration from RuntimeState through a new RuntimeState
* Observation → Belief
* Belief → Policy
* Policy → Action
* A future continuous runtime lifecycle only after a separately approved loop
  issue

---

## 14.4 Acceptance Tests

The M6 Issue #16 decision-integration increment is considered successful when:

* RuntimeController completes one decision-integration transition successfully.
* No runtime loop is introduced by this increment.
* Every module satisfies the SRS.
* All unit tests pass.

---

# 15. Extension Points

## M8 Task Model Layer

`src/core/task.py` provides immutable `Goal` and `Task` value models with
`to_dict()` / `from_dict()` public serialization APIs. `Goal` contains a
description, an ordered tuple of success criteria, and metadata. `Task` owns one
Goal, uses a stable UUID identity, and contains dictionary input, context,
constraints, and metadata. Recursive immutable storage prevents nested mutable
caller values from altering model semantics; serialization returns fresh ordinary
containers.

Task and Goal remain outside RuntimeState. GoalDirectedAgent derives Task input
into an initial Observation at task-execution time. These models contain no
execution logic and have no dependency on RuntimeController, inference, Policy,
ActionExecutor, or tools.

## M8 Result and Completion Layer

`src/core/result.py` owns `AgentStatus`, `TerminationReason`,
`CompletionDecision`, and `AgentResult`. These immutable serializable value
models hold task-level outcome information and may depend on Task identity and
RuntimeState, but never alter RuntimeState. `AgentResult` does not embed a Task
or an execution trajectory.

`src/core/completion.py` owns a stateless `CompletionEvaluator` with
an evaluation-only public API accepting Task, RuntimeState, and an optional
candidate answer. It deterministically validates only the Task-input
`expected_answer` value and returns a compact `CompletionDecision`; it does not
invoke tools, generate policies or answers, mutate state, or orchestrate runtime
cycles. GoalDirectedAgent, not RuntimeController or PolicyEngine, constructs
final AgentResult values from completion and termination context. No full
trajectory is stored, and Runtime Foundation APIs remain unchanged.

## M8 Controlled Tool Layer

`src/core/tool.py` contains the Tool contract, immutable ToolResult,
explicit instance ToolRegistry, and ToolResult-to-Observation adapter. Concrete
local capabilities belong below it in `src/tools/`, beginning with CalculatorTool.
Tool execution remains distinct from ActionExecutor and RuntimeController.
GoalDirectedAgent explicitly resolves registered tools, invokes them, adapts the
ToolResult to Observation, and sends that Observation through
RuntimeController.apply_inference(). No ToolExecutor, plugin discovery, or
ToolRequest model is present.

## M8 Goal-Aware Policy Layer

`src/core/goal_policy.py` provides `GoalAwarePolicyEngine.generate(task,
runtime_state) -> Policy`. It depends only on Task, RuntimeState, and Policy;
it has no ToolRegistry or CompletionEvaluator dependency. GoalDirectedAgent
consumes only its decision data. Existing PolicyEngine remains unchanged.

## M8 Goal-Directed Agent Layer

`src/core/agent.py` provides `GoalDirectedAgent` above the runtime
foundation. It receives an explicit ToolRegistry, uses RuntimeController
initialization and inference APIs only, consumes GoalAwarePolicy decisions,
adapts ToolResult to Observation, calls CompletionEvaluator, and assembles
AgentResult. It does not use RuntimeController's prototype decision/run APIs,
retain trajectories, or alter existing component contracts. It is behaviorally
stateless: the only retained reference is the caller-owned explicit ToolRegistry.

The complete M8 flow is Task/Goal -> Task Observation -> runtime initialization
and inference -> GoalAwarePolicyEngine -> direct completion evaluation or
registered Tool execution -> ToolResult Observation -> inference -> completion
evaluation -> AgentResult. Direct candidates do not change RuntimeState; Tool
results do. Each run has an explicit finite `max_cycles`; a final state plus
compact evidence is retained, not a history. End-to-end validation covers
completed, failed, incomplete, zero-cycle, serialization, semantic determinism,
immutability, and statelessness behavior.

## M9 Strategy Model Layer

M9 Issue #29 introduces `src/core/inference_strategy.py`, containing one immutable,
serializable `InferenceStrategy` descriptor. Its dependency direction is data
only: it does not depend on RuntimeController, InferenceEngine, Policy,
ActionExecutor, ToolRegistry, CompletionEvaluator, or GoalDirectedAgent.

The descriptor supplies a stable case-sensitive name, description, ordered
capabilities, stable configuration, and metadata. It contains no executable
implementation reference. A later explicit instance-level registry may map its
name to a controlled executable association; MetaInferenceEngine may later
select descriptor data; GoalDirectedAgent may later consume the approved
decision. None of those future components is introduced here. RuntimeState and
all current M1–M8 APIs remain unchanged.

## M9 Decision Model Layer

Issue #30 introduces a data-only src/core/meta_inference.py layer containing
MetaInferenceDecisionStatus, DecisionEvidence, and MetaInferenceDecision. The
dependency direction is from a future MetaInferenceEngine to these value models;
these models do not depend on the registry, InferenceEngine, RuntimeController,
GoalDirectedAgent, or runtime state.

InferenceStrategy describes an available strategy; MetaInferenceDecision records
one selection result by stable strategy name and compact ordered selection
rationale. DecisionEvidence is distinct from AgentResult evidence: it explains
a strategy decision rather than task execution. The models contain no strategy
implementation, selection algorithm, score, confidence, uncertainty, runtime
history, or Agent integration. Issue #31 owns registry association, Issue #32
owns selection behavior, and Issue #33 owns Agent use of an approved decision.

## M9 Controlled Strategy Registry Layer

Issue #31 introduces src/core/inference_registry.py as an instance-scoped
configuration layer between InferenceStrategy and a future MetaInferenceEngine.
It keeps the immutable descriptor separate from a controlled Protocol-backed
implementation association, with explicit registration and exact deterministic
lookup. It has no selection, scoring, confidence, uncertainty, inference
invocation, RuntimeController, or GoalDirectedAgent behavior.

The dependency direction is InferenceStrategy and the implementation Protocol
into InferenceStrategyRegistry, then a future MetaInferenceEngine consuming the
registry and MetaInferenceDecision models. Registry state is runtime
configuration and is deliberately not serialized. No global registry, dynamic
import, plugin discovery, reflection loading, replacement, or thread-safety
mechanism is introduced.

## M9 Deterministic Meta-Inference Engine Layer

Issue #32 introduces a state-free MetaInferenceEngine consuming an explicit
InferenceStrategyRegistry plus Task and RuntimeState inputs to construct a
MetaInferenceDecision. Its deterministic subset-capability match reads only
Task.metadata.required_inference_capabilities. It uses registry list_names and
descriptor get; it does not retrieve or invoke implementations. One match is
selected, no match unavailable, and multiple matches rejected without priority.
The Engine has no inference execution, RuntimeController, observation, Agent,
confidence, uncertainty, ranking, or scoring behavior.

## M9 Meta-Inference Agent Integration Layer

Issue #33 introduces explicit optional MetaInferenceEngine injection into
GoalDirectedAgent. The Agent initializes state, invokes select, records compact
decision evidence, then continues its existing policy/tool/completion flow only
for selected outcomes. It does not invoke registry implementations or change
RuntimeController/InferencesEngine behavior. Unavailable/rejected outcomes end
before task policy cycles with an explicit existing terminal result; no fallback
is permitted.

The Version 1.0 architecture intentionally reserves extension points.

Future versions should extend the system without redesigning the architecture.

---

## M10 Comparative Evaluation Layer

The completed M10 evaluation layer is outside the cognitive runtime and Agent
architecture. It consumes immutable public values and must not change Agent,
RuntimeController, InferenceEngine, Policy, Tool, or Meta-Inference behavior.

`evaluation/tasks/` provides immutable EvaluationTask and EvaluationScenario
values plus a frozen deterministic fixture factory. `evaluation/runner/`
returns compact immutable EvaluationRunResult values for explicitly configured
M8-style and M9-enabled GoalDirectedAgent baselines. `evaluation/metrics/`
consumes only compact run results and produces immutable deterministic metrics.
`evaluation/results/` executes the frozen local protocol and retains only
repetition-indexed compact summaries, consistency indicators, and metrics.

The approved A/B distinction is explicit Meta-Inference injection. Evaluation
retains no RuntimeState, Agent, Tool, registry, strategy implementation, or
trajectory. It has no network, LLM, external dataset, adaptive learning, or
claim of intelligence, reasoning quality, generalization, or superiority.

## M12 Controlled Meta-Inference Validation Scope (Planned)

M12 is an evaluation-only layer above the delivered M8/M9 public interfaces.
It shall consume frozen Task, MetaInferenceDecision, AgentResult, and compact
evaluation-result values without changing Agent, RuntimeController,
InferenceEngine, Policy, Tool, registry, or MetaInferenceEngine behavior.

The planned baseline contract is: M8 Agent with no Meta-Inference, a separately
frozen deterministic fixed-selection baseline, and the delivered M9 Agent with
MetaInferenceEngine and registry. All comparisons shall hold Task data, local
ToolRegistry configuration, cycle budget, capability vocabulary, descriptors,
and result schema constant.

M12 validates selection, unavailable, ambiguity, evidence-consistency,
determinism, and M8-preservation semantics. It does not execute selected
strategy implementations and shall not interpret decision evidence as an
execution input. No LLM, network, external benchmark, planning, multi-tool
optimization, autonomous learning, strategy-execution change, or
task-performance-improvement claim belongs to this layer.


## Reserved Extension Points

### Inference Operators

Future operators may include:

* Bayesian Inference
* Active Inference
* LLM-based Inference
* Hybrid Inference

---

### Memory

Future memory modules may include:

* Working Memory
* Episodic Memory
* Semantic Memory

---

### Tool System

Future runtime tools may include:

* Search
* Retrieval
* Python Execution
* External APIs

---

### Multi-Agent Runtime

Future releases may support:

* Agent Communication
* Belief Sharing
* Distributed Runtime
* Collective Decision Making

---

# 16. Coding Conventions

All source code shall comply with the following conventions.

---

## Language

* Python 3.11+

---

## Style

* PEP 8
* Explicit type hints
* Google-style docstrings
* Descriptive variable names

---

## Design

* Prefer composition over inheritance.
* Keep functions small and focused.
* Avoid hidden side effects.
* Avoid global mutable state.
* Keep modules independent.

---

## Documentation

Every public class shall include:

* Purpose
* Parameters
* Return values
* Examples (when appropriate)

---

## Commit Convention

Use Conventional Commits.

Examples:

```text
feat(runtime): implement runtime lifecycle

feat(belief): add belief serialization

test(runtime): add lifecycle tests

refactor(policy): simplify policy generation
```

---

# 17. Future Architecture

Version 1.0 validates the runtime abstraction.

Future releases expand the architecture without changing the core runtime.

---

## Version 0.2

* Multiple inference operators
* Tool registry
* Improved configuration system

---

## Version 0.3

* Adaptive operator selection
* Runtime scheduling
* Persistent memory

---

## Version 0.4

* Multi-Agent Runtime
* Belief synchronization
* Agent communication protocol

---

## Version 1.0

The long-term vision includes:

* Complete inference runtime
* Benchmark suite
* Visualization dashboard
* Stable SDK
* Public API
* Research publication

---

# Appendix A — High-Level Architecture

The MIND-Lite prototype consists of six core runtime components.

```text
                  RuntimeController
                        │
                        ▼
                    InferenceEngine
                        │
                        ▼
                      Belief
                        │
                        ▼
                    RuntimeState
                        │
                        ▼
                    PolicyEngine
                        │
                        ▼
                    ActionExecutor
```

RuntimeController coordinates RuntimeState and the current prototype behavior
components.

RuntimeState is the immutable runtime data model.

All current prototype orchestration interactions are coordinated through
RuntimeController; no separate Runtime class exists.

---

# End of Document

**Software-Architecture-Specification-v1.0**

Version: **v1.0**

Status: **Architecture Frozen**

This document defines the complete software architecture for the MIND-Lite prototype and serves as the authoritative implementation blueprint for all future development.
