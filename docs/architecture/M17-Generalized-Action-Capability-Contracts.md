# M17 Generalized Action and Capability Contracts

## Purpose

M17 adds an additive foundation for future registered-tool policies without adding policy selection, recovery, planning, or loop behavior. MIND-Lite v1.1 is not yet released.

## CapabilityDescriptor

`CapabilityDescriptor` is frozen and recursively JSON-normalized. It exposes only a registered `tool_id` and optional public display name, description, and parameter schema. `ToolRegistry.capability_descriptors()` derives descriptors from registered tool attributes; legacy name-only tools remain valid.

## Ownership

The session validates only public action shape and JSON compatibility. `ToolRegistry` remains authoritative for registration, unknown identifiers, and declared parameter-schema admission. The session intentionally does not import or query a registry.

## Action Semantics

Existing `answer` and `tool_call` request forms are unchanged. A `tool_call` may now syntactically represent any non-empty public identifier and nested JSON-compatible parameters. Environment/registry admission decides whether that tool exists and whether parameters are valid.

## Safety and Compatibility

Nested contract data is immutable; unsupported Python values fail explicitly. Descriptor data rejects evaluator-private answer, correctness, completion, and routing fields. Direct-answer, calculator, `GoalDirectedAgent.run()`, existing sessions, and M16 behavior are preserved.

## Deferred Work

Observation-conditioned policy behavior, recovery, multi-cycle loop changes, planning, providers, and benchmark tasks are out of scope.
