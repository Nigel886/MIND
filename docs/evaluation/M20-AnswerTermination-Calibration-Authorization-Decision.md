# M20 Answer-Termination Calibration Authorization Decision

## Decision

**ANSWER-TERMINATION CALIBRATION EXECUTION BLOCKED.**

## Verified design

The frozen v5 identity rebuilds exactly:

- Protocol / namespace: `m20_calibration_answerterm_v1`
- Manifest: `m20_calibration_manifest_v5`
- Complete digest: `4ddae3f589673a66bd3660354932594ce983b1888ba681b185f8842592352481`
- Pair/work binding digest: `6c0c08d5aaa4bb27c421aafdff1ab65cffe38f946e5f65726dfadf4cb7cd06a7`
- Runtime: `b72e76c8e1aa8ceb984753ac0cd5ad0542160f56836d06aaa0f7a2357735c336`
- Answer readiness: `m20_public_answer_readiness_v1`
- Ordering: `m20_pair_counterbalance_v4` /
  `afc4459efa7e51cea9a69a28869e2ca5ce186a6a8f0f2167863c4dac3afdfd31`

There are 12 cases, five repetitions, 60 pairs, 120 works, and 30/30
counterbalancing. The exact effective v2 allocation object is 16 reasoning, 8
tools, 8 logical provider interactions, and 8 decision cycles. Credential
presence is READY without a network call, and the v5 namespace has zero records.

## Blocking execution gap

There is no manifest-v5 execution runner or v5 authorization verifier. The
existing runner is manifest-v4-only and binds the pre-#291 runtime, so it cannot
prove or execute v5 answer-phase behavior, authorization admission, resource
limits, retry persistence, resume/idempotence, replacements, or canonical v5
persistence. Reusing it would violate the frozen v5 contract.

No live authorization artifact is issued. A separate implementation issue must
add the exact v5 bridge and verifier, after which a new independent audit is
required. No provider, calibration, pilot, or formal action occurred here.
