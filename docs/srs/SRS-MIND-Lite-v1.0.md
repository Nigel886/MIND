# SRS-MIND-Lite-v1.0
 
 **Software Requirements Specification**
 
 Project: **MIND (Meta-Inference Network Dynamics)**
 
 Version: **v1.0**
 
 Status: **Draft**
 
 ---
 
 # 1. Introduction
 
 ## 1.1 Purpose
 
 This document specifies the software requirements for the first executable prototype of the MIND project, named **MIND-Lite**.
 
 Unlike the RFC documents, which define the theoretical foundations and research concepts, this Software Requirements Specification (SRS) defines the software architecture, functional requirements and module responsibilities necessary for implementation.
 
 The intended audience includes:
 
 * Developers
 * Contributors
 * Prototype implementers
 * AI coding assistants (e.g., TRAE, Cursor, Claude Code)
 
 ---
 
 ## 1.2 Project Scope
 
 MIND-Lite is **not** intended to be a complete multi-agent framework.
 
 Its purpose is to validate the core runtime abstraction proposed by the MIND project.
 
 The first prototype focuses on a **single inference agent** capable of:
 
 * receiving observations,
 * maintaining explicit beliefs,
 * performing inference,
 * selecting actions,
 * interacting with external tools.
 
 Advanced capabilities such as adaptive operator configuration, belief communication and multi-agent collaboration are intentionally excluded from this version.
 
 ---
 
 ## 1.3 Goals
 
 The primary objectives of MIND-Lite are:
 
 * Validate the inference runtime architecture.
 * Validate explicit belief representation.
 * Establish reusable software abstractions.
 * Build the foundation for future adaptive runtime research.
 
 ---
 
 # 2. System Overview
 
 The runtime consists of six primary components.
 
 ```text
 Observation
       │
       ▼
 Inference
       │
       ▼
 Belief
       │
       ▼
 Policy
       │
       ▼
 Action
       │
       ▼
 Environment
 ```
 
 Each execution cycle updates the agent's belief state before selecting the next action.
 
 ---
 
 # 3. System Architecture
 
 The prototype follows a modular architecture.
 
 ```text
 src/
 │
 ├── core/
 │   ├── observation.py
 │   ├── belief.py
 │   ├── inference.py
 │   ├── policy.py
 │   ├── action.py
 │   └── runtime.py
 │
 ├── operators/
 │   ├── base.py
 │   ├── bayesian.py
 │   └── llm.py
 │
 ├── tools/
 │
 ├── memory/
 │
 ├── utils/
 │
 └── main.py
 ```
 
 Each directory has a single responsibility.
 
 No module should perform responsibilities assigned to another module.
 
 ---
 
 # 4. Design Principles
 
 The prototype follows the following engineering principles.
 
 ## DP-1 Single Responsibility
 
 Each module performs one responsibility only.
 
 ---
 
 ## DP-2 Explicit Runtime State
 
 All runtime state must be represented explicitly.
 
 Conversation history is not considered runtime state.
 
 Belief objects are runtime state.
 
 ---
 
 ## DP-3 Interface First
 
 All major runtime components communicate through abstract interfaces.
 
 Concrete implementations must remain replaceable.
 
 ---
 
 ## DP-4 Model Independence
 
 No runtime component may depend directly on a specific language model.
 
 LLMs are accessed only through operator interfaces.
 
 ---
 
 ## DP-5 Extensibility
 
 Future runtime components should be added without modifying existing interfaces whenever possible.
 
 ---
 
 # 5. Runtime Lifecycle
 
 Every runtime iteration executes the following sequence.
 
 ```text
Receive Observation
        │
        ▼
Inference Engine
        │
        ▼
Generate New Belief
        │
        ▼
Runtime Controller
(Update RuntimeState)
        │
        ▼
Policy Engine
        │
        ▼
Action
        │
        ▼
Receive New Observation
 ```
 
 The runtime repeats until termination conditions are satisfied.
 
 ---
 
 # 6. Out of Scope
 
 The following capabilities are intentionally excluded from MIND-Lite.
 
 * Multi-agent collaboration
 * Belief synchronization
 * Adaptive runtime scheduling
 * Runtime visualization
 * Distributed execution
 * Long-term memory optimization
 * Reinforcement learning
 * Meta-Inference
 * Operator adaptation
 
 ---

# 7. Functional Requirements

The following functional requirements define the minimum capabilities required for the MIND-Lite prototype.

---

## FR-1 Observation Management

### Description

The runtime shall receive observations from external sources.

### Inputs

* User input
* Tool output
* External API response
* Runtime feedback

### Outputs

* Observation Object

### Acceptance Criteria

* Every observation is encapsulated as an Observation object.
* Observation objects are immutable after creation.
* Every observation contains a timestamp and source identifier.

---

