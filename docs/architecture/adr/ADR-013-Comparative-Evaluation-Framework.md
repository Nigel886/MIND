# ADR-013 - Comparative Evaluation Framework

**Status:** Accepted

## Context

M10 must evaluate the observable effect of the completed deterministic
Meta-Inference architecture without changing the evaluated Agent or confusing
architecture changes with task/environment differences.

## Decision

Use one minimal controlled ablation:

- **Baseline A:** GoalDirectedAgent(tool_registry), equivalent to M8.
- **Baseline B:** GoalDirectedAgent(tool_registry, meta_inference_engine), with
  M9 enabled.

The sole intended variable is explicit Meta-Inference injection. Both baselines
receive identical serialized Tasks, ToolRegistry configuration, capability
registry configuration, max_cycles, Python version, and local runtime
environment.

Use fixed deterministic task categories: direct/calculator success, unique
capability selection, unavailable selection, ambiguous selection, and M8
compatibility (direct, calculator, unsupported, Tool failure, bounded execution).
Run every scenario at least three times and compare semantic signatures while
excluding UUIDs and timestamps. No network, LLM, external data, randomness, or
silent retry is permitted.

Collect only AgentResult status, termination reason, answer, cycles, decision
status, selected strategy, compact evidence semantics, and descriptive elapsed
duration. Do not retain full RuntimeState, private objects, implementation or
Tool instances, trajectories, or hidden state.

Metrics are success/failure rate; selection, unavailable, and ambiguity
correctness; deterministic and evidence consistency; additional decision step;
and descriptive elapsed duration. No intelligence, reasoning-quality,
human-likeness, generalization, or universal-superiority metric is valid.

## Consequences

The evaluation layer observes public outputs and cannot influence Agent,
Runtime, Meta-Inference, or execution behavior. A/B is sufficient for M10 v1;
additional architecture baselines are deferred. Results must report limitations
and negative outcomes. Future work separates protocol (#35), fixtures (#36),
runner (#37), metrics (#38), experiments (#39), and reporting (#40).
