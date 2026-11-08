# M20 feasibility generation-v2 namespace freeze

Issue #332 defines a prospective execution generation, not a revision of the
historical feasibility evidence.  It retains the scientific protocol
`m20_task_evaluator_feasibility_v1`, the Fixed-only condition, the twelve
cases, two repetitions, and twenty-four original works.

## Frozen execution identity

| Field | Value |
| --- | --- |
| Generation | `m20_task_evaluator_feasibility_generation_v2` |
| Namespace | `m20_task_evaluator_feasibility_v2` |
| Manifest | `m20_feasibility_manifest_v2` |
| Runtime | `m20_feasibility_runtime_generation_v2` |
| Result path | `evaluation/results/m20_task_evaluator_feasibility_v2` |
| Signed owner-risk schema | `m20_feasibility_owner_risk_live_authorization_v3` |
| Owner-risk policy | `m20_owner_risk_accepted_execution_v1` |

The v2 manifest deterministically includes the generation identity in its
canonical identity and work-ID derivation.  It therefore has a distinct
manifest digest and distinct work IDs while retaining the same scientific case
membership and Fixed-only assignment.

## Authorization binding

The v3 owner-risk payload is canonical UTF-8 JSON and includes an explicit
`generation_id` and `result_path` in addition to its exact protocol, manifest, membership,
namespace, work IDs, runtime, provider, ceiling, diagnostics,
policy, and logical-limit fields.  Ed25519 verification and external
trust-anchor lookup remain mandatory.  A v1/v2 authorization is not upgraded
or accepted for v2.

No signed authorization is created by this implementation.

## Destination admission

Before v2 creates an evidence store, budget, ledger, diagnostic store, or
adapter, it derives the only permitted destination from an existing trusted
repository root and the frozen relative result path.  It rejects:

- a caller-selected output root, including the historical v1 root;
- absolute or escaping paths and reparse points;
- an unknown nonempty destination;
- a missing, malformed, or drifted v2 marker; and
- an existing ledger whose full canonical authorization digest is foreign.

An empty v2 destination is the only new writable state.  A nonempty destination
is resume-eligible only when its marker and control headers exactly match v2.
The historical `evaluation/results/m20_task_evaluator_feasibility_v1` path is
not a v2 write target and is not migrated.

## Recovery and accounting

The financial ledger and live-budget schemas remain unchanged.  Their existing
full canonical authorization-digest binding distinguishes v3 v2-generation
state from historical state.  Logical admission remains once per logical
operation; physical retries have separate durable identities.  Existing
reconciliation-before-persistence, permanent unresolved-billing halt,
cross-process physical lease, canonical first replacement, and fail-closed
crash/restart rules apply to v2 without implicit state transfer from v1.

This freeze is offline engineering only.  It neither authorizes a Provider
request nor makes the local CNY 50 plan, CNY 30 warning, or CNY 40 internal
stop threshold a Provider-side spending cap.
