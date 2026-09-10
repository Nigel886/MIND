# M16 Repaired Post-Hoc Execution Summary

## Execution Summary

This is a POST-HOC REPAIRED EVALUATION. It is isolated from, and does not replace, the original M16 formal experiment or #91 analysis.

- FORMAL DEFINITIONS: 960
- TERMINAL COMPLETED: 960
- UNRESOLVED: 0
- INFRASTRUCTURE INVALID: 0
- INTERRUPTED: 0

No new benchmark execution, provider call, or significance test occurred while creating this summary.

## Frozen Identity

- Manifest: `7fb0013b2c93f23b6288604e374c9374477c427a14babbb7556454641f4304bb`
- Provider config: `c074c0e08e6b7be9a93b955a5c5f85da52bb7e9cf83601477ab2e18dad4bc780`
- Repaired MIND request: `b1e64996a00eb237b7c26cab21103cdc68c392384b06e19c06b822f16a74edf5`
- Canonical M13 schema: `f041d3f276051380edb7e3a7d520aec770592efb5a348616999e8d9197c73ccf`
- Direct request: `db59e3676a3fd2c719c7a18eded0db9443c3a83303e3831431b808990ae87078`
- Suite / split: `a450c6fa2955136da5d4db08b892af442ab7be66034412739d91e7cbf076445c` / `a41ca5a326da4f722de1fcca4c7a4b85fcf860767ba1bb0311aa6cc4176aefe3`

## Coverage

All 960 canonical definitions are represented exactly once as terminal records. Attempt and terminal IDs are unique; every record binds to the frozen manifest; persisted order equals the canonical repetition-major, sorted-case, counterbalanced schedule.

- Baselines: MIND 480; Direct 480.
- Repetitions: r1-r5 each 192.
- Families: calculator 480; direct-answer 480.

## Integrity

No active lock exists and result files were unchanged during the final read-only snapshot. There are no infra-invalid or interrupted records.

## Baseline Balance

- MIND SUCCESS: 480 / 480
- DIRECT SUCCESS: 432 / 480
- Direct wrong answer: 48 / 480

The descriptive rates are MIND 100.0% and Direct 90.0%, a raw observed difference of +10.0 percentage points. This is not a significance finding or a superiority claim.

## Failure Taxonomy

MIND records: success 480. Direct records: success 432, wrong_answer 48. No other terminal or resumable category is present.

## Provider Usage

- MIND provider requests / logical calls: 480 / 480
- Direct provider requests / logical calls: 720 / 720

Token, latency, cache, and returned-model telemetry were not persisted; none is inferred here.

## Historical Isolation

The denominator contains no records from the original Gemini, Flash-Lite, invalidated DeepSeek, restart1 DeepSeek, or Diagnostic v1 result namespaces.

- ORIGINAL FORMAL RESULTS INCLUDED: NO
- DIAGNOSTIC V1 RESULTS INCLUDED: NO
- INVALIDATED/HISTORICAL PROVIDER RUNS INCLUDED: NO

## Scientific Freeze Compliance

The authoritative records have one manifest identity, exact canonical order, and no resumptions. Frozen request/schema/provider identities, budgets, repetitions, and completion semantics are unchanged.

- RESULT-DRIVEN TUNING DURING EXECUTION: NO
- REQUEST/PROMPT CHANGED AFTER FIRST RUN: NO
- SCHEMA CHANGED AFTER FIRST RUN: NO
- PROVIDER/MODEL CHANGED: NO
- BUDGETS CHANGED: NO
- ORDERING CHANGED: NO
- REPETITIONS CHANGED: NO

## Result Location

The immutable raw set remains at `evaluation/results/m16_deepseek_repaired_posthoc_v1/`; this delivery does not modify it.

## Statistical Analysis Deferred

A later, explicitly post-hoc analysis may use only this repaired set and approved paired case-clustered methods. It must not merge with #91 or replace historical conclusions.
