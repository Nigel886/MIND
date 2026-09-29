# M20 DeepSeek Execution Bridge Authorization Decision

## Decision

**PROVIDER EXECUTION BLOCKED**

Independent audit baseline: `1db171c490b5e41677bf3506cc882958f000c7bc`. The immutable manifest (`m20_calibration_manifest_v2`, `ce129d8ee968c4bd6ddb6fa2573934f5da1fa2a8b408845e61c38275427da158`), case source (`m20_real_case_source_v1`, `4a00cb4128ef747419c601ed6696dd042cba7d4b45d09407e3fb68eb2a42ca12`), DeepSeek hash (`522fcf28714e168ce9854069468c51d3d3cb565404d7bdad3317e4fcc8f199ad`), resource ceiling, and ordering all validate. `DEEPSEEK_API_KEY` is available by a non-network, secret-safe check.

The request-isolation gate fails. The M20-native request serializer emits the public-state fields `required_progress`, `requires_observation`, and `requires_recovery`. Those fields encode evaluator success predicates. Their inclusion violates the frozen M20 information-isolation contract, regardless of whether they are present in the public-case object.

No DeepSeek call, pilot, calibration, formal execution, statistical test, or empirical record occurred. Provider/pilot/calibration/formal counts remain `0/0/0/0`. The issue is a bridge implementation defect, not model-performance or calibration evidence.

The bridge must be remediated in a separate implementation issue so its provider-visible projection excludes evaluator success predicates, then independently re-audited before execution can be authorized.
