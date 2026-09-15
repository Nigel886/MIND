# M18 ReAct Baseline

## Identity

`m18_react_baseline_v1` is an evaluation-side operational ReAct condition. It
uses the same public task, capabilities, environment feedback, action schema,
and future shared budgets as other M18 conditions. Its defining state is an
ordered explicit public action-observation history:

```text
public action -> public feedback -> append interaction -> next provider decision
```

This differs from Direct, which rebuilds every decision from current public
feedback with no accumulated history. It differs from Plan-and-Execute, which
would retain an explicit future plan. ReAct has no plan, planner, replanner,
MIND runtime state, or private provider conversation history.

## Public history and reasoning privacy

Each immutable history entry contains only a submitted public evaluation action
and the resulting public evaluation feedback. Ordering is append-only and
deterministically serialized. The provider receives that explicit history plus
the current public feedback; no other cross-decision memory exists.

Private reasoning remains private: the provider is never asked to return
thought, rationale, chain-of-thought, confidence, or a plan, and no such field
is stored. The action-observation loop itself is the operational ReAct
mechanism.

## Action and feedback contract

The condition reuses the architecture-neutral strict public action grammar:

```json
{"action":"answer","answer":<json-value>}
```

```json
{"action":"tool_call","tool_name":"<public-tool-id>","parameters":{}}
```

Malformed JSON, prose wrapping, aliases, unknown actions, duplicate keys,
unexpected fields, non-object arguments, plans, and rationale are rejected
explicitly. There is no repair parser, malformed-output retry, self-correction
request, fallback model, secondary planner, or judge call.

A tool response, recoverable failure, or invalid action is appended to public
history and can lead to another provider decision. ReAct does not centrally
choose recovery. Unrecoverable feedback and exhausted action budget terminate
without a further provider call; answer correctness is evaluator owned.

## Truth firewall and resource accounting

Task, feedback, capability, and history serialization recursively excludes
expected answers, ground truth, correct tool/action labels, difficulty, cohort
routing labels, evaluator success, private judge data, completion hints,
credentials, and hidden reasoning. Capabilities retain only the public
structural contract and their supplied order.

One eligible ReAct decision makes one logical provider call. Observational
accounting records decision count, logical calls, tool calls, invalid-action
feedbacks, and recoverable-failure feedbacks. It does not affect any request or
action selection. Shared transport and total provider-call budgets remain a
later baseline/provider freeze.

## Frozen identities

| Artifact | SHA-256 |
| --- | --- |
| implementation condition | `985fd20633c951d6bc35b9dc8502b59a275f0454369173d3a63f4202a59d4639` |
| prompt/template | `ab898143ae0d1b1e301c5cbaa6aa279f8654d97ed0af5b37ba3e9e8aa9ea469c` |
| action schema | `ab6a5e8425626177bcb90ae878d89094f5880a304c74999b95b2d31261aee565` |
| decoder | `23fea88ee5fe48386a46ab434f1f2427275a44658d9e69b4fb4334d830065b85` |
| history serializer | `6b9507970f1f2f1f0e29a4d020b4eda9c1c2335e9e9465ed3a9e682769d49e1c` |
| state/history policy | `3ce54d029a3b612b6658c9416d7241d62cbfbad1c45025157ba98909a48de2fb` |
| provider-call policy | `1c6d23dcca70cf0e602336a31898e8edbf88a3b4b323f67fb99652d0cc9a7f7d` |

## Synthetic-only validation

Provider-free tests validate ordered multi-step composition, non-first tool
selection, observation-derived next actions, recoverable and invalid-action
feedback, unrecoverable/budget termination, strict output rejection, one-call
semantics, no plan/private reasoning/hidden conversation state, truth redaction,
and deterministic artifact identities. No real provider call, pilot, benchmark
task, or experiment has been run.

The explicit action-observation history makes this recognizably ReAct-style
rather than a renamed Direct adapter, while no planner, extra calls, richer
feedback, evaluator truth, or stronger provider capability has been added.
