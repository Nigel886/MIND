# DR-M20 Prospective Calibration Preflight

## Status

**CALIBRATION BLOCKED BEFORE EXECUTION** at baseline `62652cf3e1edba1da571be312062ab4ccd2416ab`.

The completed-idempotence readiness decision authorizes creation of a calibration issue, but explicitly does not authorize provider execution. This preflight found no explicit real-provider authorization, no frozen real-provider configuration/hash, and no complete canonical M20 eligible-case manifest from which the required prospective calibration sample structure can be derived. No calibration record has been created.

## Frozen identities and intended calibration contract

The applicable frozen identities are: suite `m20_suite_v1`; environment `m20_environment_v1`; evaluator `m20_evaluator_v1`; metric `m20_resource_metrics_v1`; statistical protocol `m20_statistical_protocol_v1`; primary conditions `m20_mind_adaptive_v1` and `m20_mind_fixed_v1`; namespace `m20_calibration_v1`; and the condition-neutral resource-ceiling and provider-configuration identities required by the canonical manifest. Retry ownership and failure semantics remain those frozen by the metric contract: provider-client-owned transport retries, typed failures, and at most one linked replacement only for infrastructure/provider failure. Performance outcomes never receive a rerun.

## Exact prerequisite ledger

1. **Real-case universe:** the complete eligible real-case universe is not frozen; therefore case, repetition, cluster, and cohort calibration membership cannot be canonically bound.
2. **Calibration manifest:** a canonical calibration manifest cannot be finalized until that eligible real-case universe is frozen.
3. **Real provider identity:** no prospectively frozen real-provider configuration identity or hash exists.
4. **Real resource ceiling:** no prospectively frozen real-execution resource-ceiling identity exists.
5. **Execution authorization:** real provider execution is not authorized.

Readiness authorization from #234 permits this preflight only; it does not imply provider-execution authorization. No concrete provider hash, resource-ceiling identity, eligible case/repetition/cluster/cohort list, pairing universe, ordering/randomization, or maximum calibration size was present as a frozen real-execution artifact. Consequently a canonical calibration manifest cannot be truthfully persisted, and creating one from the deterministic test fixture or substituting fake data would violate the prospective contract.

## Allowed nuisance quantities

Only the four calibration-eligible classes in the frozen statistical protocol may later be estimated:

1. Paired success joint distribution and within-case dependence, using a conservative simultaneous confidence envelope.
2. Case-level variance/correlation of paired logical-provider-interaction differences, using an upper variance bound and no assumed beneficial correlation.
3. Cluster heterogeneity and zero inflation, using a conservative empirical cluster distribution/envelope.
4. Provider/infrastructure missingness rate, using an upper confidence bound to inflate required cases.

No estimate has been made. The primary contrast (MIND-Adaptive vs MIND-Fixed), 5 pp quality NI margin, logical-provider-interactions endpoint, 0.25-interaction MRE, one-sided 0.025 alpha per primary gate, at-least-0.90 joint power target, quality-first/resource-second gatekeeping, comparator definitions, and evaluator semantics remain unchanged.

## Execution and namespace state

Provider execution authorization: **NO**. Pilot, calibration, and formal record counts are `0/0/0`; the M20 result roots are absent. No provider call, pilot, calibration, formal execution, empirical estimate, sample-size simulation, or statistical test occurred. Formal execution remains fail-closed.

## Sufficiency

**CALIBRATION BLOCKED BEFORE EXECUTION.** No empirical calibration occurred, so empirical sufficiency cannot be established. Nuisance estimates are **NONE**. Deterministic sample-size simulation may not be created until an explicit provider-execution authorization and a complete frozen canonical calibration manifest are available.

## Focused validation

- Canonical harness integrity suite: `19 passed in 0.116s`.
- `python -m unittest`: exit `0`; `Ran 758 tests in 285.128s`; `OK`.
- `pytest`: exit `0`; `758 passed in 153.70s (0:02:33)`.
- `git diff --check`: PASS.
- Baseline: `HEAD == origin/main == 62652cf3e1edba1da571be312062ab4ccd2416ab`.
