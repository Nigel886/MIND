# M16 Post-Hoc MIND Failure Diagnostic v1 Protocol

## Purpose and status

Diagnostic v1 is a post-hoc, exploratory replication for failure-mechanism
localization only. It is not a performance estimate and does not replace the
completed M16 formal experiment or the #91 analysis.

At this freeze point:

- REAL DIAGNOSTIC RUNS EXECUTED: 0
- REAL PROVIDER CALLS: 0
- FORMAL RUNS EXECUTED: 0
- FORMAL RESULTS MODIFIED: NO
- RESULT-DRIVEN TUNING: NO

## Frozen identity

| Field | Value |
| --- | --- |
| Diagnostic protocol | `m16-post-hoc-diagnostic-v1` |
| Diagnostic manifest hash | `4fdaa47b47f621662953531af3a0dc703d6ac46550152b49cf8d421800144c74` |
| Instrumentation commit | `cfbcdf2` |
| Telemetry schema | `m16-mind-diagnostic-stage-v1` (24 stages) |
| Reason taxonomy | `m16-mind-diagnostic-reason-v1` (13 reasons) |
| Provider behavior hash | `c074c0e08e6b7be9a93b955a5c5f85da52bb7e9cf83601477ab2e18dad4bc780` |
| Provider | DeepSeek API, `deepseek-v4-flash` |
| Documented model version | `DeepSeek-V4-Flash-0731` |
| Accepted observed alias | `deepseek-flash` |
| Sampling and response mode | thinking disabled; JSON object; temperature 0; top_p 1; maximum output 512 |
| MIND prompt hash | `e33084d5605dd30bd343f2392680d3450c9c7642ac99c4d3773dfe38b852bd39` |
| MIND schema hash | `f041d3f276051380edb7e3a7d520aec770592efb5a348616999e8d9197c73ccf` |
| Calculator public schema hash | `a45d98247a7d8ebd78255efe7a6ce4224d19df946e66a35cb41b382de23b2cb7` |
| Source suite hash | `a450c6fa2955136da5d4db08b892af442ab7be66034412739d91e7cbf076445c` |
| Source split hash | `a41ca5a326da4f722de1fcca4c7a4b85fcf860767ba1bb0311aa6cc4176aefe3` |

The provider behavior hash is the byte hash of the existing DeepSeek provider
configuration. The diagnostic manifest hash is distinct because it contains
post-hoc purpose, storage, scheduling, and claim-boundary metadata.

## Frozen schedule and isolation

Diagnostic v1 uses the public M16 source task set solely for a post-hoc
replication: 96 cases, the `mind_lite_v1` baseline only, one repetition, and
96 expected runs in ascending public-case-ID order. Each run ID has the
isolated form `m16diag:v1:<diagnostic_manifest_hash>:<public_case_id>:mind_lite_v1:r1`.
It cannot overlap the normal `m16:` formal namespace.

The sole permitted result namespace is
`evaluation/results/m16_mind_failure_diagnostic_v1/`. The historical Gemini
and DeepSeek directories are excluded from reads for completion, resume,
denominators, and writes. No historical result is changed or reclassified.

## Telemetry and privacy boundary

Telemetry records ordered stage names, normalized reason codes, selected public
identifiers, public action/tool labels, counters, session phase, terminal
category, and a fixed scalar metadata allow-list. It never persists raw
provider text, prompts, credentials, private truth, RuntimeState, Belief, or
chain-of-thought.

When a provider response is received but deterministic structured decoding
fails, the frozen observation sequence is:

`provider_request_started` → `provider_response_received` →
`provider_decode_failure`.

## Storage, resume, and ownership

The manifest-bound diagnostic store writes separate append-only attempt and
stage-event JSONL files. A terminal valid diagnostic outcome is immutable and
never rerun because it is unfavorable. Provider-infrastructure-invalid and
interrupted/incomplete attempts are resumable. Events belong to one immutable
attempt ID; a resumed attempt receives a new ID and never merges its events
with a partial attempt.

One process-level lock is acquired before store initialization, schedule
traversal, Agent/provider construction, or any diagnostic execution. A second
owner performs zero work. Stale-lock recovery is explicit and verified; it is
never automatic.

## Guarded future execution

The inert module is
`src.evaluation.m16_mind_failure_diagnostic_v1_execution`. Importing it does
not execute a provider, Agent, or result write. Its preflight validates the
manifest, schemas, suite/split identity, 96 unique run IDs, MIND-only baseline,
isolated namespace, and resume consistency before provider construction.

The future explicit command is:

```text
python -m src.evaluation.m16_mind_failure_diagnostic_v1_execution --result-dir evaluation/results/m16_mind_failure_diagnostic_v1 --execute
```

This command has not been run during the freeze.

## Claim boundary

Allowed future language is: “In the post-hoc diagnostic replication, failures
were observed at stage X.” An observed mechanism may be compatible with the
historical one-step/zero-tool pattern. Diagnostic v1 cannot establish that the
original 480 failures were caused by X without separate historical evidence.
