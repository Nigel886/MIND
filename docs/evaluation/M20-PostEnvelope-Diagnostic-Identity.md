# M20 Post-Envelope Diagnostic Identity Freeze

`m20_real_provider_diagnostic_v2` is a distinct prospective diagnostic
generation for the post-envelope-remediation check.  It is not execution
authorization.

## Frozen scope

The generation contains exactly two work items for
`m20.real.multi_step_stateful.01` / `multi_step_stateful` / payload digest
`b977a2170893e1c1cfc7d7571e275df3f47d95259b29415e2d1bdea1202069be`:

| Condition | Work ID |
| --- | --- |
| MIND-Adaptive | `716f81a7fed568252a48c1dce7ce42a7fd0a33872e6a6b25ba9390881766535c` |
| MIND-Fixed | `1524725c41d33657fca0b136a56cd516e1861494c1c01d33438e6b80e8f26e27` |

Its deterministic protocol digest is
`da3df7e2f8ccae19e44d7815c02d28e18201bd6a34432395fcf8c29fee3cb5b4`, and
its separate evidence path is
`evaluation/results/m20_real_provider_diagnostic_v2`.

## Preservation

The new generation does not alter v1.  The #258 v1 records remain terminal and
idempotent in their original namespace; cross-generation work IDs and
authorization artifacts fail closed.  The provider, resource ceiling, case
source, prompt, parser, schema, action/payload semantics, envelope normalizer,
and telemetry are unchanged.

No live authorization artifact is issued by this freeze.  A fresh independent
authorization gate is required before either v2 work item may reach DeepSeek.
