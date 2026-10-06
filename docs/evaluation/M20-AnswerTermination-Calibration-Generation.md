# M20 Answer-Termination Calibration Generation

## Freeze

`m20_calibration_answerterm_v1` is the prospective post-answer-termination
calibration generation. It is non-executable without future independent
authorization.

| Binding | Value |
| --- | --- |
| Manifest | `m20_calibration_manifest_v5` |
| Namespace / path | `m20_calibration_answerterm_v1` / `evaluation/results/m20_calibration_answerterm_v1` |
| Pair/work binding digest | `6c0c08d5aaa4bb27c421aafdff1ab65cffe38f946e5f65726dfadf4cb7cd06a7` |
| Complete manifest digest | `4ddae3f589673a66bd3660354932594ce983b1888ba681b185f8842592352481` |
| Runtime identity | `b72e76c8e1aa8ceb984753ac0cd5ad0542160f56836d06aaa0f7a2357735c336` |
| Answer policy | `m20_public_answer_readiness_v1` |
| Ordering | `m20_pair_counterbalance_v4` / `afc4459efa7e51cea9a69a28869e2ca5ce186a6a8f0f2167863c4dac3afdfd31` |
| Ceiling | `m20_real_ceiling_v2` / `6b4537f6d7e688f30517307cfd2019d99ad20380f76110f8f5515d400bfa08e0` |

## Design

The frozen universe is the unchanged 12-case `m20_real_case_source_v1` source,
with five repetitions per case: 60 unique pairs and 120 unique condition work
items. Adaptive and Fixed each have 60 works; pair ordering is exactly 30
Adaptive-first and 30 Fixed-first. Pair and work identities bind manifest,
provider, ceiling-v2, runtime, answer-readiness policy, and ordering, and do not
overlap historical manifests v2--v4 or diagnostic identities.

## Runtime and scientific contract

The distinct post-#291 runtime binds the persisted envelope normalization, retry
persistence, resource admission, #252 telemetry, canonical evidence integrity,
ceiling-v2 semantics, public readiness, answer/stop-only phase legality, and
evaluator handoff. Offline validation retains normal ACT before readiness and
rejects ACT after readiness for both conditions without leaking evaluator-private
data.

The primary contrast, quality NI margin (0.05), logical-provider interaction
endpoint, resource MRE (-0.25), gatekeeping, paired case-cluster bootstrap,
one-sided alpha (0.025), and joint-power target (0.90) are unchanged.

## Boundary

No provider call or new calibration, pilot, or formal record occurred. Historical
evidence and manifests v2--v4 remain unchanged. Independent authorization is
required before any real calibration execution.
