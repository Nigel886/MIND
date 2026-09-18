# M18 Statistical Protocol Freeze — Development Report

## Status

**PARTIALLY FROZEN; BLOCKED ON A PROSPECTIVE ANALYSIS-POPULATION AND
FORMAL-PROGRESSION SPECIFICATION.**  This is a specification-only,
provider-free recovery of Issue #188.  No comparator, runtime, evaluator,
budget, suite, historical record, provider setting, or result was changed.

The target report did not exist at recovery.  The most recent directly relevant
state consists of the completed immutable v3 pilot, its independent evidence
audit, and the subsequently implemented, domain-separated corrected comparator
condition.  The corrected condition has no pilot or formal records and its
module deliberately exposes no execution entry point.

## Context

The original v3 pilot is a complete, immutable 18-case universe: 18 cases × 4
comparators × 5 repetitions = 360 admitted records, with digest
`196b48cec882fd78492f82e6dc6a031da66203dacd84f62b8142e1f4d0f77e78`.
Every one of the 90 case × repetition cells contains all four comparators.
That pilot is descriptive evidence only.  Its report expressly makes no
statistical test, confidence interval, significance claim, or comparator
ranking, and expressly says that repetitions are not independent inferential
observations.

The corrected future condition is
`m18_v3_comparator_contract_v2`.  It has a separate logical-ID domain,
provenance schema, pilot namespace, and formal namespace, so corrected evidence
cannot be pooled with the original v3 pilot.  This correction fixes Plan's
missing post-final-tool answer opportunity and imposes a strict integer-answer
decoder for all four comparators; it preserves cases, environment, evaluator,
provider configuration, and budgets.  It does not itself authorize a corrected
pilot or formal run.

## Protocol Sections Already Frozen

| Section | Decision | Repository basis | Status |
| --- | --- | --- | --- |
| Experimental pairing | Compare matched conditions within the same case; retain all five repetitions together. | `AR-M18-AdvancedAgentCapabilityEvaluationProtocol.md` requires five repetitions and its statistical section aggregates them by case; the v3 pilot has 90/90 complete paired cells. | Final as a design principle; applies prospectively, not retrospectively to make the original pilot confirmatory. |
| Analysis unit | The inferential unit is the **case cluster**, with each comparator's five outcomes represented as that case's success proportion. Run rows and individual repetitions are not independent samples. | The M18 review's statistical section; v3 pilot report's explicit non-independence boundary; established M16 methodology is corroborative only. | Final for the defined future eligible analysis population. |
| Candidate primary endpoint | Evaluator-owned task-completion success, not self-declared completion or a composite score. | M18 review's primary question/evaluator contract and v3 suite's evaluator-owned success predicate. | Conditional: exact binary mapping for every corrected runner terminal/infrastructure class still needs to be bound in the corrected execution/result specification. |
| Primary contrast | MIND-Lite versus Direct Tool Calling on the prespecified eligible A/E subset. | M18 review, “Primary Research Question” and “Statistical Analysis.” | Conditional: `A/E` is not bound to a machine-identifiable v3 subset. |
| Primary effect and inference | Mean paired case-level success-proportion difference; 95% paired case-cluster bootstrap (10,000 draws) and two-sided within-case complete-vector permutation test (100,000 draws). | M18 review, “Statistical Analysis.” | Conditional: the required separate frozen resampling seeds and the eligible case set are absent. |
| Secondary contrasts and multiplicity | MIND vs ReAct and MIND vs Plan-and-Execute are secondary; if all three primary-cohort p-values are reported, use Holm adjustment. Cohort/difficulty/subfamily analyses are exploratory. | M18 review, “Multiplicity.” | Conditional on the same primary-cohort definition and on an explicit statement whether secondary inferential p-values will be produced. |
| Repetition sensitivity | Repetition-specific rates may be descriptive only; no independent repetition-wise tests. | Case-cluster requirement and v3 pilot non-independence statement. | Final. |
| Failure handling principle | Agent-originated wrong/invalid/incomplete/failure/budget outcomes remain denominator outcomes. Only verified provider outage/transport failure, corrupted task, environment/evaluator implementation error, or missing declared tool response may be infrastructure-invalid and rerun under a frozen resume policy. | M18 review, “Failure Taxonomy” and “Infrastructure Invalidity”; pilot runner's typed stop/retry boundary. | Conditional: current corrected record schema does not yet preserve the classification needed to apply this rule prospectively. |
| Evidence separation | Original v3 evidence remains historical and must not be aggregated as corrected-condition repetitions; v2 and M16 evidence are also out of scope. | Corrected comparator contract and v3 pilot report/audit. | Final. |

