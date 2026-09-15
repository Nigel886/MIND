# M18 MIND Evaluation Policy Condition

## Status and boundary

This document freezes the evaluation-side MIND policy condition for M18. It
uses the released MIND-Lite v1.1.0 runtime commit
`99bbe96c7413024f3c76f1c3439c51593770c22e` through its existing public
`PolicyDecisionContext` and `PolicyDecisionEngine` contracts. It does not
modify runtime semantics, execute tools, own session state, or create a
benchmark task or baseline.

The adapter accepts an injected provider edge. No real provider configuration,
credentials, model selection, provider call, pilot, or experiment is frozen or
performed by this change.

## Public input and truth firewall

Each invocation projects only `PolicyDecisionContext.to_dict()` into an
immutable request. That projection contains public task/goal data, a public
runtime view, the latest public environment observation, and the ordered public
`CapabilityDescriptor` set. The adapter never reads raw `Task.input`, private
runtime data, evaluator metadata, or a tool registry.

The upstream public context contract removes evaluator-private fields. The
adapter tests this boundary with source objects containing expected answers,
ground truth, difficulty, correct-tool/action labels, evaluator success, and
private judge metadata; none can reach the provider request.

## Prompt and output contract

The frozen prompt asks for exactly one execution action using supplied public
context only. It permits only `answer` and `tool_call` and prohibits reasoning,
rationale, plans, confidence, benchmark interpretation, and extra fields.

The exact response forms are:

```json
{"action":"answer","answer":<json-value>}
```

```json
{"action":"tool_call","tool_name":"<public-tool-id>","parameters":{}}
```

They map respectively to the existing `Policy` forms `produce_answer` and
`call_tool`. Tool admission remains owned by the existing registry/environment;
the decoder does not make correctness judgments about tool selection.

## Strictness, call, and state semantics

The decoder accepts one complete JSON object only. It rejects prose-wrapped
JSON, aliases, missing or unexpected fields, duplicate keys, unsupported
actions, non-object parameters, and non-finite JSON constants. There is no
repair, output retry, self-correction call, secondary judge, or fallback model.

Every `decide()` invocation makes exactly one logical provider request and
increments observational call accounting once. Each request is built solely
from the current context; no provider history, scratch memory, or persistent
plan is retained. Public recoverable-failure and invalid-action observations
are passed through as typed public context; the adapter does not prescribe a
recovery action.

## Frozen identities

The following SHA-256 identities are hashes of canonical frozen condition
artifacts, not hashes of a provider configuration:

| Artifact | Identity |
| --- | --- |
| condition id | `m18_mind_policy_condition_v1` |
| condition | `96fba00846d0b2b1754e4d5fdab5861f93b0ffbd7e028d61d87bd1d024bad0c8` |
| prompt/template | `95afb91abff24bb097f32d323d011c4abba7954c94b3a24e207e9310ec69f672` |
| response schema | `ab6a5e8425626177bcb90ae878d89094f5880a304c74999b95b2d31261aee565` |
| strict decoder | `a4ccf7ccab573f94bac96a86069b538f3cd8b20beed0c6bb280b05f8f1654d6e` |
| context serializer | `c83275a2f327da53577db4bb5dd31d411e1ada4917e3dc183e4f26aca4766186` |
| one-call policy | `960729b575d00fe6eff815776cecb75ebb97f43838d474450b7109df73dd07d4` |

## Validation and remaining dependency

Synthetic contract validation covers direct answers, general non-calculator
tool selection, deterministic capability ordering, observation-conditioned
requests and parameters, recovery and invalid-action public context,
statelessness, one-call behavior, malformed output rejection, and the actual
provider-boundary truth firewall.

This is not real-provider validation. A later shared provider/baseline freeze
must bind an approved provider configuration and verify comparator fidelity
before any M18 benchmark execution or quality claim.
