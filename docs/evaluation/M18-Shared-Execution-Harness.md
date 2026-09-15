# M18 Shared Execution Harness

## Scope

The M18 shared harness is architecture-neutral orchestration infrastructure.
It does not choose agent actions or normalize an architecture's private state.
It has been validated only through scripted synthetic dry runs. **NO REAL
PROVIDER PILOT OR FORMAL EXECUTION PERFORMED.**

## Flow and Firewall

The harness alone holds an `M18Case` and its evaluator fixture. Before every
adapter call it derives the `M18PublicCase` task/tool/environment projection.
It passes only that projection and public environment feedback to MIND-Lite,
Direct Tool-Calling, ReAct, or Plan-and-Execute. Difficulty, target answer,
target state, correct tool/action, evaluator rules, private schedules, and
benchmark metadata never cross an adapter boundary.

`M18DeterministicEnvironment` receives the public action and the case only at
the orchestration boundary. Its output is converted into public evaluator
feedback. After `answer_submitted`, the external evaluator alone compares the
answer to private truth. Runtime terminal state and evaluator outcome are
separate record fields.

## Shared Provider and Adapters

All bindings use the #118 provider configuration hash
`0f251e14722603e6e39416374467a3598cd72e1d28673e60daf8440dd6115ee2`.
The harness counts logical provider calls separately from transport attempts;
it neither retries model output nor provides a fallback model/parser. Thin
bindings preserve MIND policy, Direct statelessness, ReAct public history, and
Plan-and-Execute's one-replan limit.

## #120 Pre-Pilot Fairness Remediation

The initial #117 harness recorded the shared provider hash but permitted
arbitrary provider injection into bindings. Independent Issue #119 therefore
correctly returned `BLOCKED ON PROVIDER FAIRNESS`. This remediation retains
synthetic dependency injection only in explicit `synthetic` mode. `frozen`
mode fails closed unless supplied an exact #118 `M18SharedProviderClient` whose
full canonical configuration and recomputed hash match the frozen provider
condition. Its single client is then bound to MIND, Direct, ReAct, and both
Plan-and-Execute roles.

The v2 harness also validates every record against the active manifest before
atomic persistence: run membership/ID, suite, provider hash, system artifact,
repetition, harness identity, result schema, and experiment namespace must all
match. The MIND binding now creates one `CognitiveAgentSession` per run and
sends each public environment observation through `session.observe`; a second
repetition creates a fresh session. No runtime state crosses runs.

## Runtime, Failure, and Budget Semantics

Neutral runtime terminals are `answer_submitted`, `budget_exhausted`,
`invalid_action_exhausted`, `unrecoverable_environment_failure`,
`agent_internal_failure`, `provider_failure`, and `infrastructure_invalid`.
Only actual transport/artifact/evaluator/persistence faults are infrastructure
invalid. Malformed model output, wrong tools, wrong answers, and exhausted
budgets are ordinary experiment outcomes.

Records preserve decision cycles, logical provider calls, transport attempts,
tool calls, invalid actions, recoverable failures, and replans. Plan-and-
Execute retains its frozen maximum of one replan. Token, latency, and returned
model telemetry remain nullable when a provider does not expose them.

## Scheduling, Identity, and Results

Run IDs hash suite version, case ID, system condition, repetition, provider
configuration hash, and harness version. The formal schedule uses exactly five
independent repetitions and a deterministic balanced per-case/repetition
rotation, preventing a system-blocked order. The frozen maximum manifest is:

`162 cases × 4 systems × 5 repetitions = 3240 run identities`.

The tracked execution-harness manifest freezes suite, provider, scheduler,
failure-mapping, result-schema, persistence, and harness identities. Per-run
JSON persistence is atomic; a second completed ID is rejected. Resume validates
the stored manifest and schedules only missing IDs. Any identity mismatch is
configuration drift and stops execution.

## Raw Artifact Policy and Synthetic Validation

Permitted audit evidence is public action/observation/environment output and
provider telemetry where exposed. Secrets, private evaluator data, prompts,
and hidden reasoning are forbidden. Scripted synthetic dry runs validated all
four adapters through the same harness, public/private firewall, neutral
failure mapping, deterministic scheduling, duplicate rejection, and resume
reconciliation. They do not compare performance.