## Blocker Analysis

### Exact blocked protocol area

The blocked area is the **confirmatory analysis population and its resulting
formal-progression criteria**.  It is a **repository/specification
inconsistency**, with consequences for the endpoint denominator, primary
contrast, inference implementation, multiplicity family, and authorization.
It is both a **scientific-design blocker** and a
**missing-repository-specification blocker**; it is not merely an
implementation or documentation defect.

### Exact requirement that cannot be frozen

Issue #188 cannot freeze a reproducible confirmatory estimand for a future
corrected M18 run because the repository does not identify which frozen v3
cases constitute the review's “prespecified eligible A/E subset,” nor does it
prospectively justify the actual 162-case formal split against the review's
required final sample-size justification.  A runner cannot deterministically
derive the primary denominator, paired clusters, contrast family, or required
resampling inputs from the current artifacts without making a new design
choice.

### Available evidence/specification

- The M18 architecture review supplies a scientifically coherent method:
  MIND versus Direct, five repetitions aggregated to case-level proportions,
  paired cluster bootstrap, complete-vector within-case permutation, and Holm
  adjustment if three primary-cohort p-values are reported.
- It defines A/E as dependent multi-step composition/stateful goal progression
  and separately identifies selection-under-distractors and recovery/correction
  constructs.  It also says ineligible conditions are excluded from the primary
  denominator.
- The v3 suite instead uses `multi_step`, `distractor_selection`, and
  `recovery_correction` cohorts, 18 pilot and 162 formal cases, and runs every
  one of four comparators on every case.  No artifact binds these labels to A/E
  eligibility, identifies a primary formal subset, or marks any condition
  capability-boundary for that subset.
- The review recommends 32 held-out case clusters per cohort × difficulty
  (288 total) and requires the final count to be prospectively justified from a
  registered minimum detectable paired effect and discordance assumption.  No
  such justification exists for v3's 162 formal cases or for its prospective
  A/E subset.
- The v3 pilot audit independently found no M18 pilot-specific analysis plan,
  test, effect summary, or frozen resampling seed, and forbade post-hoc paired
  analysis.  Its conclusion remains applicable to the original v3 evidence.
- The corrected-contract code makes future evidence isolated, but it contains
  no corrected execution runner or formal analysis manifest.  Its narrow result
  record has terminal/evaluator outcome but not the complete failure/infrastructure
  classification required to apply the invalid-run rule without an additional
  prospective record contract.

### Missing or contradictory information

1. There is no explicit mapping from v3's `multi_step` (or any combination of
   v3 cohorts) to the review's A/E eligible primary subset.  Treating
   `multi_step` as A/E is plausible but not stated; including all three cohorts
   contradicts the review's eligibility boundary.
2. There is no registered minimum detectable effect, discordance assumption, or
   owner-approved rationale establishing that 162 formal cases—and the smaller
   primary subset implied by A/E—are adequate for the intended confirmatory
   claim.
3. No numerical permutation/bootstrap seeds are frozen for M18.  Choosing them
   now would be a new statistical specification, not recovery of an existing
   one.
4. The current v3 terminal taxonomy includes `answer_submitted` with evaluator
   outcomes such as `success`, `malformed_answer`, and
   `interaction_incomplete`, plus `agent_failure`; the corrected future record
   does not yet persist a closed distinction between comparator outcome and a
   verified infrastructure-invalid run.  Thus the proposed endpoint denominator
   and rerun exclusion rule cannot be mechanically enforced as written.
