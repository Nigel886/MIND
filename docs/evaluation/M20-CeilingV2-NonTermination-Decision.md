# M20 Ceiling-v2 Non-Termination Decision

## Decision

**POLICY/RUNTIME NON-TERMINATION SUPPORTED**

This offline decision diagnoses the completed ceiling-v2 calibration only. It
does not amend the M20 prompt, response parser, schemas, runtime, manifest, or
ceiling; it does not authorize another provider execution.

## Evidence reconstruction

The persisted manifest-v4 namespace reconciles to 120 terminal condition
records and 60 complete pairs. Every record is `incomplete`. Adaptive and Fixed
each have 60 episodes, 480 logical provider interactions, 480 tool attempts,
480 decision cycles, and 480 physical attempts; every episode consumes all
eight provider/tool/cycle slots. There are zero retries and zero provider,
infrastructure, parser, invalid-interaction, partial-lifecycle, or replacement
events.

All 960 response diagnostics are legal, admitted `act` proposals. No diagnostic
records an `answer` proposal. This establishes an ACT-only/no-answer-selection
trajectory for both conditions.

## Reachability and runtime finding

The 12 frozen cases retain successful reference witnesses. Per cohort, the
maximum witness is two actions followed by an answer: 3 total slots for
multi-step, recovery, and resource-constrained cases; 2 for information
acquisition; and 1 for distractor and answer-ready early-stop cases. Thus all
12 witnesses fit within eight cycles.

The condition-neutral environment applies public actions without terminally
answering a case. The evaluator owns the private target and runs only when the
provider emits `ANSWER`. The runtime otherwise solicits the next provider
proposal after every admitted action and returns `incomplete` after the eighth
cycle. It has no automatic answer/termination handoff for an answer-ready state.

The empirical record intentionally excludes exact action identifiers and
pre/post public states. It cannot prove a particular repeated action or state
loop after the fact. It can prove that no answer was selected, all admitted
proposals were actions, and all executions saturated despite witnesses of at
most three slots.

## Decision consequence

The saturation is unsupported as a claim of genuine horizon demand. A
ceiling-v3 amendment is therefore not scientifically justified by this result.
Prospective policy/runtime termination remediation is required before any new
calibration generation can be considered, followed by a new independent
authorization. This calibration remains calibration evidence only, not formal
comparative evidence.

## Boundary

No provider call, pilot record, calibration record, or formal record was
created by this audit. Historical #250/#282 evidence, ceiling v1, manifests
v2/v3, and diagnostic v1-v5 evidence remain unchanged.