## FR-2 Belief Management

### Description

The runtime shall maintain an explicit belief state.

### Responsibilities

* Store the current world state.
* Record confidence information.
* Support belief updates.
* Support serialization.

### Acceptance Criteria

* Belief state can be saved and restored.
* Belief updates do not modify historical observations.
* Belief is updated only through the Inference module.

---

## FR-3 Inference Engine

### Description

The Inference Engine derives a new immutable Belief from the current Observation and the current Belief.

The Inference Engine is a pure transformation component responsible solely for belief inference.

It SHALL NOT:

- modify RuntimeState;
- perform runtime orchestration;
- execute actions;
- access external tools directly.

### Inputs

* Observation
* Current Belief

### Outputs

* Updated Belief

### Constraints

- The Inference Engine shall expose a single public inference operation.
- The Inference Engine shall remain stateless.
- The Inference Engine shall not perform runtime orchestration.
- The Inference Engine shall not execute actions.
- Different inference operators shall share the same interface.

### Acceptance Criteria

- A new immutable Belief is produced.
- Previous Belief remains unchanged.
- Multiple inference operators can be swapped without changing runtime behavior.

---

## FR-4 Policy Generation

### Description

The Policy Engine shall derive exactly one immutable Policy decision object from
the current Belief. A Policy describes the next action but does not execute it.

### Inputs

* Current Belief

### Outputs

* One immutable Policy object

### Responsibilities

* Produce a deterministic prototype decision from the current Belief.
* Identify the selected action type.
* Preserve action parameters and non-execution decision metadata.

### Constraints

- Policy shall be immutable and serializable.
- Policy shall contain only `action`, `parameters`, and `metadata`.
- Policy shall not execute actions, invoke tools, create Observations, or own
  hidden state.
- PolicyEngine shall consume only Belief, remain stateless, and produce no
  external side effects.
- PolicyEngine shall not modify the input Belief, perform runtime orchestration,
  or execute actions.
- Equivalent Belief inputs shall produce equivalent Policy outputs.
- This prototype shall not implement Expected Free Energy optimization, Active
  Inference policy selection, reinforcement learning, utility or cost
  optimization, candidate-action registries, or action search.

### Acceptance Criteria

* Policy generation depends only on the current Belief and returns exactly one
  Policy.
* Policy objects can be serialized and restored without loss of nested
  parameters or metadata.
* Policy objects remain independent of action execution.
* The input Belief remains unchanged after Policy generation.

---

## FR-5 Action Execution

### Description

ActionExecutor shall execute one selected Policy and return a new immutable
Observation that represents the execution result. Action execution is separate
from Policy generation and does not modify Belief.

### Inputs

* One Policy object

### Outputs

* One new Observation object

### Supported Prototype Actions

* `await_observation` produces an Observation indicating that the system is
  waiting for new external evidence.
* `maintain_belief` produces an Observation indicating that no external action
  is currently required and the existing belief state remains unchanged.

Both identifiers are deterministic prototype execution semantics only. They do
not update Belief or invoke external systems.

### Result Contract

Every successful execution shall create an Observation through the existing
Observation creation mechanism with:

* `source` equal to `"action_executor"`;
* structured `content` containing `action`, `status` equal to `"completed"`,
  and `parameters` from the input Policy.

### Unsupported Actions

Unsupported Policy action identifiers shall fail explicitly. The prototype shall
raise `ValueError` until a dedicated ActionError type is introduced by an
approved specification.

### Supported Actions

* `await_observation`
* `maintain_belief`

### Constraints

- ActionExecutor shall consume only Policy and shall never generate Policy.
- ActionExecutor shall remain stateless and shall never modify Policy, Belief,
  or RuntimeState.
- ActionExecutor shall not access Belief, perform inference, or orchestrate the
  runtime lifecycle.
- ActionExecutor shall not access the network, shell, arbitrary Python,
  production APIs, authentication, retries, scheduling, memory, or multi-agent
  behavior.
- No RuntimeController integration is included in this issue.
- No Tool interface, registry, discovery mechanism, dynamic loading, or real
  external integration is required for these two self-contained prototype
  actions.

### Acceptance Criteria

* Every executed action generates a new observation.
* Successful execution returns a new immutable Observation with a unique identity
  and timestamp assigned by the existing Observation model.
* Action execution must not modify Policy or Belief directly.
* Unsupported action identifiers fail explicitly.

---

## FR-6 Runtime Subsystem

### Description

The Runtime Subsystem consists of two architectural components:

* RuntimeState
* RuntimeController

RuntimeState represents the immutable runtime data model.

RuntimeController coordinates the complete execution cycle by operating on RuntimeState instances.

### RuntimeState Responsibilities

* Store the current Observation.
* Store the current Belief.
* Store runtime metadata.
* Support serialization and deserialization.

