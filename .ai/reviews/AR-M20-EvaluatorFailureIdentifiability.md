# M20 Evaluator Failure Identifiability Review

## Verdict

**PROSPECTIVE DIAGNOSTIC CONTRACT FEASIBLE.** This is a design and offline
feasibility result only. It does not authorize any provider call, calibration
rerun, manifest, or live experiment.

## Frozen evidence

Read-only canonical reload confirms the frozen v5 result: 120 original works,
60 pairs, 60 Adaptive and 60 Fixed assignments, 102 evaluator-result failures,
18 incomplete episodes, zero successes, zero quality discordance, and nine
quality-missing pairs. The existing `NO VALID FORMAL N` decision is preserved.
No empirical record was edited or relabelled.

## Actual evaluator boundary

The agent sees only public task state and action legality. An answer proposal
is passed to the private evaluator. Success requires all of:

1. answer exactly equals the private target;
2. public progress meets `required_progress`;
3. observation is present when required; and
4. recovery is present when required.

Private targets and witnesses have no provider-visible path. The current
evaluator returns the same `failure_or_incorrect` result for an invalid answer
with valid prerequisites, valid answer with invalid prerequisites, and both
invalid. Thus current v5 evidence cannot distinguish H1/H2/H3.

## Identifiability matrix

| Hypothesis | Required observation | Current evidence | Authority / visibility | Verdict |
| --- | --- | --- | --- | --- |
| H1 payload failure | private target-equality boolean; prerequisites pass | outcome only | evaluator-private | UNKNOWN retrospectively; prospectively observable |
| H2 prerequisite failure | per-prerequisite pass/fail | outcome and public trace only | evaluator-private summary | UNKNOWN retrospectively; prospectively observable |
| H3 combined failure | both signals | outcome only | evaluator-private | UNKNOWN retrospectively; prospectively observable |
| H4 unknown/other | diagnostic completeness/conflict status | absent | evaluator-private | UNKNOWN retrospectively; prospectively observable |

## Proposed contract

Version `m20_evaluator_failure_diagnostic_v1` separately from all v5 outcome
identities. On evaluator handoff only, persist evaluator-owned metadata:

- `answer_matches_private_target`: boolean or absent;
- `prerequisite_status`: pass/fail/absent (without exposing target or witness);
- `witness_status`: present/missing/absent;
- `classification`: `success`, `answer_payload_failure`,
  `prerequisite_failure`, `combined_failure`, or `unknown_other`;
- diagnostic schema/version and completeness/validation status.

This metadata is written after provider response admission, is not returned to
the provider, is not an agent-policy input, and does not alter evaluator
success decisions. Missing, malformed, conflicting, or missing-witness
diagnostics must produce `unknown_other`, never a fabricated subtype.

## Offline synthetic validation

`tests/test_m20_evaluator_identifiability_feasibility.py` passed **3 tests in
0.003s, exit 0**. It verified actual outcome collapse for valid/invalid answer
and prerequisite combinations; future H1/H2/H3 separation; H4 handling for
missing data; malformed/conflicting/missing-witness fail-closed handling; and
the absence of private target or answer payload in the diagnostic object.

## Measurement and future-study limits

The proposed metadata does not change quality success, resource accounting,
replacement eligibility, missingness, agent actions, policy inputs,
provider-visible observations, quality NI margin, resource MRE, or #221
endpoints. It requires a separate prospective implementation and independent
authorization. That future study must freeze its own evaluator-diagnostic
schema, provenance, persistence/privacy review, test plan, authorization, and
analysis plan; it may not modify or pool v5 evidence.
