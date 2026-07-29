# ADR-006 — Controlled Local Tool Architecture

**Status:** Accepted

## Context

M8 requires deterministic local capabilities for a future GoalDirectedAgent,
without placing tool behavior in ActionExecutor, RuntimeController, inference,
policy, or completion evaluation.

## Decision drivers

Safety, determinism, explicit registration, immutable result data, testability,
and preservation of existing RuntimeState and runtime APIs.

## Alternatives

1. Separate Tool abstraction, ToolResult, and explicit registry.
2. Put Tool logic in ActionExecutor.
3. Hard-code Tool behavior in GoalDirectedAgent.
4. Use dynamic plugin discovery.

## Proposed decision

Use a small structural `Tool` Protocol in `src/core/tool.py`, requiring a stable
`name` and `execute(parameters: dict[str, Any]) -> ToolResult`. Use immutable,
serializable ToolResult containing `tool_name`, `success`, `output`, `error`,
`parameters`, and optional metadata. Success has output and no error; controlled
failure has no output and a compact string error. Live exceptions and runtime
objects are forbidden.

Use an explicit mutable instance `ToolRegistry` with `register(tool)`,
`get(name)`, `contains(name)`, and deterministic `list_names()`. Names are
non-empty strings, exact and case-sensitive; duplicates raise ValueError, unknown
lookup raises LookupError, and no global registry, discovery, unregister, or
serialization exists.

Do not add ToolRequest: later policy data can carry a tool name and parameter
mapping, and a second request model would duplicate the currently unfrozen
orchestration boundary. Do not add ToolExecutor: a future GoalDirectedAgent will
resolve a Tool from the registry and call it explicitly.

Tools return ToolResult. A narrow `tool_result_to_observation()` adapter in the
tool core converts it to a new Observation with source `"tool:<tool_name>"` and
content `{tool_name, success, output, error}`. Tools do not construct runtime
state or Observation themselves.

The first concrete Tool is `CalculatorTool` in `src/tools/calculator.py`, named
`calculator`. It accepts exactly two operands in a dictionary with `operation`
(`add` or `multiply`) and `operands`. Operands are finite int or float, excluding
bool; strings, Decimal, NaN, infinity, empty/wrong-length lists, and unsupported
operations are validation errors. No eval, parsing, shell, filesystem, network,
browser, external API, LLM, or arbitrary code is allowed.

## Failure semantics

Configuration and parameter validation raise TypeError or ValueError; unknown
tools raise LookupError; unexpected implementation defects propagate. No broad
exception conversion exists. Controlled result failures are reserved for valid
future domain execution failures.

## Compatibility and consequences

RuntimeState, RuntimeController, ActionExecutor, PolicyEngine, CompletionEvaluator,
Task/Goal, and AgentResult remain unchanged. Policy fields can later carry a
tool name and data but never Tool instances. Tool selection, tools in policies,
and Agent orchestration are deferred.

## Deferred capabilities

ToolRequest, ToolExecutor, plugins, discovery, permissions, retry, concurrency,
network tools, GoalAwarePolicyEngine, GoalDirectedAgent, and Meta-Inference.
