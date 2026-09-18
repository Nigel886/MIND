# M18 Benchmark v3 Suite Freeze

## Status and boundary

This artifact freezes the provider-free M18 v3 benchmark universe at source
baseline `b8efbfa24d1cfd01cd6dcb4dab1b1acc5703a03e`. It authorizes neither a
pilot nor a formal execution and contains no provider output. The four
comparator conditions are MIND-Lite v1.1, Direct Tool Calling, ReAct, and
Plan-and-Execute.

The frozen identities are `m18_suite_v3`, `m18_environment_v3`,
`m18_evaluator_v3`, `m18_shared_execution_runtime_v3`, `m18_budget_v3`, and
`m18_v3_logical_run_id_v1`. The public-action contract is
`m18_v3_public_action_contract_v1`; its budget is six action cycles and four
tool attempts.

## Universe and split

The v3 universe preserves v2 case membership, with a new v3 semantic identity.
The canonical machine-readable membership and ordered fixtures are in
`evaluation/m18/suites_v3/`.

| Split | Cases | Cohorts | Difficulty | Failure subtypes | Logical IDs |
| --- | ---: | --- | --- | --- | ---: |
| Pilot | 18 | 6 each | 6 each | 3 invalid, 3 recoverable | 360 |
| Formal | 162 | 54 each | 54 each | 27 invalid, 27 recoverable | 3,240 |

The cohort categories are `distractor_selection`, `multi_step`, and
`recovery_correction`; difficulty levels are `easy`, `medium`, and `hard`.
Pilot and formal membership are disjoint. Five repetitions are frozen for each
case/comparator condition. The deterministic split hash is
`dcab018037617762768c1ee15146335cac986d3a40e2c2bd77a39e1d6edd5ad7`.

## Fixture hashes

| Artifact | SHA-256 canonical hash |
| --- | --- |
| Pilot public fixture | `2e72bafd7e2619dcb7a58479f7754ead2f992fe160ac08f9a46cb801e7c5f088` |
| Pilot private fixture | `d19d8f2e514d73a15691ce601397a5f9b161bbbe8394b7fe1bd5680a2e434229` |
| Formal public fixture | `9a76596188a0e1ae82c18c8dc95c8eb2eedaa69fe6c8fcd86caa3f50f932ca9f` |
| Formal private fixture | `11866028c5965a915d18367bb286a8bd994a7ec242c6aae850cf6d9f6ea0f08b` |
| Manifest | `2f88a22a25118d93b30fa3e399562deb21e0034164c04e3fa30caa3103da0db9` |

## Provider-free validation

Canonical regeneration is deterministic for case IDs, ordered public/private
fixtures, split membership, and hashes. The reference trajectory reaches the
intended terminal behavior for 18/18 pilot and 162/162 formal cases. Its
maximum use is five action cycles and four tool attempts.

For both splits, public-contract predicates uncovered, stale executable
contexts, future executable contexts, truth/future-state leakage, stable-tool
identifier mismatches, and parameter-contract mismatches are all zero. The
public context exposes exactly the current executable tool and exact public
parameter contract; display labels are not executable.

All four concrete adapters consumed every pilot case via provider-free fake
outputs (18 × 4 = 72 checks) without a context-contract failure. Identical
reference action sequences replay deterministically. V3 logical IDs are unique
within each split, disjoint between splits, and domain-separated from historical
M18 v2 canonical and diagnostic IDs.

Historical evidence was read-only verified: v2 canonical has 360 records with
digest `50caa6c9afaaf3712e10c5f75f397bb1f8306ebe12b0fd305a8f076a4a79473c`;
v2 diagnostic has 72 records with digest
`2c2f3f52dfde996fba8b91e491297b7fdc7cc2f09425d3ba51595a06a0bbf0e2`.
No v3 pilot or formal result records exist.
