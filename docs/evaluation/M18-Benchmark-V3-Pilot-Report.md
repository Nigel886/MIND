# M18 Benchmark v3 Pilot Report

## Scope and Evidence Boundary

This report records the completed, authorized `m18_suite_v3` pilot execution.
It is descriptive evidence only. It does not establish comparative task
performance, superiority, inferiority, or a root cause for any terminal
outcome, and it does not rank the comparator conditions. Formal execution
remains unauthorized.

The canonical evidence namespace is
`evaluation/m18/results/v3/pilot/m18_suite_v3`. Its admitted record-set digest
is `196b48cec882fd78492f82e6dc6a031da66203dacd84f62b8142e1f4d0f77e78`.

## Frozen Identities and Execution Baseline

| Field | Value |
| --- | --- |
| Authorized execution baseline (HEAD) | `b282c27e31452ec5c1f6eb7a6b75b11e8bb892c1` |
| Suite freeze source baseline | `b8efbfa24d1cfd01cd6dcb4dab1b1acc5703a03e` |
| Suite identity | `m18_suite_v3` |
| Suite manifest hash | `2f88a22a25118d93b30fa3e399562deb21e0034164c04e3fa30caa3103da0db9` |
| Split hash | `dcab018037617762768c1ee15146335cac986d3a40e2c2bd77a39e1d6edd5ad7` |
| Provider configuration hash | `0f251e14722603e6e39416374467a3598cd72e1d28673e60daf8440dd6115ee2` |
| Environment / evaluator / budget | `m18_environment_v3` / `m18_evaluator_v3` / `m18_budget_v3` |
| Runtime | `m18_shared_execution_runtime_v3` |
| Public action contract | `m18_v3_public_action_contract_v1` |
| Logical run-ID schema | `m18_v3_logical_run_id_v1` |
| In-record provenance identity | `provider_free_v3` / `provider_free_v3` |
| Repository `real_execution_authorized` manifest flag | `false` |

The provider condition is the single frozen M18 shared DeepSeek condition
(`deepseek_api`, `openai_chat_completions`, requested model `deepseek-flash`,
temperature `0`, top-p `1`, max output tokens `512`, thinking disabled,
`json_object` response format, transport retry policy `2` retries with
`0.5`/`1.0` s backoff, 60 s per transport attempt). Provider configuration was
re-verified against the frozen settings before the first real call.

## Exact Authorized Universe

The authorized universe is exactly the frozen pilot split: 18 cases × 4
comparator conditions × 5 repetitions = 360 real pilot runs. Each run is
identified by a domain-separated v3 logical run ID; all 360 expected IDs were
unique, and no formal or historical identity was scheduled.

## Canonical Preflight

The real v3 preflight was run before the first provider call:

| expected | valid | missing | duplicates | invalid | unexpected |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 360 | 0 | 360 | 0 | 0 | 0 |

Pre-execution gates also passed: HEAD matched the authorized runner baseline;
the frozen manifest matched `2f88a22a…` exactly; the canonical v3 pilot
namespace held 0 records; v3 formal records were 0; historical v2 evidence was
unchanged; no persisted systematic provider stop existed; and the live provider
configuration hash matched the frozen authorized configuration.

## Execution and Persistence

Execution used the single authorized entry point
`python -m src.evaluation.m18_v3_pilot_runner --suite m18_suite_v3 --split
pilot --execute` with the real provider. Every completed run was persisted
atomically, re-read from disk, and admitted against the frozen universe before
the next run was scheduled. No code, test, suite artifact, budget, evaluator,
or comparator condition was modified during execution.

## Completion Reconciliation (from disk)

Evidence was reconstructed from the canonical namespace, not from in-memory
counters, by re-running admission over every persisted v3 pilot record.

| expected | valid | missing | duplicates | invalid | unexpected |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 360 | 360 | 0 | 0 | 0 | 0 |

| Comparator | Records |
| --- | ---: |
| MIND-Lite (`mind_lite_v11`) | 90 |
| Direct Tool Calling (`direct_tool_calling`) | 90 |
| ReAct (`react`) | 90 |
| Plan-and-Execute (`plan_and_execute`) | 90 |

| Repetition | Records |
| --- | ---: |
| 1 | 72 |
| 2 | 72 |
| 3 | 72 |
| 4 | 72 |
| 5 | 72 |

| Cohort | Records |
| --- | ---: |
| `multi_step` | 120 |
| `distractor_selection` | 120 |
| `recovery_correction` | 120 |

Difficulty strata are `easy` 120, `medium` 120, and `hard` 120; each of the 18
cases contributes 20 records; failure subtypes are `invalid_action` 60,
`recoverable_failure` 60, and none 240. Paired case/repetition cells: 90
complete, 0 incomplete — every cell contains all four comparator conditions.

## Terminal Outcome Taxonomy

Categories are reported exactly as persisted and are not collapsed. The
`failure_taxonomy` field is derived from the frozen runner rule (a `success`
evaluator outcome has no failure taxonomy; otherwise the terminal class is
retained).

