# M18 v2 Budget-Exhaustion Diagnostic Protocol

## Purpose and boundary

The frozen M18 v2 pilot contains 360 canonical records: 359
`budget_exhausted` and one `malformed_answer`.  Its canonical digest is
`50caa6c9afaaf3712e10c5f75f397bb1f8306ebe12b0fd305a8f076a4a79473c`.
Historical records do not retain the action-cycle count, tool-attempt count,
terminal branch, or public trace.  The specific historical exhaustion dimension
is therefore not recoverable and must not be backfilled or inferred.

This protocol defines separate, non-canonical diagnostic infrastructure.  It
does not change the pilot evidence, benchmark outcome taxonomy, prompts,
provider configuration, public feedback, evaluator, environment, decoder, or
the frozen `m18_budget_v2` six-cycle/four-tool budget.

## Identity and universe

The condition identity is `m18_v2_budget_diagnostic_v1`; its result schema is
`m18_v2_budget_diagnostic_record_v1`.  Each ID binds that condition, a frozen
pilot source case ID, comparator condition, and diagnostic repetition.  It is
derived separately from canonical v2 run IDs.

The initial diagnostic universe is all 18 frozen pilot cases × four
comparators × one repetition: 72 runs.  It is not selected from observed pilot
outcomes.  Results belong only in
`evaluation/m18/results/diagnostic/m18_v2_budget_diagnostic_v1/`; the namespace
is non-canonical, diagnostic-only, and not performance evidence.

## Prospective telemetry

Each record includes action cycles, tool attempts, invalid actions, recoverable
failures, logical provider calls, transport attempts, terminal outcome and
reason, an exact finite exhaustion dimension, and safe last-action data.
Supported dimensions are `action_cycle_limit`, `tool_attempt_limit`,
`logical_provider_call_limit`, `invalid_action_limit`,
`recoverable_failure_limit`, and `none`.

The bounded public trace holds action type, public tool identifier and
parameters, public environment category/progress, and counters after each
step.  It never stores evaluator targets, prompts, provider raw output,
credentials, hidden reasoning, or chain-of-thought.  Token/latency fields are
explicitly null when unavailable.

## Completion analysis and interpretation

The observer may determine after execution, from public state/configuration
only, whether all required public transformations had completed before the
first answer.  It is offline telemetry only; no readiness signal is supplied to
an agent during execution.

The external benchmark outcome remains unchanged.  In particular, a terminal
`budget_exhausted` can have a separate diagnostic exhaustion dimension without
altering evaluator semantics.  Diagnostic outcomes cannot replace the original
pilot results, support comparator ranking, or enter any formal denominator.

## Persistence and execution guard

The diagnostic store uses a dedicated manifest, atomic no-overwrite persistence,
re-read admission, duplicate rejection, and missing-only resume.  Importing or
constructing a plan creates no result directory and makes no provider call.
Execution requires an explicit caller-supplied provider factory.  Issue #162
creates infrastructure and provider-free tests only; it authorizes no
diagnostic, pilot, or formal execution.

## Hardening guarantees

The observer is fail-safe: observer exceptions are suppressed so frozen runtime
actions, counters, state, evaluator outcome, and terminal benchmark outcome
remain authoritative. Exhaustion is a finite typed event, not a reconstruction
from final counters. The telemetry schema is closed; unknown fields and traces
over the six-event action-cycle-derived bound fail admission.

Public completion replay is offline-only. It accepts public case configuration
and a bounded public trace, identifies the first public completion step and
post-completion actions, and never supplies readiness to execution. Diagnostic
provider-contract failures must use the established systematic-stop semantics:
a persistent structural stop blocks later scheduling while transient transport
failures remain ordinary diagnostic results. A stop is not a benchmark result.
