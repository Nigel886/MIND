# M18 Plan-and-Execute Baseline

## Architecture identity

The historical `m18_plan_and_execute_baseline_v1` is an evaluation-side condition with a
strict initial planner, immutable explicit public plan, separate executor, and
at most one budgeted replan. The flow is:

```text
public task + public tools -> planner -> explicit plan -> executor -> public feedback
```

It is distinct from Direct (no persistent plan/history), ReAct (public
interaction history but no future plan), and MIND (released cognitive runtime
state). It uses no MIND `RuntimeState`, no ReAct transcript, no hidden provider
history, and no planner/executor tool execution.

The provenance-distinct repaired condition is
`m18_plan_provider_contract_repair_v1`. It retains this comparator design and
adds only an explicit JSON-output instruction to the planner prompt required
by the frozen JSON-object provider mode. See
`M18-Plan-Provider-Contract-Repair.md`; historical results remain associated
with the original condition identity.

## Plan and execution contracts

A plan is an immutable ordered tuple of typed steps, each with a stable step
identifier, public subgoal, and optional public capability identifier. The
strict planner accepts only `{"steps":[...]}` with exactly those fields per
step; generic metadata, evaluator labels, rationale, prose-wrapped JSON, and
unknown fields are rejected.

The executor receives public task, explicit plan, cursor, current public
feedback, public tools, budget, and the shared strict action grammar:

```json
{"action":"answer","answer":<json-value>}
```

```json
{"action":"tool_call","tool_name":"<public-tool-id>","parameters":{}}
```

Successful tool feedback advances the cursor. The executor may derive later
parameters from public feedback; it never rewrites the plan. The planner never
executes tools.

## One-replan policy and accounting

Exactly one initial planner call is allowed. A single replan is allowed only
after public `recoverable_failure` or `invalid_action` feedback. The replan
receives public task/tools, current explicit plan/cursor, and current public
feedback; it replaces the remaining plan. A second eligible failure produces a
bounded termination and no second planner call. Unrecoverable feedback or
exhausted budget also terminates without a provider call.

Planner calls, executor calls, replan calls, tool calls, invalid actions,
recoverable failures, and action cycles are recorded independently. There is no
repair parser, malformed-output retry, fallback model, hidden provider budget,
or evaluator-correctness termination input.

## Truth firewall

Planner, executor, plan, and replan inputs are recursively limited to public
task/tool/feedback/budget data. Expected answers, ground truth, correct
tool/action labels, difficulty, cohort hints, evaluator success, private judge
data, completion labels, credentials, and private reasoning are removed. The
typed plan has no generic metadata channel.

## Frozen artifact identities

| Artifact | SHA-256 |
| --- | --- |
| implementation | `cecf2e8c2f4a64d102e561581cc849384baf9b778185b8e35abb88d110b6afd4` |
| planner prompt | `688efd0d1cae5c940c1991af46bb370e6946ce56540725c192a417d8ccae54ba` |
| planner schema | `caed9738447430206dd1e8487f53407797829370d4fc0c1bfe5835cf2a0a88d1` |
| planner decoder | `875d11cb67d3486a5c0f2c39c9eb45a377c0ff55712611235ecd465c9f45df0b` |
| executor prompt | `a6ae8feb0473fcbf03b34baa1901f64fa8ca079fdca41c8d649a4520fc55ab64` |
| action schema | `ab6a5e8425626177bcb90ae878d89094f5880a304c74999b95b2d31261aee565` |
| executor decoder | `e4979941028c0d03fdaeaf58df5b1a982dcc61c0ec069385f22a0635cecc17b6` |
| plan serializer | `e87ca408628bb702e06b006ff13bc24879583fd3b19c103661aab42f668d8a38` |
| one-replan policy | `94aa4a6d3670e4168a2a783b008d0c9d9c22973992c924030812363a299a88e6` |
| provider-call accounting | `7204c523662d7219cfdce86b00d7a79a6500f77e76e6eb2b98db9294396bcaeb` |

## Validation status

Synthetic provider-free tests cover planner/executor separation, immutable and
deterministic plans, dependent multi-tool progression, public observation-
derived parameters, distractor tools, recoverable and invalid-action replans,
the second-replan limit, strict schemas, truth redaction, and accounting. No
real provider call, pilot, benchmark task, or experiment was run.
