# M16 Repaired Post-Hoc Evaluation v1 Protocol

## Objective

This document freezes a new, post-hoc M16 evaluation that measures the two
frozen baselines after the DeepSeek M13 schema-bearing repair. It is separate
from the completed restart1 formal experiment and does not alter its records,
analysis, or conclusions.

## Post-Hoc Status

The repaired evaluation is authorized for execution only by an explicit future
invocation of its `--execute` entry point. Freezing this protocol is not an
execution authorization.

## Repaired Artifact Identity

The repaired MIND request path is the artifact at repair commit `5b942df`.
Its frozen identities are:

- Repaired MIND request template hash:
  `b1e64996a00eb237b7c26cab21103cdc68c392384b06e19c06b822f16a74edf5`
- MIND JSON-schema hash:
  `f041d3f276051380edb7e3a7d520aec770592efb5a348616999e8d9197c73ccf`
- Direct request template hash:
  `db59e3676a3fd2c719c7a18eded0db9443c3a83303e3831431b808990ae87078`
- DeepSeek provider-configuration hash:
  `c074c0e08e6b7be9a93b955a5c5f85da52bb7e9cf83601477ab2e18dad4bc780`

## Provider Identity

The provider is DeepSeek V4 Flash through the frozen OpenAI-compatible
configuration. Neither provider choice, model, prompts, schemas, budgets, nor
retry policy may be changed by this protocol.

## Suite Identity

The evaluation reuses the immutable 96-case M16 Cohort A suite (suite version
`1.0.0`; suite-generation protocol `1.1.0`) and its frozen identities:

- Suite hash: `a450c6fa2955136da5d4db08b892af442ab7be66034412739d91e7cbf076445c`
- Split hash: `a41ca5a326da4f722de1fcca4c7a4b85fcf860767ba1bb0311aa6cc4176aefe3`
- Execution protocol: `1.2.0`
- Completion semantics: `m16_completion_v2`

## Fair Comparison Design

Both baselines are rerun contemporaneously under the same public task,
environment, judge, budget, retry, and completion contracts:

- `mind_lite_v1`
- `direct_tool_calling`

This is a repaired post-hoc comparison. It must not be merged into the prior
formal denominator, relabel historical outcomes, or be described as the
original formal experiment.

## Schedule

The canonical schedule sorts the 96 public evaluation identifiers, applies
the frozen counterbalanced baseline order, and uses repetitions `0` through
`4`. It therefore defines exactly 960 runs. Run identifiers begin with
`m16-repaired-posthoc-v1:` and include the canonical manifest hash; they cannot
overlap historical run identities.

## Budgets and Completion Semantics

The frozen budget is two public steps, one tool call, and a 240-second wall
timeout. MIND has one logical provider call; Direct has two. Transport retry
uses the unchanged maximum of three attempts. Completion remains
`m16_completion_v2`.

## Manifest and Run-ID Namespace

The result namespace is:

`evaluation/results/m16_deepseek_repaired_posthoc_v1/`

The manifest hash frozen by this protocol is:

`7fb0013b2c93f23b6288604e374c9374477c427a14babbb7556454641f4304bb`

## Result Namespace and Resume Semantics

The result store writes only its own manifest and JSONL attempt records. It
uses the existing lock mechanism and resume semantics: valid terminal agent
outcomes are not rerun, while `provider_infrastructure_invalid_run` and
`interrupted_incomplete` remain resumable.

## Lock Safety and Preflight

The inert module entry point is
`src.evaluation.m16_deepseek_repaired_posthoc_v1_execution`. Importing the
module and ordinary test collection do not construct baselines, contact a
provider, or execute a case. A read-only preflight validates the manifest,
suite and split identities, canonical schedule, result directory, and foreign
record isolation while holding the evaluation lock.

## Execution Not Yet Authorized

The future explicit execution command is:

```powershell
python -m src.evaluation.m16_deepseek_repaired_posthoc_v1_execution --result-dir evaluation/results/m16_deepseek_repaired_posthoc_v1 --execute
```

Execution is not performed by this freeze.

## Historical Exclusions

The following raw historical result namespaces are excluded from inspection,
writing, staging, and statistical aggregation by the repaired result store:

- `evaluation/results/m16/`
- `evaluation/results/m16_flash_lite/`
- `evaluation/results/m16_deepseek_v4_flash/`
- `evaluation/results/m16_deepseek_v4_flash_restart1/`
- `evaluation/results/m16_mind_failure_diagnostic_v1/`

## Statistical Boundary

The eventual analysis may make only repaired post-hoc claims about the new
contemporaneous records. It may not claim that the repair explains an
individual historical failure, overwrite the #90/#91 evidence base, or
establish general intelligence, reasoning superiority, or broader capability.

## Freeze Verification

At protocol-freeze time:

- REAL BENCHMARK RUNS EXECUTED: 0
- REAL BENCHMARK PROVIDER CALLS: 0
- HISTORICAL RESULTS MODIFIED: NO
