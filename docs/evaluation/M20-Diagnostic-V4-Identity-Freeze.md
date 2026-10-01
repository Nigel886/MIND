# M20 Diagnostic v4 Identity Freeze

## Frozen generation

`m20_real_provider_diagnostic_v4` is a new prospective generation, not a
repair or rerun of v1, v2, or v3. Its result namespace is
`m20_real_provider_diagnostic_v4` and its path is
`evaluation/results/m20_real_provider_diagnostic_v4`.

Its canonical protocol digest is
`b714470f7fd8ca25287bddb341346985a6728f395945b0eda85ad5ab54c4dca1`.
The two deterministic work IDs are:

- Adaptive: `c79a65566a45fb0418b208957c2a86c45925857e0ff9cd76d17dfeb8cd52ee66`
- Fixed: `4c5fa94fde493862dbe9d18d5ac1b4b9cc5d0cb1e7e26a42639508c238eb088f`

It preserves the one-case, two-condition scientific scope, source/provider/
ceiling bindings, #259 envelope path, unchanged parser/schema/prompt, #252
telemetry, and #269 shared retry-persistence semantics. Cross-generation work,
namespace, protocol, path, and authorization artifacts fail closed.

This freeze does not authorize provider execution. Historical #250, v1, v2,
and invalid Fixed v3 evidence remain unchanged. A separate independent
authorization gate is required before either v4 work item can be executed.

Focused validation passed 36 tests. Full unittest passed 786 tests in 131.189s
(exit 0); pytest passed 786 tests in 134.13s (exit 0); and `git diff --check`
passed.
