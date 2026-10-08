# M20 Manifest-v5 Real Calibration Execution

## Scope and authorization

This report records the first real-provider calibration under the exact #313
live authorization artifact
`docs/evaluation/M20-AnswerTermination-Calibration-LiveAuthorization.json`.
The production consumer accepted the artifact before transport.  The frozen
generation was `m20_calibration_manifest_v5`, with complete manifest digest
`4ddae3f589673a66bd3660354932594ce983b1888ba681b185f8842592352481`, runtime
identity `b72e76c8e1aa8ceb984753ac0cd5ad0542160f56836d06aaa0f7a2357735c336`,
ordering `m20_pair_counterbalance_v4`, provider hash
`522fcf28714e168ce9854069468c51d3d3cb565404d7bdad3317e4fcc8f199ad`, and
ceiling-v2 digest `6b4537f6d7e688f30517307cfd2019d99ad20380f76110f8f5515d400bfa08e0`.

Credential readiness was checked without disclosure.  The authorized runner
used the frozen DeepSeek `deepseek-flash` contract, 60-second attempt timeout,
and at most two retries after an initial physical attempt.  No pilot or formal
execution was performed.

## Execution and canonical reconciliation

The canonical result path is
`evaluation/results/m20_calibration_answerterm_v1`.  Disk-only reload passed:

| Item | Result |
| --- | ---: |
| Original assignments accounted for | 120 / 120 |
| Frozen pairs accounted for | 60 / 60 |
| Adaptive / Fixed | 60 / 60 |
| Ordering | 30 Adaptive-first / 30 Fixed-first |
| Completed partial lifecycles | 0 |
| Eligible original provider/infrastructure failures | 0 |
| Replacement records | 0 |
| Duplicate/extra original work | 0 |

All records bind the frozen manifest, provider, runtime, ordering, ceiling,
pair/work membership, and namespace.  No cross-generation record was admitted.
Canonical reload, retry/resource reconciliation, linked-replacement validation,
and all 60 calls to `statistical_pair_input` passed.  This is calibration
evidence only, not formal comparative evidence.

## Provider and resource accounting

There were 400 logical provider interactions and 400 physical attempts: zero
retries and zero provider/infrastructure failures.  No ninth provider or tool
attempt was admitted for a saturated execution.

| Condition | Logical interactions min / max / mean / population variance | At provider ceiling |
| --- | --- | ---: |
| Adaptive | 1 / 8 / 3.350000 / 5.794167 | 9 / 60 |
| Fixed | 1 / 8 / 3.316667 / 5.683056 | 9 / 60 |

Tool-attempt ranges were 0--8 for both conditions; reasoning-step ranges were
0--0 (Adaptive) and 0--8 (Fixed); decision-cycle ranges were 1--8 for both.
The paired Adaptive-minus-Fixed logical-interaction differences were 57 zero,
two `+2`, and one `-2`; mean `+0.033333`, population variance `0.198889`.
Cohort means were zero except `resource_constrained` (`+0.2`); its population
variance was `0.36`, and `recovery_replanning` variance was `0.8` (all other
cohort difference variances were zero).

## Outcome, missingness, and #221 projection

All 60 pairs passed the production pair-level projection.  There were 102
observed `failure_or_incorrect` condition outcomes (51 in each condition) and
18 `incomplete` outcomes (nine in each condition).  The nine incomplete pairs
are unavailable performance observations; they are not reclassified as
incorrect and were not imputed.  The remaining 51 pairs were
`failure_or_incorrect` / `failure_or_incorrect`; no observed success and no
paired quality discordance occurred.  There was no infrastructure missingness
and no provider failure replacement pathway to select.

## Nuisance and formal-N decision

The resource difference distribution and permitted cohort heterogeneity above
are estimable.  Quality-success/discordance dependence is not: observed
successes are zero, observed quality discordance is zero, and nine pair cells
are unavailable due to incomplete episodes.  Therefore the frozen quality-NI
calibration input cannot support the required paired case-cluster simulation.

**NO VALID FORMAL N: the calibration supplies no non-degenerate observed
quality-success/discordance nuisance input for the frozen 0.05 quality-NI,
one-sided 0.025, quality-first gatekeeping procedure.**  The -0.25 resource
MRE, paired bootstrap, and joint-power target of at least 0.90 remain frozen;
they were not weakened to manufacture a sample size.

## Preservation and boundary

Historical #250/#282 calibration evidence, prior manifests/ceilings, and
diagnostic v1--v5 namespaces were not modified.  Pilot records remain zero;
formal records remain zero.  No post-hoc protocol, prompt, provider-contract,
manifest, ceiling, evaluator, or endpoint change was made.

## Post-execution validation

Disk-only canonical reconciliation and all 60 production pair projections
passed.  The focused non-network manifest-v5 persistence/lifecycle suite
passed: **13 tests in 6.732s, exit 0**.  No focused check contacted a provider
or wrote the real calibration namespace.