RuntimeState SHALL remain immutable.

### RuntimeController Responsibilities

RuntimeController is responsible for:

- initializing RuntimeState;
- updating RuntimeState;
- coordinating interactions between RuntimeState and the completed inference and
  decision components.

RuntimeController SHALL remain stateless.

RuntimeController SHALL NOT own RuntimeState internally.

RuntimeController SHALL construct new RuntimeState instances instead of modifying existing ones.

For M6 Issue #16, RuntimeController shall provide
`apply_decision(runtime_state: RuntimeState) -> RuntimeState`. Given one
RuntimeState, it shall read the current Belief, delegate Policy generation to
PolicyEngine, delegate the resulting Policy to ActionExecutor, and incorporate
the returned Observation through update(). This operation performs one state
transition only; it does not perform inference or run a runtime loop.

Policy is transient during this operation and shall not be persisted in
RuntimeState. RuntimeState shall continue to contain only observation, belief,
and metadata.

For M6 Issue #17, RuntimeController shall provide
`run_cycle(runtime_state: RuntimeState, observation: Observation) -> RuntimeState`.
It shall call `apply_inference(runtime_state, observation)` exactly once, then
call `apply_decision(inferred_state)` exactly once, and return the final state.
The incoming Observation is evidence for inference; the final state's
Observation is the action-result Observation returned by ActionExecutor.

One runtime cycle is not a bounded runtime loop. Cycle limits, termination
evaluation, and multiple-cycle execution belong to Issue #18.

For M6 Issue #18, RuntimeController shall provide
`run(runtime_state: RuntimeState, observation: Observation, max_cycles: int) -> RuntimeState`.
It shall execute exactly `max_cycles` calls to `run_cycle()`, using the initial
Observation for the first call and each returned RuntimeState Observation for
the next call. It shall return only the final RuntimeState.

`max_cycles` shall be an `int` but not `bool`. Non-integer values and bool
values raise TypeError; negative integers raise ValueError; zero returns the
original RuntimeState unchanged. The only termination condition is reaching the
explicit limit. This is deterministic prototype execution, not adaptive runtime
scheduling.

### Acceptance Criteria

* RuntimeState objects can be created.
* RuntimeState objects are immutable.
* RuntimeController initializes RuntimeState correctly.
* RuntimeController constructs new RuntimeState instances through update().
* RuntimeController remains stateless.
* Decision integration returns a new immutable RuntimeState and leaves its input
  RuntimeState unchanged.
* The returned RuntimeState contains the Observation returned by ActionExecutor
  and preserves the current Belief.
* Metadata is preserved according to the existing RuntimeController.update()
  contract.
* Policy is not persisted in RuntimeState and RuntimeState fields are not
  expanded.
* PolicyEngine and ActionExecutor retain their existing responsibilities; the
  RuntimeController implements neither policy generation nor action execution.
* Unsupported-action ValueError is not silently swallowed.
* Decision integration performs no inference and no runtime loop.
* One runtime cycle performs exactly one inference, generates exactly one
  Policy, and executes exactly one action.
* The final RuntimeState is new, contains the Belief produced from the incoming
  Observation, and contains the Observation returned by ActionExecutor.
* The original RuntimeState and incoming Observation remain unchanged; metadata
  is preserved according to the existing update() contract.
* RuntimeController reuses apply_inference() and apply_decision(), remains
  stateless, duplicates no component logic, and propagates errors without a
  fallback state.
* A bounded run performs exactly the requested positive number of cycles; each
  cycle after the first receives the preceding action-result Observation.
* The initial RuntimeState and Observation remain unchanged; every successful
  cycle returns a new immutable state and only the final state is returned.
* No trajectory, metadata counter, retry, fallback, semantic termination, or
  unbounded loop is introduced. Component exceptions propagate immediately.

---

# 8. Non-Functional Requirements

---

## NFR-1 Modularity

Each runtime component shall be independently replaceable.

---

## NFR-2 Extensibility

Future modules shall be integrated without modifying existing public interfaces.

---

## NFR-3 Explainability

All belief updates shall be traceable.

Developers should be able to inspect:

* Input observation
* Previous belief
* Updated belief
* Selected policy
* Executed action

---

## NFR-4 Maintainability

Every major module shall contain:

* Type annotations
* Documentation
* Unit tests

---

## NFR-5 Performance

The runtime architecture shall avoid unnecessary coupling.

The target of MIND-Lite is architectural validation rather than optimization.

---

## NFR-6 Portability

The prototype shall run on:

* Windows
* macOS
* Linux

without modifying source code.

---

# 9. Module Responsibilities