| Terminal | `evaluator_outcome` | `failure_taxonomy` | Count |
| --- | --- | --- | ---: |
| `answer_submitted` | `success` | none | 296 |
| `answer_submitted` | `malformed_answer` | `answer_submitted` | 8 |
| `answer_submitted` | `interaction_incomplete` | `answer_submitted` | 1 |
| `agent_failure` | not evaluated | `agent_failure` | 55 |

The following repository terminal classes had zero records and are reported as
zero rather than omitted: `success` (as a standalone terminal), `wrong_answer`,
`budget_exhausted`, `invalid_action_exhausted`
(`invalid_action_threshold_reached`), `recoverable_failure_exhausted`
(`recoverable_failure_threshold_reached`), `malformed_answer` as a terminal,
`provider_failure`, `agent_internal_failure`, `timeout`,
`unrecoverable_environment_failure`, `replan_limit_reached`, and
`plan_exhausted`.

The frozen v3 harness maps any non-answer, non-declared-failure loop exit to the
default terminal `budget_exhausted`. Because that count is zero, no run
terminated through action-cycle exhaustion, tool-attempt exhaustion, the
invalid-action threshold, or the recoverable-failure threshold.

## Outcomes by Comparator

| Comparator | `answer_submitted` | `agent_failure` | `success` | `malformed_answer` | `interaction_incomplete` |
| --- | ---: | ---: | ---: | ---: | ---: |
| MIND-Lite | 90 | 0 | 82 | 8 | 0 |
| Direct Tool Calling | 90 | 0 | 90 | 0 | 0 |
| ReAct | 90 | 0 | 90 | 0 | 0 |
| Plan-and-Execute | 35 | 55 | 34 | 0 | 1 |

## Outcomes by Cohort, Difficulty, and Repetition

| Cohort | `success` | `malformed_answer` | `interaction_incomplete` | `agent_failure` |
| --- | ---: | ---: | ---: | ---: |
| `multi_step` | 98 | 7 | 1 | 14 |
| `distractor_selection` | 90 | 0 | 0 | 30 |
| `recovery_correction` | 108 | 1 | 0 | 11 |

| Difficulty | `success` | `malformed_answer` | `interaction_incomplete` | `agent_failure` |
| --- | ---: | ---: | ---: | ---: |
| `easy` | 89 | 3 | 1 | 27 |
| `medium` | 102 | 4 | 0 | 14 |
| `hard` | 105 | 1 | 0 | 14 |

| Repetition | `success` | `malformed_answer` | `interaction_incomplete` | `agent_failure` |
| --- | ---: | ---: | ---: | ---: |
| 1 | 60 | 1 | 0 | 11 |
| 2 | 59 | 2 | 1 | 10 |
| 3 | 61 | 0 | 0 | 11 |
| 4 | 58 | 3 | 0 | 11 |
| 5 | 58 | 2 | 0 | 12 |

| Cohort × Comparator | `success` | `malformed_answer` | `interaction_incomplete` | `agent_failure` |
| --- | ---: | ---: | ---: | ---: |
| `multi_step` / MIND-Lite | 23 | 7 | 0 | 0 |
| `multi_step` / Direct | 30 | 0 | 0 | 0 |
| `multi_step` / ReAct | 30 | 0 | 0 | 0 |
| `multi_step` / Plan-and-Execute | 15 | 0 | 1 | 14 |
| `distractor_selection` / MIND-Lite | 30 | 0 | 0 | 0 |
| `distractor_selection` / Direct | 30 | 0 | 0 | 0 |
| `distractor_selection` / ReAct | 30 | 0 | 0 | 0 |
| `distractor_selection` / Plan-and-Execute | 0 | 0 | 0 | 30 |
| `recovery_correction` / MIND-Lite | 29 | 1 | 0 | 0 |
| `recovery_correction` / Direct | 30 | 0 | 0 | 0 |
| `recovery_correction` / ReAct | 30 | 0 | 0 | 0 |
| `recovery_correction` / Plan-and-Execute | 19 | 0 | 0 | 11 |

## Provider Telemetry

| Comparator | Records | Logical provider calls | Persisted transport attempts |
| --- | ---: | ---: | ---: |
| MIND-Lite | 90 | 290 | 290 |
| Direct Tool Calling | 90 | 290 | 290 |
| ReAct | 90 | 290 | 290 |
| Plan-and-Execute | 90 | 354 | 354 |
| **Total** | **360** | **1224** | **1224** |

Persisted logical-call distribution (comparator: calls → records): Direct
`2→30, 3→20, 4→30, 5→10`; MIND-Lite `2→30, 3→20, 4→30, 5→10`; ReAct
`2→30, 3→20, 4→30, 5→10`; Plan-and-Execute `2→30, 3→8, 4→15, 5→12, 6→25`.

Provider failures: `0`. Persisted provider diagnostics: `0`. Persisted
systematic provider stops: `0`. Every run ended through an ordinary action
path, so no structural provider-contract stop and no transient retry-exhaustion
event is recorded.

Telemetry limitations are reported as unavailable rather than zero:

