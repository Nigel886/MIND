# M20 DeepSeek Request Isolation Authorization Decision

## Decision

**PROVIDER EXECUTION AUTHORIZED**

Independent audit baseline: `d2ee32eaba3a4f5ef7aa81749ebd49ea58dbb3e4`. The frozen v2 manifest is `ce129d8ee968c4bd6ddb6fa2573934f5da1fa2a8b408845e61c38275427da158`; case source is `m20_real_case_source_v1` at `4a00cb4128ef747419c601ed6696dd042cba7d4b45d09407e3fb68eb2a42ca12`; DeepSeek hash is `522fcf28714e168ce9854069468c51d3d3cb565404d7bdad3317e4fcc8f199ad`; shared ceiling is `m20_real_ceiling_v1:6d497729bdb5d5fd87639a690b3d35064f8588e56268770ccbbecf143f5d1423`.

Independent fake-provider inspection through both future runner paths confirms that the wire projection contains only public task text, legal action IDs, and allowlisted current public state. Prior leaked success predicates, evaluator target, private witness, target-specific hints, hidden ground truth, future state, and injected canaries are absent from request objects and serialized messages. The projection has no generic state-copy or evaluator-object path. Adaptive remains native-M19 admitted; Fixed remains on its frozen schedule; both share the same bridge.

Structured-response failure handling, canonical retry/resource accounting, persisted lifecycle/reinvocation, pair reconstruction, and #221 projection remain intact. The manifest dry run remains exactly 60 pairs and 120 condition executions. Credential status is `CREDENTIAL READY` by non-network check. Provider, pilot, calibration, and formal records remain `0/0/0/0`.

Focused independent validation: 4 tests, exit 0. Full unittest: exit 0, no failures observed. Pytest: 773 passed in 130.20s, exit 0. `git diff --check`: PASS. The scientific contract remains unchanged: Adaptive versus Fixed, 5pp NI margin, logical-provider-interaction endpoint, MRE 0.25, one-sided alpha .025, joint power at least .90, gatekeeping, comparator, and evaluator semantics.

This authorizes a separate future execution issue to make real DeepSeek calibration calls only under the frozen v2 manifest and its existing boundaries.
