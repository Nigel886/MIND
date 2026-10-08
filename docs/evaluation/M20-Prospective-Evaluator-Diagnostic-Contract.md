# M20 Prospective Evaluator Failure Diagnostic Contract

## Purpose

This proposed evaluator-side contract makes future answer failures
identifiable without changing the success rule. It is not implemented by
manifest-v5 and is not provider-visible.

## Versioned schema

`m20_evaluator_failure_diagnostic_v1` records only evaluator-owned summaries:

| Field | Values | Authority |
| --- | --- | --- |
| `answer_matches_private_target` | true / false / absent | private evaluator |
| `prerequisite_status` | pass / fail / absent | private evaluator |
| `witness_status` | present / missing / absent | private evaluator |
| `classification` | success / answer_payload_failure / prerequisite_failure / combined_failure / unknown_other | derived evaluator metadata |
| `validation_status` | complete / malformed / conflicting / missing | diagnostic validator |

The contract must never contain the target, witness contents, submitted answer
payload, hidden reasoning, or private evaluator predicate. It is persisted only
after answer handoff and has no provider or policy read path.

## Classification

- false target match + passing prerequisites: H1 `answer_payload_failure`;
- true target match + failing prerequisites: H2 `prerequisite_failure`;
- both false/failing: H3 `combined_failure`;
- any unavailable, malformed, conflicting, or missing-witness diagnostic: H4
  `unknown_other`.

The existing evaluator outcome remains authoritative for success/failure. This
contract neither changes that outcome nor supplies a replacement, missingness,
or statistical endpoint.
