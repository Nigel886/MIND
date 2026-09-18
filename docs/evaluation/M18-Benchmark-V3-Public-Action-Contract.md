# M18 Benchmark v3 Public Action Contract

## Status and purpose

This document specifies the prospective `m18_suite_v3` public action contract. It is an interface correction derived from the non-canonical M18 v2 diagnostic; it neither changes nor reinterprets historical evidence. It authorizes no provider call, pilot, or formal execution.

The v2 diagnostic established that all four comparator request paths omitted the public state required by the v2 runtime to admit an action. V3 therefore freezes one complete, minimal, public action-context projection. It does not expose evaluator truth or a future reference trajectory.

## Public action-state projection

At each decision cycle, every comparator must receive a canonical `public_action_context` with exactly these task-relevant fields.

| Field | Classification | Contract |
| --- | --- | --- |
| `case_id` | PUBLIC AND REQUIRED | Stable public case identity. |
| `task_text` | PUBLIC AND REQUIRED | Public task instruction only. |
| `state.completed_steps` | PUBLIC AND REQUIRED | Number of successful public transitions. |
| `state.required_successful_steps` | PUBLIC AND REQUIRED | Public action-phase length; it is not an evaluator success result. |
| `state.current_value` | PUBLIC AND REQUIRED | Exact public value required for the next legal tool action. |
| `current_action.tool_id` | PUBLIC AND REQUIRED | The one stable, machine-action identifier currently accepted by the environment. |
| `current_action.parameters` | PUBLIC AND REQUIRED | Exact public action parameter map; initially `{ "value": current_value }`. |
| `current_action.parameter_schema` | PUBLIC AND REQUIRED | Public schema for the current action, including required fields and JSON types. |
| `current_action.available` | PUBLIC AND REQUIRED when an action exists | Boolean current-step availability; `current_action` is `null` only after the public action phase is complete. |
| `capabilities` | PUBLIC AND REQUIRED | The one currently executable capability descriptor: `tool_id`, optional display name, public description, and public parameter schema. Future capabilities are omitted. |
| `latest_feedback` | PUBLIC AND REQUIRED after an interaction; `null` initially | Finite public feedback category and safe public details. |
| `budget` | PUBLIC AND REQUIRED | Current public resource counters and remaining limits. |
| `public_state_version` | PUBLIC BUT OPTIONAL | Monotonic public snapshot identity, if needed for replay/debugging; it cannot encode hidden state. |
| display labels | PUBLIC BUT OPTIONAL | Readability only; never an executable identifier. |

The projection deliberately exposes only the current action and current executable capability. It must not expose a list of future ordered tool IDs, a future parameter sequence, an evaluator target, or a reference trajectory. After an accepted public transition, the environment computes the next state and emits a fresh projection.

`required_successful_steps` and `completed_steps` are public action progress. Their equality is not a private ready-to-answer oracle: answer submission remains an explicit public action and evaluator success remains evaluator-owned.

## Truth firewall — PASS by contract

The following are PRIVATE / FORBIDDEN in `public_action_context`, comparator prompts, capability descriptors, public feedback, traces, plans, and persisted public result fields:

- evaluator expected answer, private target, target state, success oracle, completion label, or judge metadata;
- hidden reference trajectory, future ordered tools, future parameters, or hidden generator state;
- failure schedule before it becomes an actual public feedback event;
- benchmark labels, private routing metadata, credentials, prompts, chain-of-thought, hidden reasoning, or private runtime state.

The v3 adapter must project from a typed current-state view, not pass through the full internal task configuration. This makes the omission of future steps structural rather than blacklist-dependent.

## Stable tool identity

`tool_id` is the sole canonical provider-facing execution identifier. A provider must emit that exact stable identifier in `tool_name`; the runtime must not resolve arbitrary aliases.

Display names may be shown alongside `tool_id`, but are never accepted as aliases. An alias such as `Operation A` is rejected with the finite public category `unknown_tool_id` (or `tool_not_currently_available` when it is a known but non-current stable ID). This preserves deterministic admission and avoids silently broadening runtime acceptance.

## Comparator request equivalence

MIND, Direct, ReAct, and Plan must each receive the exact same serialized `public_action_context` for a given cycle. Their existing comparator-specific structure remains permitted only in addition to that shared projection:

| Comparator | Required common context | Permitted comparator-specific public structure |
| --- | --- | --- |
| MIND | Complete `public_action_context` | Existing public policy/runtime view and latest public observation. |
| Direct | Complete `public_action_context` | Stateless current-feedback framing. |
| ReAct | Complete `public_action_context` | Prior bounded public action/observation history. |
| Plan | Complete `public_action_context` | Existing public plan, cursor, and bounded public replan history. Planning may not receive future ordered tools unavailable in the current context. |

