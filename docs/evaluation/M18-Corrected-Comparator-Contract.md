# M18 Corrected Comparator Contract

## Status and scope

**Verdict:** `M18 CORRECTED COMPARATOR CONTRACT SPECIFIED`.

This is a specification-only correction for a future condition. It authorizes neither an implementation change nor a provider call, pilot run, formal run, suite change, environment change, evaluator change, or budget change. The proposed identity is `m18_v3_comparator_contract_v2`; it is a **COMPARATOR CONTRACT CORRECTION**, not a benchmark semantic change.

## Code-supported Plan defect

The current control flow is `M18PlanAndExecuteBaseline.step` in `src/evaluation/m18_plan_and_execute.py`:

1. `planner` is called when `self._plan is None`.
2. The executor receives `plan`, `cursor`, current public feedback, public tools, and budget. Its present request contract requires `0 <= cursor < len(plan.steps)`.
3. An executor `tool_call` sets `_pending_tool=True`.
4. On the next call, a `TOOL_RESPONSE` while pending increments `cursor` and clears `_pending_tool`.
5. The adapter then tests `cursor >= len(plan.steps)` before it can construct another executor request; if true it returns `FAIL(plan_exhausted)`.
6. Otherwise, the executor may return `answer` or `tool_call`; an answer is submitted by the shared runtime to the evaluator.
7. Public `INVALID_ACTION` or recoverable `TOOL_FAILURE` invokes `replan` when its allowance remains, otherwise the adapter returns `replan_limit_reached`.

The precise defect state is therefore: a tool call for the final indexed plan step completed successfully; `_cursor == len(_plan.steps)` and `_pending_tool == False`; no executor request giving a final answer opportunity has occurred. The cursor guard terminates in this state. This does not attribute every historical Plan failure to this defect.

## Corrected Plan completion state machine

| State | Entry condition | Required transition |
| --- | --- | --- |
| `EXECUTING_PLAN` | `cursor < len(steps)` | Execute the next ordinary decision. A successful final executable step enters `ANSWER_PENDING`. |
| `ANSWER_PENDING` | All executable steps complete; no answer opportunity yet | Make one ordinary executor decision using the shared answer/action contract. |
| `ANSWERED` | A structurally valid answer is decoded and handed to the shared runtime | Terminal adapter state; the evaluator classifies it. |
| `REPLAN_AVAILABLE` | Public invalid/recoverable feedback and `replan_calls < max_replans` | Make one replan, replacing remaining executable work, then return to execution. |
| `PLAN_EXHAUSTED` | Legitimate exhaustion condition below | Bounded terminal failure. |

`ANSWER_PENDING` must use an explicit typed request phase/mode (or equivalent request variant); it must not pretend that an out-of-range cursor identifies another executable step. Entering it neither consumes an action-cycle nor a tool-attempt. Its real executor decision remains subject to the unchanged action-cycle budget and cannot synthesize an answer.

## Legitimate `plan_exhausted`

`plan_exhausted` must not mean `cursor >= len(plan.steps)`. It is legitimate only after all executable steps are complete, an answer opportunity has already occurred without yielding a decodable answer, and no legal continuation or eligible replan remains. An independently enforced budget or unrecoverable environment termination retains its existing, distinct terminal reason. Thus, `cursor >= len(plan.steps)` with `answer_opportunity_occurred == false` enters `ANSWER_PENDING`, never `PLAN_EXHAUSTED`.

An answer decoded in `ANSWER_PENDING` enters `ANSWERED` whether the evaluator later calls it success, wrong answer, malformed answer, or interaction incomplete. An invalid, missing, or non-integer answer is a decoder failure, not a successful answer or automatic tool action.

## Replan and interaction semantics

`max_replans` remains exactly `1`: one initial planner call plus at most one eligible replan. Only public `invalid_action` and recoverable failure remain eligible. Plan completion creates no planning attempt. A decoded answer is handed to the evaluator and never automatically replans; decoder rejection is a strict output failure, not feedback that silently creates a replan. Once the allowance is used, the next eligible feedback terminates with `replan_limit_reached`.

The v3 evaluator permits submission of an answer action and then returns `interaction_incomplete` if the required public trajectory is not complete. The corrected comparator preserves that behavior: it may submit a structurally valid integer early, and the evaluator—not the comparator—returns `interaction_incomplete`. It must not convert this outcome to success or automatically issue a tool call. Conversely, completing Plan steps is an answer opportunity, not proof of evaluator interaction completion.

## Shared answer-value and decoder contract

The evaluator requires a JSON integer and excludes booleans. Every corrected provider-facing answer branch—MIND, Direct, ReAct, and Plan—must use this same schema:

```json
{"type":"object","additionalProperties":false,"required":["action","answer"],"properties":{"action":{"const":"answer"},"answer":{"type":"integer"}}}
```

The decoder must also enforce `isinstance(answer, int) and not isinstance(answer, bool)` before evaluator invocation. The current shared Direct decoder and its `"answer": {}` schema are historical behavior, not the corrected contract.

| Provider output | Corrected decoder behavior | Evaluator invocation |
| --- | --- | --- |
| Integer answer | Accept | Exactly once |
| String, float, object, array, null, or boolean answer | Typed rejection | Never |
| Missing answer / invalid answer structure | Structural rejection | Never |
| Invalid JSON / extra fields | Strict rejection | Never |

There is no coercion: neither `"17"` nor `17.0` becomes `17`. Rejection preserves strict repository failure semantics: no silent repair, retry, fallback, success, tool action, or replan.

## Identity, evidence, and benchmark preservation

Future logical run identity must bind `comparator_contract_id: m18_v3_comparator_contract_v2` (or an equivalently closed field), use a domain-separated run-ID schema/version, and persist into a separate result namespace or provenance binding. Corrected evidence needs new run IDs and a new admitted result-set digest; it must never be aggregated as repetitions of the old condition.

Original M18 v3 pilot evidence remains historical under the original comparator condition: 360 canonical records, digest `196b48cec882fd78492f82e6dc6a031da66203dacd84f62b8142e1f4d0f77e78`. M18 v2 canonical evidence remains 360 records with digest `50caa6c9afaaf3712e10c5f75f397bb1f8306ebe12b0fd305a8f076a4a79473c`; v2 diagnostic evidence remains 72 records with digest `2c2f3f52dfde996fba8b91e491297b7fdc7cc2f09425d3ba51595a06a0bbf0e2`.

Benchmark semantics preserved: **YES**. Cases, public action context, environment transitions, evaluator target and success criterion, the 6 action-cycle / 4 tool-attempt budget, and provider configuration remain frozen.

## Provider-free acceptance criteria for future implementation

- Scripted-provider tests show exact-length one-step and multi-step Plans complete tools, enter `ANSWER_PENDING`, and submit an answer.
- Exhaustion occurs only under the stated legitimate condition, never merely after final cursor advancement.
- Exactly one eligible replan is allowed; the next eligible failure is `replan_limit_reached`, without another planning call.
- An early integer answer remains evaluator-classified `interaction_incomplete`, without automatic success or tool use.
- All four comparators accept an integer and reject non-integer, missing, and malformed answers before evaluator invocation, using equivalent decoder behavior except for the intended Plan completion correction.
- Historical regression fixtures reproduce old exact-length Plan termination before answer and show the same public trajectory reaches an answer opportunity in the corrected condition.
- Historical regression fixtures show the old schema structurally accepted a non-integer answer and the corrected schema/decoder rejects it.

No provider call, benchmark run, pilot run, formal run, or implementation change is part of this specification.
