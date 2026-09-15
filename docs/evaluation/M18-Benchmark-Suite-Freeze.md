# M18 Benchmark Suite Freeze

## Freeze status

`m18_suite_v1` is **FROZEN**. It was deterministically generated from the
#115 generation foundation commit `a8cef9b6e3c1a746a4062aa0e126308d8842d5b0`.
No provider was called and no agent, pilot, or formal experiment was executed.
Any content change requires a new suite identity, hashes, manifest, and
explicit invalidation procedure.

## Artifacts

Canonical artifacts reside in `evaluation/m18/suites/`:

- `pilot/private_cases.json` and `pilot/public_cases.json`
- `formal/private_cases.json` and `formal/public_cases.json`
- `manifests/m18_suite_v1_manifest.json`
- `manifests/m18_suite_v1_split.json`

Private records are evaluator-only. Agents must consume only the separately
generated public projection; it structurally omits cohort/difficulty labels,
targets, evaluator rules, failure schedules, generation metadata, and routing
hints.

## Allocation

The formal suite has 162 cases: 18 per cohort×difficulty cell, yielding 54
cases in each of multi-step progression, distractor selection, and recovery /
correction, and 54 easy / 54 medium / 54 hard cases. Cohort C has 27
recoverable-failure and 27 invalid-action cases. The 18-case pilot has two
cases per cohort×difficulty and a 3/3 Cohort C subtype split.

Difficulty is structural: A has dependency depths 1/2/3; B has 2/3/4 public
tools; C has fixed deterministic failure subtype/position rules. No model or
baseline outcome informed allocation or labels.

## Audits

Canonical ordering is cohort, difficulty, subtype, then case identifier. The
freeze audit verifies exact-ID/private/public uniqueness, pilot/formal
separation, recursive public-projection leakage absence, A observation-
dependency flags, B tool-position distribution support, C deterministic and
system-neutral failures, evaluator target/wrong-answer behavior, and
environment system-identity independence. Repository-fixture contamination is
guarded through independent templates, values, IDs, and seed domains; this is
not a claim about external training data.

## Frozen identities

| Artifact | SHA-256 |
| --- | --- |
| pilot private | `811d3bd92d016d36efcd147770d8f97b0211fb7c652093c4b00d13a81fb8da1d` |
| pilot public | `2515eb193492d0423dfd1b32b5207106ddb4c53088c4572158db94a6119b081d` |
| formal private | `667a14ff57e64e06eb400ac195f8385fa89951d8e802f39daef6aef2b19bc7f2` |
| formal public | `f9fb25cf41f61cb9a769d2cfac1b4c40a5f95b472e6bc43050756ea6d0074979` |
| split | `88c0a88063f0e50f1f396f4e01fc2ce6bd53bb4858ac895b8e1fae5e1c911e67` |
| environment/evaluator | `5294df99c8bba4748b56cd689ce250b36bd40ae8318abc94dafa772508db8248` |
| manifest | `4eb3c8a1a4da0a17297bf26937db28b7d9fb33b9174e2f2128d14fd6fc6aec04` |

Versions: `m18_suite_v1`, `m18_generation_v1`, `m18_case_schema_v1`,
`m18_environment_v1`, and `m18_evaluator_v1`. Pilot and formal seeds are
separate namespaces: `m18_pilot_seed_v1` and `m18_formal_seed_v1`.