No comparator receives a private target, evaluator data, future action schedule, or extra task-relevant public state absent from another comparator. **Comparator public-context equivalence: PASS by v3 contract.**

## Runtime validation and completeness invariant

For every submitted public action, the runtime validates:

1. allowed action type;
2. exact stable `tool_id` identity;
3. public parameter schema, including required fields and JSON type;
4. current availability (`available_now`);
5. equality with the current ordered tool ID; and
6. state-dependent current public parameter constraints, initially `value == current_public_state.current_value`.

**Public-contract completeness invariant:** for every runtime rejection predicate based solely on public state, the same cycle's provider-facing `public_action_context` must contain sufficient public information to construct an action that satisfies that predicate. A rejection based on private/evaluator state is permitted only when it is not needed to construct a legal public action.

This invariant is mechanically testable by enumerating runtime public-validation branches and requiring a corresponding field in the typed v3 action projection. It prevents a repeat of the v2 task-only adapter projection.

## Public error feedback

Invalid actions return one finite category plus safe details, without private truth:

- `unsupported_action_type`;
- `unknown_tool_id`;
- `tool_not_currently_available`;
- `parameter_schema_violation`;
- `parameter_value_not_current_public_state`;
- `interaction_complete`.

Feedback includes `retry_permitted` and a replacement `current_action` snapshot when another legal public action exists. It does not reveal a future step, target answer, or evaluator success state.

## Answer and budget policy

V3 preserves explicit answer semantics. The environment never sends a private-truth-derived ready signal; it may only expose public progress and the current action availability described above.

V3 initially preserves the v2 numerical budget: six action cycles and four tool attempts. The identity is nevertheless version-bound as `m18_budget_v3`. No budget increase is justified by the v2 interface defect; a changed bound would require separate provider-free evidence and a new documented condition.

## Version identities and run isolation

V3 must use new, non-interchangeable identities:

| Purpose | Identity |
| --- | --- |
| Suite | `m18_suite_v3` |
| Public action contract | `m18_v3_public_action_contract_v1` |
| Environment | `m18_environment_v3` |
| Evaluator | `m18_evaluator_v3` |
| Runtime | `m18_shared_execution_runtime_v3` |
| Budget | `m18_budget_v3` (values remain 6/4) |
| Run-ID schema | `m18_v3_logical_run_id_v1` |
| Result namespaces | `evaluation/m18/results/v3/pilot/m18_suite_v3` and `evaluation/m18/results/v3/formal/m18_suite_v3` |

The run ID must hash the v3 suite identity, case ID, comparator condition ID, repetition, environment/evaluator/budget/runtime identities, provider configuration hash, execution baseline, and v3 public-action-contract identity. Domain separation by the v3 schema and identities is required; collision with M18 v1, canonical M18 v2, M18 v2 diagnostic, or repaired Plan evidence is an admission failure.

## V2 to V3 delta

| Change | Classification |
| --- | --- |
| Replace task-only adapter projection with current typed public action state | Interface correction |
| Require stable `tool_id`, prohibit display-label execution aliases | Interface correction |
| Add public state-dependent parameter equality information | Interface correction |
| Add finite safe error feedback categories and refreshed current action | Interface correction |
| New suite/environment/evaluator/runtime/budget/run identities | Provenance correction |
| Change transition, target, difficulty distribution, answer semantics, or numerical budget | Not authorized by this specification |

V3 is specified as an interface correction only. Any later task semantic or difficulty change must be explicitly documented as a new benchmark condition rather than folded into this correction.

## Historical evidence policy

- M18 v1 evidence remains historical.
- Canonical M18 v2 evidence remains historical operational evidence.
- M18 v2 diagnostic evidence remains root-cause evidence.
- None of these records may be merged with, reclassified as, or used as a denominator for v3 performance evidence.

## Provider-free acceptance criteria before real-provider use

Before any v3 provider call, implementation must prove provider-free that:

1. ideal public action trajectories are accepted;
2. all four comparators receive byte/semantic-equivalent task-relevant public context;
3. every public runtime validation branch maps to a visible contract field;
4. stable `tool_id` round-trips and display-label aliases are rejected predictably;
5. current-action parameters and state constraints are sufficient for legal action construction;
6. truth, secret, and chain-of-thought firewalls hold;
7. deterministic replay holds;
8. v3 run IDs cannot collide with historical namespaces; and
9. canonical historical evidence remains byte/digest unchanged.

No provider smoke, pilot, or formal execution is authorized by this document.
