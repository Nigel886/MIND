# M18 Task Generation and Evaluator Foundation

## Status

This module supplies deterministic typed case generation, structural public
projection, a neutral synthetic environment, and external evaluator fixtures.
It does not generate or freeze the M18 formal suite, call a provider, execute
an agent, or run an experiment.

## Case boundaries

`M18Case` separates execution metadata (`case_id`, namespace, protocol and
version identities), evaluator-private fields (target answer/state, completion
rule, deterministic failure schedule, provenance), and `M18PublicCase`.
Agents receive only the public projection: task text, ordered public tool
contracts, and public environment configuration. Difficulty, cohort labels,
private targets, evaluator rule, generation seed, correct action/tool, and
failure schedule are structurally absent from that projection.

## Cohorts and structural difficulty

- A generates lookup/transform-style dependency cases where later action
  parameters require a prior public observation; easy/medium/hard have depth
  one/two/three.
- B generates two/three/four plausibly described public tools at
  easy/medium/hard, with seed-controlled correct-position support.
- C generates deterministic `recoverable_failure` and `invalid_action`
  schedules. The environment maps equivalent actions to equivalent public
  feedback without system/provider identity branching.

Difficulty is structural only and is never derived from system performance.

## Environment and evaluator

The neutral environment accepts architecture-neutral action dictionaries and
produces `success`, `recoverable_failure`, `invalid_action`, or where defined
`unrecoverable_failure` outcomes. It ignores the optional system identity.

The external evaluator uses private case truth rather than agent termination
labels. It emits neutral categories including success, wrong answer, budget
exhaustion, invalid-action exhaustion, unrecoverable environment failure,
agent/internal and provider failure, and infrastructure invalidity. Exact
target answer or target-state equivalence permits trajectory-independent valid
completion.

## Canonical identities and split support

Canonical UTF-8 JSON with sorted keys supports stable full-case, public-case,
and ordered-collection hashes. Explicit `pilot` and `formal` namespaces prevent
case-ID collision. Version constants are `m18_case_schema_v1`,
`m18_generation_v1`, `m18_environment_v1`, and `m18_evaluator_v1`.

`M18SuiteDesign(18)` represents the approved 162-case primary design;
`M18SuiteDesign(10)` represents the 90-case fallback. These are capacity
descriptions only: no final suite collection is generated or frozen here.