| Module                | Responsibility                                            |
| --------------------- | --------------------------------------------------------- |
| observation.py        | Define the Observation object and manage external inputs. |
| belief.py             | Maintain and update the explicit belief state.            |
| inference.py          | Execute inference operators and produce updated beliefs.  |
| policy.py             | Generate executable policies from beliefs.                |
| action.py             | Execute actions and interact with external environments.  |
| runtime.py            | Implement the Runtime subsystem, including RuntimeState and RuntimeController orchestration.              |
| operators/base.py     | Define the abstract inference operator interface.         |
| operators/bayesian.py | Reference Bayesian inference implementation.              |
| operators/llm.py      | LLM-based inference implementation.                       |
| memory/               | Future extension for persistent runtime memory.           |
| tools/                | External tool interfaces and wrappers.                    |
| utils/                | Shared utility functions.                                 |

---

# 10. Runtime Interfaces

This section defines the software interfaces between runtime components.

The interfaces described here are implementation-independent.

---

## 10.1 Observation Interface

### Input

External environment events.

Examples:

* User messages
* Tool responses
* API responses
* Runtime feedback

### Output

```text
Observation
```

### Responsibilities

* Create immutable observation objects.
* Record timestamps.
* Record observation sources.

---

## 10.2 Inference Interface

### Input

```text
Observation
Current Belief
```

### Output

```text
Updated Belief
```

### Rules

* The inference module must not perform actions.
* The inference module must not call external tools directly.
* Every inference operator must implement the same interface.

---

## 10.3 Belief Interface

### Supported Operations

* Create
* Read
* Update
* Serialize
* Deserialize
* Clone

### Rules

* Beliefs are mutable only through the inference engine.
* External modules cannot modify beliefs directly.

---

## 10.4 Policy Interface

### Input

```text
Belief
```

### Output

```text
Policy
```

### Rules

* Policy generation must be deterministic given identical inputs.
* Policies contain decisions only.
* Policies do not execute actions.

---

## 10.5 Action Interface

### Input

```text
Policy
```

### Output

```text
Observation
```

### Rules

* Every executed action must generate a new observation.
* Action execution must never update beliefs directly.

---

# 11. Runtime State Machine

The runtime executes a continuous state transition process.

```text
Observation

↓

Inference Engine

↓

Belief

↓

Runtime Controller

↓

RuntimeState

↓

Policy

↓

Action
```

The implemented prototype executes only a finite number of cycles explicitly
requested through `RuntimeController.run(..., max_cycles=...)`. It has no
semantic termination, trajectory storage, hidden long-running loop, or external
Tool execution. Semantic completion is future Goal-Directed Agent scope.

---

# 12. Acceptance Criteria

The MIND-Lite prototype will be considered complete when all of the following conditions are satisfied.

## Runtime

* [x] RuntimeState can be created.
* [x] RuntimeState supports serialization.
* [x] RuntimeController initializes RuntimeState.
* [x] RuntimeController updates RuntimeState immutably.
* [x] Runtime Core integration and bounded execution are validated.

---

## Observation

* [x] Observation objects can be created and are immutable.

---

## Belief

* [x] Belief objects, immutable inference updates, and serialization are supported.

---

## Inference

- [x] InferenceEngine can derive a new immutable Belief.
- [x] Previous Belief remains unchanged.
- [ ] Reference inference operator works.
- [ ] Operators are interchangeable.

---

## Policy

* [x] Policies are generated deterministically from Belief and remain independent of execution.

---

## Action

* [x] Prototype actions generate new immutable observations.

---

## System

* [x] Finite bounded runtime execution, end-to-end validation, and public-interface checks pass.

The completed system is a cognitive runtime foundation. Task/Goal solving,
AgentResult/final answers, real Tools, LLM/network integration, multiple
operators, Meta-Inference, multi-agent behavior, and comparative evaluation
remain explicit future scope.

---

# 13. Future Extensions

The following capabilities are intentionally reserved for future versions of MIND.

## Version 0.2

* Multiple inference operators
* Runtime configuration
* Additional tool interfaces

---

## Version 0.3

* Adaptive operator selection
* Runtime scheduling
* Persistent memory

---

## Version 0.4

* Multi-agent runtime
* Structured belief communication
* Belief merging

---

## Version 1.0

* Complete inference runtime
* Benchmark suite
* Visualization tools
* Public SDK
* Stable API

---

# Appendix A — Terminology

| Term               | Definition                                                        |
| ------------------ | ----------------------------------------------------------------- |
| Observation        | Information received from the environment.                        |
| Belief             | The runtime's explicit representation of the current world state. |
| Inference Operator | A module that transforms observations into updated beliefs.       |
| Policy             | A decision generated from the current belief state.               |
| Action             | An executable interaction with the external environment.          |
| Runtime Subsystem  | The subsystem containing RuntimeState and RuntimeController.      |

---

# End of Document

```
SRS-MIND-Lite-v1.0
Version 1.0
Status: Draft
```
