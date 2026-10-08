# M20 Prospective Feasibility Readiness Decision

## Decision

**PROSPECTIVE FEASIBILITY OFFLINE READY.**

The implementation admits only the frozen 24-original-work, Fixed-only
generation and uses a synthetic authorization payload solely for offline tests.
Missing, altered, or historical authorization rejects before any transport;
the runner has no live execution implementation.

Canonical persistence, reload/idempotence, ceiling-v2 accounting,
answer-readiness, the authoritative evaluator, and the private
`m20_evaluator_failure_diagnostic_v1` sidecar are bound to the same execution
identity. Diagnostics are generated only after evaluator handoff and cannot
alter the evaluator outcome. Descriptive projection reports outcomes,
diagnostic classes, unknown rate, resources, and exhaustion only.

This decision does not authorize a provider call or create a real feasibility
record. A separate independent prospective authorization audit is required.

## Offline validation

- Focused non-network checks: 8 passed in 0.287s, exit 0.
- Full unittest: 845 tests in 225.625s, exit 0.
- Full pytest: 845 passed, 1 warning in 114.00s, exit 0.
- Diff check: PASS.
