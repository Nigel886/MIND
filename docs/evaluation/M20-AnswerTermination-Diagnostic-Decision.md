# M20 Answer-Termination Diagnostic Decision

## Authorization

**M20 ANSWER-TERMINATION DIAGNOSTIC AUTHORIZED.** This permits only a future,
separate execution issue to run the four exact frozen condition executions. It
does not authorize calibration or formal evaluation.

## Frozen generation

- Protocol: `m20_answer_termination_diagnostic_v1`
- Digest: `60f3e8352458b313a18228e153dd1cfbc070c622a8b710efc87a2908c1b8bdb7`
- Namespace: `m20_answer_termination_diagnostic_v1`
- Path: `evaluation/results/m20_answer_termination_diagnostic_v1`
- Answer-readiness policy: `m20_public_answer_readiness_v1`
- Runtime: `4cdb0137de17e7f91da913abd9b9a386c9cdc5aee8715cc43fcf6cd27e7fde83`
- DeepSeek hash: `522fcf28714e168ce9854069468c51d3d3cb565404d7bdad3317e4fcc8f199ad`
- Ceiling: `m20_real_ceiling_v2` (16 reasoning, 8 tools, 8 logical provider,
  8 cycles), digest `6b4537f6d7e688f30517307cfd2019d99ad20380f76110f8f5515d400bfa08e0`

The four work IDs are:

- Case A Adaptive: `c945c24d53658f06b792452b9a86f3d025ebb0b6d7634640da67353c646bc632`
- Case A Fixed: `8e0cd4f92170d35108b275842589b7279469f97208338f614921e61e6da51c7a`
- Case B Adaptive: `01c65ea11f132e317b955e118a361821abecaaa92436afba1b026f25371b12ac`
- Case B Fixed: `672be0b0c9914018b5a07af066fa041716ae41f043a6850385c689ff6942ee12`

## Cases and public contract

Case A is `m20.real.answer_ready_early_stop.01` (cohort
`answer_ready_early_stop`, payload digest
`78543a525a6634b00afe26759ee1e4a826b29fae325d20f5804de25b14050a6f`).
It is answer-ready initially and exposes only `answer` and `stop`; `act` is
absent.

Case B is `m20.real.multi_step_stateful.01` (cohort `multi_step_stateful`,
payload digest `b977a2170893e1c1cfc7d7571e275df3f47d95259b29415e2d1bdea1202069be`).
It begins not-ready and reaches readiness after its frozen two-action public
progression. The provider sees only the normal public action contract before
that point and `answer`/`stop` after it. Witness, target, evaluator-private
state, success predicate, and hidden reasoning remain absent.

Valid `ANSWER` reaches the evaluator; valid `STOP` terminates cleanly;
answer-phase ACT is rejected before tool/environment action. Correctness is not
required for diagnostic pipeline success.

## Boundary

Exact authorization and fake-boundary checks passed. Credential presence is
READY by non-network check. This issue made zero provider calls and zero new
diagnostic, calibration, pilot, or formal records. Historical evidence remains
unchanged.
