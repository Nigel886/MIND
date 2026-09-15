# MIND-Lite v1.1 Release Validation

## Release Identity

- Release: **MIND-Lite v1.1.0**
- Planned tag: `v1.1.0`
- Tag status: **NOT YET CREATED**
- Original blocked candidate: `4c13920e5fdd4107a059f2670727503bb3916302`.
- Original independent readiness verdict: **BLOCKED ON TRUTH LEAKAGE**.
- Original candidate status: **NEVER TAGGED OR RELEASED**.
- Replacement candidate: this truth-firewall remediation commit supersedes the original candidate; its exact immutable identity is recorded after commit creation.

## Scope

v1.1 adds an opt-in, provider-independent cognitive runtime path to the v1.0 artifact. It does not change the v1.0 `GoalDirectedAgent.run()` path, M16 artifacts, or historical evaluation results.

## Architecture Additions

- #101: immutable `CapabilityDescriptor`, generalized JSON-safe `tool_call`, and registry-owned validation.
- #102: immutable, sanitized `PolicyDecisionContext` and provider-independent policy protocol.
- #103: typed immutable `EnvironmentOutcome` categories/reasons and public outcome observations.
- #104: bounded `CognitiveExecutionController`, execution budgets/results, and environment protocol.

## Integrated Runtime Path

```text
Task -> sanitized PolicyDecisionContext -> policy -> public action
-> CognitiveExecutionController -> external environment -> EnvironmentOutcome
-> agent_environment Observation -> RuntimeController inference/new immutable state
-> fresh PolicyDecisionContext -> next policy decision
```

The controller orchestrates only. Policies choose semantic actions; environments own execution/admission; evaluators own correctness.

## Supported Capability Matrix

| Capability | Status |
| --- | --- |
| Generalized tool selection | SUPPORTED |
| JSON-safe arbitrary parameters | SUPPORTED |
| Observation-conditioned decision | SUPPORTED |
| Dependent multi-tool composition | SUPPORTED |
| Observation-derived parameterization | SUPPORTED |
| Recoverable failure progression | SUPPORTED |
| Invalid-action correction | SUPPORTED |
| Unrecoverable termination | SUPPORTED |
| Bounded multi-cycle execution | SUPPORTED |
| Immutable state history | SUPPORTED |

## E2E Validation Scenarios

Provider-free deterministic release validation covers:

- Tool A -> public X -> Tool B(X) -> result -> submitted answer.
- Three-stage public observation progression across Tool A, Tool B, Tool C, and answer submission.
- Recoverable typed failure admitted into state, then policy-selected alternate action and answer.
- Invalid-action outcome admitted into state, then bounded policy correction and answer.
- Unrecoverable outcome admitted into state, then no later policy invocation.
- Exact `max_cycles`, `max_tool_calls`, `max_invalid_actions`, and `max_recoverable_failures` exhaustion.
- Terminal direct answer submission without an environment/evaluator correctness claim.

## Execution Budgets

`CognitiveExecutionBudget` supplies finite deterministic limits. `max_cycles` counts each policy/action unit. `max_tool_calls` counts submitted tool calls. Invalid-action and recoverable-failure counters increment after their typed observations are admitted. Reaching the final permitted invalid/recoverable count prevents another policy invocation. Optional specialized limits default to `max_cycles`; limits never reset or expand.

## Termination Semantics

- `ANSWER_SUBMITTED`: policy submitted an answer; it is **not** evaluator-confirmed success.
- `UNRECOVERABLE_ENVIRONMENT_FAILURE`: public outcome was admitted, then the controller stopped.
- `BUDGET_EXHAUSTED`: a finite architecture-level limit prevented continuation.
- `POLICY_FAILURE` / `ENVIRONMENT_FAILURE`: compact runtime failures without exception internals.

## Truth Leakage Audit

The original candidate's `CapabilityDescriptor.parameter_schema` accepted unrestricted JSON metadata except for a partial blacklist.  Independent readiness review found that this allowed evaluator-private `difficulty` metadata to reach generalized policy context.  The remediation replaces that admission path with an explicit recursive public input-schema allowlist; unknown schema fields are rejected at descriptor construction and cannot enter policy context.

Generalized policy context and public outcomes exclude expected answers, ground truth, correct tools/actions, evaluator success, benchmark completion state, difficulty, private judge metadata, prompts, credentials, hidden reasoning, and exception/traceback data. The controller does not import completion evaluation or inspect evaluator truth.

## Immutability Validation

Task, observation, capability, outcome, context, result, and budget payloads are detached/frozen. Each admitted outcome is passed through canonical inference before policy re-invocation or termination. Historical RuntimeState and Belief instances remain unchanged.

## Backward Compatibility

v1.1 is opt-in. Direct answer, calculator behavior, `GoalDirectedAgent.run()`, manual `CognitiveAgentSession` lifecycle, `RuntimeController`, #101–#103 contracts, and M16 evaluation contracts remain regression-tested and unchanged.

## Test Evidence

- Focused v1.1/runtime/truth-firewall validation: **35 passed**.
- Full `python -m unittest` regression suite: **484 passed**.
- Full `pytest` regression suite: **484 passed**.
- `git diff --check`: **passed**.

## Known Limitations

- No production provider-backed advanced policy.
- No persistent planner, ReAct, or Plan-and-Execute implementation.
- No dynamic capability-set mutation within a session.
- No long-term memory capability.
- No M18 comparative benchmark evidence.
- No claim of general agent superiority or task-quality improvement.
- Recovery is selected by a supplied policy; the controller does not plan recovery.

## M16 Relationship

M16 evaluated the v1.0 / repaired integration setting. It is not v1.1 evidence and is not reinterpreted by this release validation.

## M18 Boundary

M18 must evaluate the frozen v1.1.0 artifact separately. New task suites, provider-backed policies, ReAct, Plan-and-Execute, and external comparisons are outside this release-freeze scope.
