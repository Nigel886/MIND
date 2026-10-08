# M20 Prospective Evaluator Failure Diagnostics

## Implementation

`src/evaluation/m20_evaluator_failure_diagnostics.py` implements the approved
`m20_evaluator_failure_diagnostic_v1` contract as an explicitly opt-in,
evaluator-private sidecar.  It records only target-match boolean, prerequisite
status, witness status, classification, validation status, schema, and private
evaluator provenance. It never stores targets, witness contents, answer
payloads, hidden reasoning, or evaluator predicates.

The hook is deliberately after the authoritative evaluator handoff. The
existing `M20RealEvaluator.evaluate` success predicate is not modified. The
diagnostic verifies outcome consistency; missing, malformed, unsupported,
conflicting, or missing-witness check state is fail-closed as `unknown_other`.
H1/H2/H3 map respectively to payload, prerequisite, and combined failure;
H4 is `unknown_other`. A successful outcome remains separately classified as
`success`.

## Privacy, persistence, and invariance

The sidecar has no provider, public-state, policy-input, tool-observation, or
retry-message path. It uses a dedicated versioned store, canonical digest,
evaluator-private provenance, identical-replay idempotence, and conflict
rejection. It neither reads nor migrates manifest-v5 evidence and is not
enabled by manifest-v5 execution.

Focused synthetic tests compare each original evaluator result with its
diagnostic-enabled result and require equality. Private target and answer
canaries are absent from serialized sidecar data. Diagnostic collection failure
does not modify the evaluator result.

## Regression recovery

The first captured full unittest completion was trustworthy and revealed an
audit-test defect: the #313 artifact-generation test required environment
variables during ordinary full discovery. The committed #313 matrix/artifact
run used those variables explicitly; ordinary regression does not need to
rewrite them. The test now writes artifacts only when explicit paths are
provided, while always validating the complete 43-case matrix. Earlier
partial logs lacked final aggregates/exit artifacts and are classified as
incomplete; no unproven process-termination cause is asserted.

The recovered final captures are:

- Focused diagnostics plus identifiability and audit coverage: **11 tests in
  2.218s, exit 0**.
- Full unittest: **838 tests in 395.994s, exit 0**.
- Full pytest: **838 passed in 320.52s, exit 0**, with one non-fatal pytest
  cache permission warning.
- `git diff --check`: PASS.

## Boundary

No provider call, calibration rerun, pilot, formal execution, historical
empirical modification, frozen endpoint change, evaluator-success-rule change,
or live authorization occurred.
