# M18 Formal-Progression Decision

## Decision

Current M18 formal execution is **not scientifically authorized**. The
prospectively frozen calibration-to-power mapping reached its valid
fail-closed stopping condition: no nuisance scenario compatible with the
prespecified +10 percentage-point MRE remains in the required conservative
envelope, so no formal sample size is defined. No formal suite was executed.

## Evidence and frozen mapping

The admitted `m18_power_calibration_v1` store reconciles as
`480/480/0/0/0/0` (expected/valid/missing/duplicates/invalid/unexpected),
with 240 MIND and 240 Direct records, 48 clusters, 240 complete pairs, and
zero formal records. Its canonical digest is
`872edfe1d9032cd5e92270cd6893f2fa6d88243050395919f6a50be91f2dd558`.

All records are `answer_submitted` / `success`. Under the frozen estimators,
both marginal success estimates are 1.0 and `p10 = p01 = 0.0`. The mandatory
zero-discordance fallback gives a 97.5% Wilson upper bound of
`0.01575391994155881` for total discordance over 240 paired cells. This bound
is below the frozen +0.10 MRE; together with degenerate margin/covariance
bounds, it admits no MRE-compatible scenario. The protocol therefore requires
fail-closed termination before formal-N simulation or formal-suite generation.

This is a valid frozen-design statistical result, not an implementation
failure, insufficient admission evidence, or an equivalence conclusion. It
does not establish MIND/Direct equivalence or comparative superiority.

## Boundary and closure

Changing the MRE, endpoint, calibration size, failure classification, alpha,
target power, or power model after observing this calibration would be a new
prospective study, not a continuation of M18. Pooling historical or corrected
pilot evidence is likewise prohibited. Any future study would require a new
protocol identity, provenance, calibration, power design, and formal
authorization chain before provider execution.

M18 may be scientifically closed with the following bounded conclusion:
the frozen confirmatory design reached a valid prospective stopping condition;
calibration showed insufficient endpoint discordance to support the
prespecified +10pp confirmatory-effect model, therefore no valid formal sample
size was defined and formal execution was not performed.