5. The v3 pilot's Plan defect and shared answer-type leniency were found after
   that pilot.  Corrected runs must be new evidence, so those historical data
   cannot be used to choose, power, or retrospectively validate a corrected
   confirmatory analysis.

### Why a choice now would be unjustified

Selecting `multi_step` as A/E, accepting 162 cases as adequate, inventing
resampling seeds, or collapsing provider/infrastructure failures into a
denominator would silently redefine the study after the suite freeze.  Those
choices alter what population the primary effect estimates and whether its
uncertainty and p-value support formal progression.  The repository's
specification-driven conventions require owner-approved architecture/protocol
decisions rather than inference from similarly named cohort labels or reuse of
M16 values.

### Blocker classification

- **Primary classification:** repository/specification inconsistency.
- **Affected categories:** endpoint definition, inference design,
  multiplicity policy, repeated-measures handling, missing/failure policy, and
  formal-progression criteria.
- **Not blocked by:** missing pilot cells, a need to call a provider, or a
  comparator/runtime/evaluator/budget implementation change.

## Evidence / Repository Basis

| Artifact | Relevant fact |
| --- | --- |
| `.ai/reviews/AR-M18-AdvancedAgentCapabilityEvaluationProtocol.md` | Defines the A/E-only MIND-vs-Direct primary comparison, case-level aggregation, bootstrap/permutation design, secondary hierarchy, Holm rule, invalid-run principle, and sample-size requirement. |
| `docs/evaluation/M18-Benchmark-V3-Suite-Freeze.md` | Freezes the actual v3 membership: 18 pilot/162 formal cases, three cohort labels, four comparators, five repetitions. |
| `docs/evaluation/M18-Benchmark-V3-Pilot-Report.md` | Establishes the 360-record pilot as descriptive only and prohibits treating repetitions as independent observations. |
| `.ai/reviews/AR-M18-V3-PilotEvidence-Audit.md` | Records no M18 pilot analysis plan, no frozen analysis seeds/effect summary, and no formal progression; says M16 methods do not transfer automatically. |
| `docs/evaluation/M18-Corrected-Comparator-Contract.md` and `src/evaluation/m18_corrected_comparator_contract.py` | Preserve historical evidence, create the corrected condition's separate identity/namespaces, and deliberately omit a provider execution path. |

## Candidate Resolution Options

The smallest unresolved owner decision is which analysis population the
prospective corrected M18 primary question estimates.  Scientifically
reasonable options are:

1. **A/E-only primary population:** explicitly bind a named, machine-readable
   subset of formal v3 cases (for example, a precisely defined mapping from
   qualified `multi_step` cases to A/E) and exclude capability-boundary cohorts
   from the primary denominator.  This follows the M18 review most closely but
   reduces the primary cluster count and therefore requires a prospective
   MDE/discordance justification.
2. **All-cohort descriptive benchmark:** retain all three v3 cohorts and four
   comparators for descriptive completion/failure reporting, with no
   confirmatory pooled claim.  This honors the existing suite layout but does
   not answer the review's sole confirmatory research question.
3. **New prospectively powered eligible formal suite:** retain the A/E primary
   estimand, define eligibility and failure recording in a new versioned
   manifest, and choose a formal count from a documented MDE/discordance
   calculation.  This gives the cleanest confirmatory design but changes the
   future formal protocol/suite rather than merely annotating v3.

After the owner selects an option, the protocol must also record fixed,
separate resampling seeds; an explicit success=1/non-success=0 mapping for all
agent-originated terminal categories; a verified-infrastructure-invalid
classification and deterministic rerun policy; and whether secondary p-values
will be reported (thereby activating the stated Holm family).  These are
consequential freeze fields, not values to infer from the historical pilot.

## Narrowest Remediation

One project-owner decision is required before any corrected pilot is used to
support formal progression:

> **For the corrected M18 formal protocol, should the confirmatory population
> be (1) an explicitly mapped A/E-only v3 subset, (2) no confirmatory population
> with all v3 cohorts descriptive only, or (3) a newly versioned, prospectively
> powered eligible formal suite?**
>
> Option 1 preserves the original research question but requires a justified
> subset sample size; option 2 preserves the current suite without a pooled
> inferential claim; option 3 provides the strongest confirmatory basis but
> requires a new future suite/protocol freeze.

