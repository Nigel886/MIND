# M20 Ceiling-v2 Calibration Generation

`m20_calibration_ceilingv2_v1` is a prospective, non-executable calibration
generation. It uses manifest version `m20_calibration_manifest_v4`, namespace
`m20_calibration_ceilingv2_v1`, and result path
`evaluation/results/m20_calibration_ceilingv2_v1`.

It binds `m20_real_ceiling_v2` exactly, with 16 reasoning steps, eight tool
attempts, eight logical provider interactions, and eight decision cycles. Its
runtime identity is a new ceiling-v2 generation identity, which carries the
ceiling identity alongside the #259 envelope normalization, #269 retry
persistence, #273 resource admission, #252 telemetry, canonical evidence
validation, harness, and frozen DeepSeek request contract.

The frozen design has 12 eligible `m20_real_case_source_v1` cases (digest
`4a00cb4128ef747419c601ed6696dd042cba7d4b45d09407e3fb68eb2a42ca12`), five
repetitions, 60 pairs, 120 work identities, and `m20_pair_counterbalance_v3`
with 30 Adaptive-first and 30 Fixed-first pairs. The manifest retains the
pre-specified contrast, 0.05 quality NI margin, logical-provider-interaction
resource endpoint, -0.25 MRE, paired case-cluster bootstrap, one-sided 0.025
gate alpha, 0.90 joint-power target, and two-gate sequence.

Manifest, ordering, pair, and work identities are deterministic and fail
closed against v1/v2/v3 manifests, v1 ceilings, stale ordering/runtime,
provider, source, namespace, and digest bindings. At most one linked eligible
provider/infrastructure replacement is allowed; performance reruns are
prohibited.

Historical #250 and #282 records, ceiling v1, manifest v2/v3, and diagnostic
v1-v5 remain immutable. This freeze made no provider calls and no new pilot,
calibration, or formal records. A fresh independent authorization audit is
required before any real provider execution.
