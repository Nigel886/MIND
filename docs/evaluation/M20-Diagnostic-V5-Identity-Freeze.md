# M20 Diagnostic v5 Identity Freeze

`m20_real_provider_diagnostic_v5` is a new prospective generation after the
#273 resource-admission correction. It uses namespace
`m20_real_provider_diagnostic_v5`, path
`evaluation/results/m20_real_provider_diagnostic_v5`, and canonical digest
`34b3ac97415a30df900956f8065acbd7061ab2682ce18b7b6373abf6dc367aa4`.

Its only work IDs are Adaptive
`5327a0d66e6be142413ac84e73d2c47de44b9489162dc1a323765c00be117e83` and
Fixed `2c054d2e64a341ebe4df72c62f490696da4d69017b1a3d11f7084849fe9dfddf`.
They are isolated from v1–v4. V5 preserves all frozen scientific and provider
inputs, #259 envelope behavior, #269 retry identity, and #273 pre-transport
resource admission. The exact-budget fake path admits four operations and
stops the fifth before transport; retry fixtures reload canonically.

This freeze creates no execution authorization. V1–v4 evidence remains
unchanged; a new independent authorization gate is required before either v5
work item can use a real provider.

## Validation

- Focused: 40 tests in 0.760s, exit 0.
- `python -m unittest`: 790 tests in 411.219s, exit 0.
- `pytest`: 790 passed in 412.43s, exit 0.
- `git diff --check`: passed at delivery inspection.