Once answered, add one prospective statistical manifest that binds the chosen
case IDs, eligibility/condition table, endpoint and failure/invalidation map,
MDE/discordance justification where inference is intended, effect definition,
resampling seeds/draw counts, secondary-test decision and multiplicity family,
and corrected-run result-schema requirements.  This is a methodology and
specification action, not a request for implementation or execution work.

## Progression Impact

| Question | Answer | Reason |
| --- | --- | --- |
| Does this invalidate original v3 pilot evidence? | **NO** | The pilot remains complete, immutable descriptive evidence under its original condition. |
| Does this invalidate corrected comparator implementation? | **NO** | The corrected contract and provenance isolation remain valid provider-free implementation work. |
| Does this block corrected runner preparation? | **NO** | Provider-free preparation can remain isolated; it must not select or execute a formal analysis protocol by implication. |
| Does this block real corrected pilot execution? | **YES** | A real pilot intended to inform formal progression needs the owner-selected prospective population, endpoint/failure rules, and progression gate first; otherwise it would recreate the non-comparative v3-pilot ambiguity. |
| Does this block formal execution? | **YES** | Formal execution lacks a frozen eligible denominator, justified sample-size/progression rule, and fully bound analysis/invalidation plan. |
| Does this affect historical v2 evidence? | **NO** | v2 identities, records, and digests are outside the corrected condition and remain untouched. |

## Final Verdict

The repository contains a strong methodological template for a case-clustered
paired analysis, but not a fully frozen, executable M18 comparative statistical
protocol for the corrected condition.  The missing prospective binding between
the review's A/E primary population and the v3 suite, together with the absent
formal-size justification and terminal/infrastructure map, prevents a justified
confirmatory estimand or formal authorization.  The original v3 pilot remains
descriptive only.

**BLOCKED**

## Issue #189 Resolution — Prospective Formal-Population Design

Issue #189 resolves the #188 blocker without post-hoc v3 cohort remapping. The authoritative design is `docs/evaluation/M18-Confirmatory-Population-and-Power-Design.md`.

### Resolution

The confirmatory population is not derived from `multi_step`, `distractor_selection`, or `recovery_correction`. It is a new held-out formal population whose cases carry a machine-checkable `primary_eligible` proof for `dependent_stateful_composition`: at least two public state transitions, a later required action dependent on an earlier public outcome, evaluator-owned completion, and equivalent MIND/Direct public contracts and external budgets. Existing v3 labels remain source/descriptive metadata only.

MIND versus Direct remains the sole confirmatory contrast. Five repetitions remain paired within a case and are aggregated to case-level success proportions. ReAct and Plan remain secondary/descriptive. The prospective framework fixes two-sided alpha 0.05, 90% target power, a 10-point minimally relevant paired absolute effect, complete-vector within-case permutation inference, paired case-cluster bootstrap intervals, and fixed simulation/permutation/bootstrap seeds.

### Power Resolution

The formal N is neither borrowed from v3's 162-case split nor inferred from historical outcomes. It will be selected once through preregistered simulation of the clustered paired five-repetition design. The power record must state MIND/Direct margins, paired discordance, repeated-measure dependence, stratum allocation, and a conservative scenario envelope. The smallest balanced N whose lower Monte Carlo power bound reaches 0.90 throughout that envelope is required.

A corrected pilot may provide only prespecified nuisance estimates for that conservative one-time calculation, after a pilot-to-power addendum is frozen. It cannot change the population, endpoint, contrast, alpha, sidedness, MRE, success/failure classification, or inferential method. Original v3, v2, corrected implementation, and frozen suite artifacts remain unchanged.

### Residual Authorization Boundary

The analysis-population and power-design blocker is resolved. Corrected-pilot and formal execution remain separately unauthorized by this specification. Before formal authorization, the corrected pilot, frozen pilot-to-power addendum, conservative N calculation, newly generated/validated formal manifest, and independent methodology review must all pass.

**M18 CONFIRMATORY POPULATION AND POWER DESIGN SPECIFIED**
