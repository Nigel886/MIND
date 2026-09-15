# M18 Direct Tool-Calling Baseline

## Identity and boundary

`m18_direct_tool_calling_v1` is the M18 evaluation-side Direct Tool-Calling
condition. It is multi-decision, stateless, provider-mediated tool calling: on
each eligible evaluation step, it receives only the current public task,
current public feedback, ordered public capabilities, public budget view, and
strict action contract. It makes one provider decision and returns an existing
public evaluation action. It does not execute tools, judge correctness, use
MIND `RuntimeState`, retain a plan, or retain a conversation/action history.

The condition does not modify MIND-Lite v1.1.0 or the frozen M18 MIND policy
condition. It is a synthetic-only baseline contract; no real provider, pilot,
benchmark, or comparative result is involved.

## Input, feedback, and multi-decision semantics

The public task projection has a task identifier, goal description, success
criteria, and sanitized public input. The public feedback projection contains
only the current environment feedback type and payload. Capability descriptors
retain their supplied order and carry only their structural public contract.
Remaining public execution budget is included if shared across conditions.

After a tool response, recoverable failure, or invalid-action feedback, the
external loop may call the adapter again. The next request is constructed afresh
from that current feedback; it contains no earlier provider messages, persistent
plan, ReAct scratchpad, transcript, or MIND runtime analogue. This permits
multi-tool decisions and public correction without turning Direct into a
planner.

Unrecoverable environment feedback and exhausted action budget are compatible
with explicit termination without a provider call. Answer submission terminates
through the existing evaluation action contract. Correctness remains evaluator
owned.

## Strict action contract

The adapter permits exactly one of:

```json
{"action":"answer","answer":<json-value>}
```

```json
{"action":"tool_call","tool_name":"<public-tool-id>","parameters":{}}
```

The decoder rejects aliases, prose-wrapped JSON, duplicate keys, unknown
actions, missing or unexpected fields, non-object parameters, non-finite JSON,
plans, rationale, thoughts, confidence, and hidden metadata. There is no repair
parser, malformed-output retry, self-correction request, fallback model, or
judge call. Unknown tool admission remains environment/registry owned.

## Truth firewall and accounting

The actual provider request sanitizes evaluator-private fields recursively,
including expected answers, ground truth, correct tool/action, difficulty,
cohort routing labels, evaluator success, private judge data, completion
labels, credentials, and hidden reasoning. It carries no semantic hints beyond
the public task, current feedback, tool descriptors, and action contract.

One eligible Direct decision makes exactly one logical provider call. The
adapter records observational-only logical calls, action/decision count,
tool-call count, invalid-action feedback count, and recoverable-failure
feedback count. These counters never enter a provider request or action choice.
Shared provider transport policy and global execution budgets remain a later
common-baseline freeze.

## Frozen artifact identities

| Artifact | SHA-256 |
| --- | --- |
| implementation condition | `25dc1df5a3938e4780af2525783d11a635a543f083c95e8a3bef731937ab3296` |
| prompt/template | `ba7e5f02478471ca064df4b9b9919fba73f0c95b2dd02155b8fe1afc325e60ff` |
| response schema | `ab6a5e8425626177bcb90ae878d89094f5880a304c74999b95b2d31261aee565` |
| strict decoder | `259f39e3480dd97b02d396a0a06dd5b58f9df334f8ebe46c9eee75c4eb0a04c1` |
| input serializer | `f57939f4f3856484d7aa9eda81fc69b442058b5ad0f98585c49fa0be52b9af6b` |
| state/history policy | `1c7010c4e2cbbae57a655cbc35ffb25934aceb66eed55fc0ee50e6f207ff819f` |
| provider-call policy | `30ac116317c0c739d72a2f5f173186cce6a8d5ea0aa636f1a89b0a8bd7ba59a3` |

## Synthetic fidelity validation

Provider-free tests cover answer and general tool actions, non-first distractor
tool selection, current-feedback visibility, observation-derived parameters,
recoverable/invalid feedback leading to a fresh decision, unrecoverable and
budget termination compatibility, strict malformed-output rejection, one-call
accounting, no planner/history/runtime state, truth redaction, and deterministic
artifact identities.

A knowledgeable researcher can recognize this as a capable Direct Tool-Calling
condition because it can continue after legitimate public feedback. It is not
given planner state, ReAct history, evaluator truth, extra calls, or repair
privileges.
