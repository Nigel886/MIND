# M20 Evaluation Question and Allowable Claims

## Status

**SPECIFICATION** — This document freezes the empirical question and claim
boundary for M20, *Adaptive Deliberation Empirical Evaluation*. It creates no
benchmark, comparator adapter, pilot, formal evaluation, provider call, or
statistical result.

## Objective and Primary Research Question

M19 established deterministic architecture for adaptive deliberation and
resource-aware meta-control; it established no empirical performance result.
M20 asks prospectively:

> Under controlled, prospectively defined conditions, does M19 adaptive
> deliberation change resource efficiency while preserving acceptable task
> quality relative to an otherwise comparable fixed-deliberation MIND system?

The wording is neutral: improvement is neither assumed nor required.

## Primary Architectural Contrast

The sole primary contrast is **MIND-Adaptive versus MIND-Fixed**.

- **MIND-Adaptive** is MIND with the frozen M19 adaptive meta-control
  capability admitted under a future fixed execution contract.
- **MIND-Fixed** uses the same underlying MIND architecture wherever feasible,
  task inputs, tool/provider environment, evaluator, execution contract, and
  resource ceilings, but replaces adaptive meta-control with a prospectively
  defined fixed deliberation strategy.

Issue #217 does not define the fixed strategy implementation. Issue #218 must
freeze its executable comparator contract before any empirical run.

Direct, ReAct, and Plan may be included later only as secondary descriptive or
secondary inferential comparators. They cannot replace the primary contrast,
become primary after outcomes are observed, or redefine M20 success.

## Endpoint Hierarchy

The primary scientific framing is **quality-preserving resource efficiency**.

1. **Primary endpoint:** resource efficiency for MIND-Adaptive versus
   MIND-Fixed, conditional on a prospectively frozen task-quality preservation
   (non-inferiority) requirement.
2. **Quality safeguard endpoint:** task quality for the same primary contrast;
   it establishes whether the primary efficiency claim is admissible.
3. **Secondary resource endpoints:** reasoning steps, tool attempts, provider
   interactions, and total decision cycles.
4. **Diagnostic endpoints:** M19 decision counts, resource exhaustion,
   recovery frequency, recoverable failures, and invalid/malformed
   decision/action rate.

Diagnostics are not post-hoc primary endpoints. Token use, monetary/provider
cost, and wall-clock latency remain optional only if a later protocol freezes
stable acquisition semantics, identity, and missingness treatment.

## Claim Classes and Non-Claims

If the prospective design, evaluator, execution contract, and analysis are
valid, M20 may support bounded claims about the evaluated task distribution and
frozen conditions:

- task-quality difference;
- resource-consumption difference;
- quality-preserving efficiency difference; and
- adaptive-control, failure, recovery, or exhaustion behavior difference.

M20 must not automatically claim general intelligence improvement, universally
better reasoning, universal agent superiority, lower real-world cost outside
measured provider conditions, performance outside the evaluated distribution,
causality beyond its randomized/paired design, or superiority over every agent
architecture.

## Quality-Preservation, Pilot, and Statistical Constraints

Before any real pilot, calibration, or formal execution, a later issue must
prospectively freeze a scientifically justified task-quality preservation or
non-inferiority margin. No retrospective margin selection, similarity-based
interpretation, equivalence claim without an equivalence design, or
non-inferiority claim without a valid design is permitted.

Future pilot/calibration data may be used only for prospectively authorized
runtime feasibility, contract debugging, variance/nuisance estimation, or
power-model inputs. It must not select an endpoint/comparator/quality margin,
change an MRE for desired significance, or redefine success from outcomes.

A later statistical protocol must freeze the primary contrast, endpoint,
paired/cluster-aware analysis where relevant, sidedness, alpha, power target,
quality/MRE margin, multiple-testing handling for inferential secondary
contrasts, and machine-reproducible exclusions/missingness rules before
execution.

Formal execution must fail closed if future work cannot establish a valid
evaluator, comparator contract, endpoint, statistical design, or sample size.
No formal execution is a scientifically valid outcome.

## Relationship to M18 and M19

M18 evidence is historical and independent. Its lessons—unreachable evaluator
success, missing public state, comparator mismatch, provenance mismatch,
post-hoc repair risk, pilot misuse, and no-N fail-closed closure—are M20 design
constraints, not M20 results. M19 is architectural capability evidence only.
M20 is the first milestone intended to evaluate empirical effects of adaptive
deliberation; M18 records may be contextual only unless a later prospective
design explicitly permits a historical descriptive comparison.

## Downstream Boundaries

| Issue | Frozen future responsibility |
| --- | --- |
| #218 | Experimental Conditions and Comparator Contracts |
| #219 | Evaluation Suite and Environment |
| #220 | Resource and Cost Metrics |
| #221 | Statistical Analysis and Power Protocol |
| #222 | Evaluation Harness |
| #223 | Independent Readiness Audit |
| #224 | Prospective Pilot / Calibration |
| #225 | Pilot Audit and Formal Progression Decision |
| #226 | Formal Evaluation Execution |
| #227 | Independent Statistical Audit |
| #228 | M20 Milestone Closure |

None of these is implemented or authorized by Issue #217.
