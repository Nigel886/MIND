# M16 Post-Hoc Diagnostic v1 Analysis

## Scope

This is a post-hoc, exploratory analysis of the completed Diagnostic v1
replication in `evaluation/results/m16_mind_failure_diagnostic_v1/`. It does
not replace the frozen DeepSeek formal experiment or its statistical analysis,
and it does not change any historical result, configuration, denominator, or
evaluation judgment. The diagnostic ran MIND-Lite once for each of 96 public
M16 task definitions. It cannot establish the cause of an individual
historical run because historical records lack this telemetry and provider
outcomes are stochastic across executions.

## Integrity

The observed manifest hash,
`2170633e05dd51c0ffd899e8ee9913b8d95e127b29ac2f05abcd93417bbd4899`, matches
the frozen expected identity. There are 96 attempts, 96 unique run IDs, 96
terminal-valid records, zero incomplete records, and 768 telemetry events. See
[`run_integrity.json`](../../evaluation/analysis/m16_mind_failure_diagnostic_v1/run_integrity.json).

## Observed mechanism

Every run has this exact sequence:

```text
provider_request_started
→ provider_response_received
→ provider_decode_failure (malformed_structured_output)
→ admission_failed (admission_failure)
→ terminal_adapter_action (fail / agent_fail)
→ evaluator_invoked
→ terminal_adapter_action (fail / agent_fail)
→ terminal_reason (agent_fail)
```

The sequence appears 96 times in
[`event_sequence_signatures.csv`](../../evaluation/analysis/m16_mind_failure_diagnostic_v1/event_sequence_signatures.csv).
The direct finding is **D. provider-contract incompatibility at the
structured-output interface**: each run received a provider response, could
not decode it under the frozen structured-provider contract, then failed
admission and emitted `agent_fail`.

Raw provider responses were deliberately not persisted. Therefore this does
not identify the precise structural discrepancy, assign provider fault, show a
transport failure or model refusal, or establish a task-level reasoning or
downstream MIND runtime defect.

## Counts and downstream exclusions

| Item | Count |
| --- | ---: |
| Provider request started | 96 |
| Provider response received | 96 |
| Provider decode failure | 96 |
| Admission failed | 96 |
| Terminal adapter action | 192 |
| Evaluator invoked | 96 |
| Terminal reason | 96 |
| `malformed_structured_output` | 96 |
| `admission_failure` | 96 |

No run reached proposal construction or validation, validated-requirement
creation, Meta-Inference selection, integration selection, private session,
policy, projected action, tool interaction, or completion beyond evaluator
termination. Their counts are zero. See
[`stage_counts.csv`](../../evaluation/analysis/m16_mind_failure_diagnostic_v1/stage_counts.csv)
and
[`reason_counts.csv`](../../evaluation/analysis/m16_mind_failure_diagnostic_v1/reason_counts.csv).

Explicit event-level request/model-call counters are null. The 96 response
receipts support an inference of a logical response, but no independent
persisted logical-model-call counter is available.

## Terminal telemetry audit

There are two `terminal_adapter_action` events per run, both `fail / agent_fail`,
and one `terminal_reason` event per run. The actions occur at distinct ordinals
before and after evaluator invocation. Their normalized labels/payloads do not
preserve an emitter identity, which is a telemetry-quality limitation rather
than a second mechanism. Frozen source sequencing associates the first with
adapter-side admission failure and the second with runner-side evaluator
projection. See
[`terminal_event_audit.csv`](../../evaluation/analysis/m16_mind_failure_diagnostic_v1/terminal_event_audit.csv).

## Stratified consistency

Each family-by-difficulty stratum has 16 runs and exactly 16 decode failures,
16 admission failures, and 16 `agent_fail` outcomes. Thus the pattern is
uniform across calculator/direct-answer families and easy/medium/hard labels.
See
[`family_breakdown.csv`](../../evaluation/analysis/m16_mind_failure_diagnostic_v1/family_breakdown.csv)
and
[`difficulty_breakdown.csv`](../../evaluation/analysis/m16_mind_failure_diagnostic_v1/difficulty_breakdown.csv).

## Historical boundary and conclusion

The historical formal MIND-Lite result had 480/480 `agent_fail` outcomes, one
step, zero tool calls, and one provider request/model call per run. This
Diagnostic v1 mechanism is compatible with that visible pattern, because it
ends before policy, tool, or private-session stages. It does **not** prove the
original 480 were caused by malformed structured output.

**M16 DIAGNOSTIC V1 MECHANISM IDENTIFIED.** In this post-hoc replication, all
96 MIND-Lite runs stopped at structured-response decoding and admission before
downstream cognitive execution. Any remediation or new experiment requires a
separate reviewed frozen contract and result namespace; it must not overwrite,
reinterpret, or be pooled with the completed formal experiment.

### Bounded paper statement

In a separate post-hoc Diagnostic v1 replication, observed MIND-Lite failures
uniformly occurred at the structured-provider decoding and admission boundary
before downstream cognitive execution. This evidence is compatible with, but
does not establish the cause of, the earlier formal M16 failures.
