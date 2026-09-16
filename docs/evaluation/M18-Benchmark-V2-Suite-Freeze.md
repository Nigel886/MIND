# M18 Benchmark Suite v2 Freeze

M18 v2 replaces the v1 condition for future evaluation because v1's 3/1
execution identity made the approved multi-step and recovery trajectories
unreachable. It does not reinterpret historical v1 results.

The frozen suite identity is `m18_suite_v2`, binding
`m18_environment_v2`, `m18_evaluator_v2`, `m18_budget_v2`,
`m18_shared_execution_runtime_v2`, the four exact comparator conditions, and
repetitions `1..5`. It has 18 pilot and 162 formal cases, with equal cohort and
difficulty distributions (6/54 per cohort and difficulty respectively).

The manifest records public/private fixture hashes, split hash, provider
condition hash, freeze baseline, and the deterministic run universe: 360 pilot
and 3,240 formal identities. Public artifacts exclude evaluator targets;
private fixtures remain repository evaluation artifacts. Every case passes the
provider-free public reference reachability, target/public-result equality,
budget-fit, evaluator determinism, and truth-firewall gates.

Frozen hashes (canonical JSON) are:

- Pilot public: `6f06c05eff1fff480f0efdb669ef1803a9245ce6c9110be763dfbe1831e65e40`
- Pilot private: `4439a36bf3f0d327396900505728c543112fcbc70d96a9a10f10a5d8ccf3f1d5`
- Formal public: `91e7a0ab1ebc57af741e164cc4c26b369f8045c2a7530de04a0d1622509ace44`
- Formal private: `efaf9a3ec31c685beac1a616902b359735012402545c43fb46090e170e194283`
- Split manifest: `af8b52a395f9e0400f68f3ef32982b9eb2657694d76910fa7383020659176c25`
- Suite manifest: `ef8ac7edb2ac049d9152e7d0cb9d2d3c18a91be08ce41075a2d9808ee412ef09`

The freeze replays each public-only reference trajectory through the validated
v2 shared runtime. It also verifies wrong and malformed answers, Cohort B
distractor actions, and Cohort C recovery feedback fail or behave as required.
This is a fixed pre-execution admission gate, not case tuning.

No provider call, pilot execution, or formal execution occurred during this
freeze. The result namespace specification is reserved for later admission and
execution gates; no result records were initialized. Any semantic change
requires a new suite version rather than overwriting these artifacts.
