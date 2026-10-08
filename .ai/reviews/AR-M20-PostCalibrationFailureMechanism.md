# M20 Post-Calibration Failure-Mechanism Review

## Verdict

The manifest-v5 negative calibration is canonically valid, but it is not
feasible as an input to the frozen formal-N procedure. Observable evidence
supports two mechanisms: evaluator-rejected/incorrect answer episodes and
ceiling-exhausted episodes that never submitted an answer. It does not support
a causal attribution between wrong answer payload and unmet evaluator state.

## Disk-only reconciliation

The canonical v5 store reloads without repair: 120 original works in 60 pairs,
60 Adaptive and 60 Fixed assignments, and 30/30 ordering. It has 400 logical
interactions, 400 physical attempts, zero retries, zero provider/infrastructure
failures, zero replacements, 102 `failure_or_incorrect`, 18 `incomplete`, zero
successes, zero observed quality discordance, and nine quality-missing pairs.
These match the #314 record.

## Read-only per-work diagnostic table

A 120-row disk-only table was constructed from every canonical record with
work identity, case, repetition, condition, outcome, lifecycle, provider and
tool attempts, proposal sequence, answer-phase evidence, ceiling status, and
response-diagnostic stage. It contains no raw provider content, evaluator
target, or credential.

| Observable per-work class | Adaptive | Fixed | Interpretation |
| --- | ---: | ---: | --- |
| Answer proposal, evaluator result `failure_or_incorrect` | 51 | 51 | Answer submitted; evaluator handoff follows the frozen runtime path. |
| No answer proposal, `incomplete`, provider/tool at 8 | 9 | 9 | Both ceilings exhausted before answer submission. |
| STOP proposal | 0 | 0 | No stop-based terminal episode. |
| Provider/infrastructure failure, parser rejection, illegal answer-phase ACT | 0 | 0 | Not supported by canonical response/retry evidence. |

All 400 provider responses were admitted (298 legality-stage actions and 102
answer-schema admissions); no rejection category occurred. The 102 answer
episodes entered answer phase and proposed `answer`. The frozen runtime calls
the evaluator synchronously on every answer proposal, and the persisted result
is `failure_or_incorrect`. No answer payload or private target is persisted, so
the evidence cannot distinguish wrong payload from unmet public-state
precondition. That distinction is **unknown**, not inferred.

## Adaptive / Fixed description

Both conditions had 51 evaluator-result failures and nine incompletions, with
no success or quality discordance. Adaptive/FIxed logical interactions were
respectively min/max/mean/variance `1/8/3.350000/5.794167` and
`1/8/3.316667/5.683056`. Their paired difference was 57 zero, two `+2`, and one
`-2` (mean `+0.033333`, variance `0.198889`). This is descriptive calibration
accounting, not confirmatory inference.

## Frozen evaluator/task contract

The evaluator returns success only when the answer exactly equals the private
target and public preconditions for progress, observation, and recovery hold.
Every frozen case retains a reachable reference witness, so no contract
integrity mismatch was observed. V5 establishes answer handoff for 102
episodes and evaluator failure outcomes, but not their causal subtype. The 18
incomplete episodes are separately explained by observable exhaustion.

## Formal-N and historical context

The frozen #221 path produced 60 validated pairs. Fifty-one pairs have
observed `(failure_or_incorrect, failure_or_incorrect)` outcomes; nine are
unavailable due to two incomplete cells. With no observed success and no
quality discordance, the quality-NI nuisance is degenerate. The original
**NO VALID FORMAL N** decision is preserved without imputation or artificial
variation.

This generation is not pooled with #282 (v4 universal ceiling exhaustion),
#289 (interrupted ceiling-v2 generation), or #293 (tiny answer-termination
pipeline diagnostic). #293 shows answer handoff was reachable but was not a
correctness study and cannot repair v5 outcomes.

## Prospective choices

1. Stop and record negative feasibility: immediately supported.
2. Commission a separately authorized task/evaluator-feasibility investigation:
   recommended, provided it does not alter v5.
3. Consider a separately frozen prospective generation only after that
   investigation and fresh independent authorization.

No provider call, calibration rerun, pilot, formal evaluation, frozen-protocol
change, or evaluator change occurred in this review.
