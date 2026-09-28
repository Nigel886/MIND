# DR-M20 Real Case Source and Execution Configuration

## Status

#236 was blocked because no canonical real M20 case source existed. #237 introduces the deterministic, provider-free `m20_real_case_source_v1` source; it is not the `m20.fake.case.1` fixture and contains no provider outputs or performance outcomes.

## Real case source

The source materializes two explicitly authored deterministic cases for each frozen cohort: `multi_step_stateful`, `information_acquisition`, `distractor_unnecessary_action`, `recovery_replanning`, `answer_ready_early_stop`, and `resource_constrained` (12 eligible cases total). Every case binds a case ID, public payload digest, cohort, cluster, public actions/state, private evaluator target, private reference witness, eligibility state, and authorship/template/enumeration provenance. The prospective repetition structure is five matched repetitions per case; primary pair construction remains condition-specific over the same case/repetition/cluster identity.

The environment is condition-neutral and deterministic. The evaluator retains private targets and requires the appropriate public progress, observation, and recovery state. Source validation rejects duplicates/payload collisions and confirms each eligible private witness reaches official evaluator success through public legal actions only. The source digest is `4a00cb4128ef747419c601ed6696dd042cba7d4b45d09407e3fb68eb2a42ca12`.

## Execution configuration status

A secret-free canonical provider-configuration schema and canonical resource-ceiling schema are present. No concrete real provider/backend, model/version, API mode, or other provider values have been supplied by the frozen context; therefore no concrete provider hash can truthfully be frozen. Likewise, no prospectively justified numeric real resource limits have been supplied; therefore no concrete real resource-ceiling identity can be frozen. The schemas do not store credentials.

Retry ownership/failure semantics remain frozen: provider-client-owned transport retries, typed failures, and at most one linked replacement solely for eligible infrastructure/provider failure. No execution path is authorized by these schemas.

## Boundary and unresolved decision

Provider calls, pilot records, calibration records, formal records, and nuisance estimates remain `0/0/0/0/NONE`. Provider execution remains unauthorized. A user-specified real provider/model configuration and prospectively justified shared reasoning/tool/provider/decision-cycle limits are required before calibration-manifest freeze can be retried.

## Focused validation

- `python -m unittest tests.test_m20_real_case_source tests.test_m20_evaluation_harness`: `23 passed in 0.079s`.
- `python -m unittest`: exit `0`; `Ran 762 tests in 130.328s`; `OK`.
- `pytest`: exit `0`; `762 passed in 132.41s (0:02:12)`.
- `git diff --check`: PASS.
