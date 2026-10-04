# M20 Post-Remediation Calibration Generation

`m20_calibration_postremediation_v1` is a new non-executable generation in
`evaluation/results/m20_calibration_postremediation_v1`, manifest version
`m20_calibration_manifest_v3`.

Complete manifest digest:
`0d1faac7d3543041c4873e5dab5f6acbdd198206b663b88853d898e34ad3e91b`.
Pair/work binding digest:
`75a0756826aba183f31acf45799988265cf358f6fe3f42b799c9047759f5b2a5`.
Ordering: `m20_pair_counterbalance_v2` /
`03ba5c6d3bcffd194a562060883197371247623a241da1d651e842592d88ba31`.
Runtime identity:
`2f24111f2dfacd5f875cf9b7a1eb534ef7642948a16d32d512c9e3034ac003bb`.

It freezes 12 eligible cases, five repetitions, 60 pairs, and 120 work IDs;
the scientific, provider, ceiling, comparator, remediation, failure, and
integrity contracts are bound and validated. Historical v2/#250 is immutable
and not executable for new calibration. No provider call or empirical record
is authorized; a fresh independent audit is required before execution.

Validation: focused 27 tests in 0.689s; unittest 792 tests in 252.803s;
pytest 792 passed in 256.97s; `git diff --check` passed.