- The persisted `transport_attempts` field is gate-level accounting that
  mirrors `logical_provider_calls` by construction (the shared provider exposes
  no per-call attempt attribute, so each logical call is accounted as one
  transport attempt). Real transport attempt and retry counts are not persisted
  and are therefore unavailable.
- Prompt tokens, completion tokens, cached tokens, total tokens, returned-model
  identity, finish reason, and per-call latency are not persisted by the v3
  result-record schema. Token and latency telemetry is unavailable.
- Provider-native cache telemetry is `not_configured_telemetry_only_if_exposed`
  and no cache telemetry is persisted.

## Operational Incidents

Execution ran as a single uninterrupted pass. There was no provider failure, no
systematic provider stop, no interrupt, no crash, and no resume; no run ID was
replaced, no admitted identity was rerun, and no temporary file was left behind.
The canonical namespace contains exactly 360 record files plus the store
manifest, and the formal namespace is absent.

One regression-gate interaction is recorded here for completeness. The
pre-execution-only assertion `test_historical_evidence_and_v3_real_namespaces_
remain_untouched` asserted that the reserved v3 result namespace contains no
JSON. An authorized pilot execution necessarily creates that namespace, so the
assertion is false after execution. That test was replaced with a read-only,
lifecycle-aware, admission-bound invariant: an absent namespace remains valid
before execution, and an existing one is accepted only when its store manifest
and every record pass the frozen pilot admission contract while the formal
namespace stays empty. This mirrors the treatment already applied to the v2
namespace gate (`c6e8d96`, issue #160). It is an evidence-lifecycle correction,
not an experimental-condition change, and no assertion about observed outcomes
was added, relaxed, or removed.

## Result-Set Digest

The deterministic canonical v3 pilot result-set digest is produced from the
validated admitted-record mechanism as the canonical hash of every admitted
record projection ordered by `run_id`, which makes it independent of
filesystem enumeration order:

`196b48cec882fd78492f82e6dc6a031da66203dacd84f62b8142e1f4d0f77e78`

No canonical record was modified after final reconciliation.

## Historical Integrity

| Historical artifact | Expected | Observed | Status |
| --- | --- | --- | --- |
| M18 v2 canonical record count | 360 | 360 | PASS |
| M18 v2 canonical result-set digest | `50caa6c9afaaf3712e10c5f75f397bb1f8306ebe12b0fd305a8f076a4a79473c` | `50caa6c9afaaf3712e10c5f75f397bb1f8306ebe12b0fd305a8f076a4a79473c` | PASS |
| M18 v2 diagnostic record count | 72 | 72 | PASS |
| M18 v2 diagnostic digest | `2c2f3f52dfde996fba8b91e491297b7fdc7cc2f09425d3ba51595a06a0bbf0e2` | `2c2f3f52dfde996fba8b91e491297b7fdc7cc2f09425d3ba51595a06a0bbf0e2` | PASS |
| M18 v2 formal records | 0 | 0 | PASS |

## v3 Public-Contract Sanity

Bounded to persisted safe evidence: no provider-side rejection, no
provider-contract diagnostic, and no systematic stop are recorded; no run
terminated through the invalid-action or recoverable-failure threshold; and no
run exhausted the action-cycle or tool-attempt budget. MIND-Lite produced an
admissible public action in all 90 of its runs (82 `success`, 8
`malformed_answer`), so no persisted evidence indicates the historical v2
interface defect of stale current context, missing current tool/value context,
display-name aliases accepted as executable IDs, or widespread current-step
action rejection attributable to absent public state.

This sanity statement is bounded by the record schema. The v3 result record
does not persist per-action rejection reasons, action payloads, or rejection
counts, so a direct per-step rejection census cannot be reconstructed from
canonical evidence. The statement rests on the structural termination classes
above and remains `UNKNOWN` at per-action granularity.

## Interpretation Limitations

- The v3 result record persists only provenance, terminal class, evaluator
  outcome, failure taxonomy, provider accounting, and optional provider
  diagnostic. Action sequences, action payloads, per-step environment outcomes,
  and runtime budget counters are not persisted.
- Consequently the specific frozen reason behind each of the 55
  `agent_failure` records (`unrecoverable_environment_failure`,
  `replan_limit_reached`, or `plan_exhausted`) is not recoverable from
  canonical evidence. All 55 belong to Plan-and-Execute (30
  `distractor_selection`, 14 `multi_step`, 11 `recovery_correction`).
- The concentration of `agent_failure` outcomes in Plan-and-Execute, and the 8
  MIND-Lite `malformed_answer` outcomes, require independent post-execution
  validity investigation before any task-performance interpretation. They are
  reported as observations, not explained.
- No statistical test, confidence interval, significance claim, or comparator
  ranking is reported here. Individual runs and repetitions are not treated as
  independent inferential observations.
- Telemetry gaps (transport attempts, retries, tokens, latency, cache) are
  reported as unavailable and were not backfilled.

## Formal and Authorization Boundary

Formal v3 records remain `0`. Formal execution is not authorized and was not
performed. Historical M18 v1, v2, v2 diagnostic, repaired Plan, and M16
evidence are outside this pilot namespace and were not modified.
