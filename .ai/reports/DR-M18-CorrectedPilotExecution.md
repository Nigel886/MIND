# M18 Corrected Pilot Execution — Development Record

## Authorization and Preflight

Issue #192 authorized only the corrected pilot condition m18_v3_comparator_contract_v2 at baseline 4b6d7b64295abfd083cdf7c1b624a340a56bd7e6. Read-only preflight before the first call reported 360 expected, 0 valid, 360 missing, 0 duplicate, 0 invalid, 0 unexpected, corrected formal 0, and the corrected run-ID prefix/schema. Original v3/v2 evidence checks matched their required counts/digests.

## Execution and Resume

The real provider was invoked through the corrected pilot-only runner. An execution-host interruption occurred while the original process continued; a later overlapping resume attempt was rejected by create-only admission, with no overwrite. The original authorized process completed the missing-only universe. This is documented operationally; no code, comparator, runtime, evaluator, provider configuration, budget, or benchmark artifact was changed during execution.

## Disk Reconciliation

The corrected store re-read 360 admitted records and 0 missing. Comparator counts are 90 each, repetitions 72 each, and all 90 paired cells are complete. There are no provider failures, no systematic stop, no corrected formal records, and no modified historical evidence. Canonical corrected digest: f572f10b3e16cfb4a4d66de9afc1a035fa46af292d24a1d0ad7615e2c113e9ff.

## Outcomes

All terminals are answer_submitted. Evaluator outcomes: success 349, interaction_incomplete 11. By comparator: MIND 90 success; Direct 90 success; ReAct 89 success/1 interaction_incomplete; Plan 80 success/10 interaction_incomplete. No ranking or inferential analysis was performed.

No persisted plan_exhausted terminal supplies recurrence evidence for the historical Plan completion defect. The action/request trace is not persisted, so Plan's interaction_incomplete outcomes cannot be attributed to a specific completion phase. No malformed_answer outcome supplies recurrence evidence for answer-type leniency.

## Protocol Boundary

The only reported MIND/Direct nuisance facts are 90/90 observed success for each and paired run-level discordances n10=0, n01=0; repeated-measure dependence is boundary-degenerate/unavailable. These are inputs only to a future frozen mechanical addendum and do not change any #188/#189 choice. Provider transport/token/latency/cache telemetry is unavailable because the corrected record schema does not persist it.

Formal execution remains unauthorized.
