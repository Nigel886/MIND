# M18 Plan Repair Rerun Provenance

## Purpose

The original operational Plan-and-Execute records remain historical evidence.
All 60 ended in provider failure because the initial planner request violated
the DeepSeek JSON-object request contract. The corrected Plan condition is
post-hoc repair evidence; it neither overwrites nor reclassifies those records.

## Dedicated identity and namespace

The repair manifest is
`evaluation/m18/manifests/plan_repair_rerun_v1.json`, with identity
`m18_plan_repair_rerun_v1`. Future repaired results belong only in
`evaluation/m18/results/repair/m18_plan_provider_contract_repair_v1/`.
This namespace is distinct from `m18_pilot_v1`, all remaining-pilot work, and
formal evaluation. Admission rejects the historical namespace.

Each repair identity hashes its original Plan run ID plus the repaired-condition
identity, repair-manifest identity, repair commit, and frozen provider hash.
It is deterministic and cannot equal its original ID. Every repaired record
must carry both IDs, source pilot/tranche identities, repair manifest/hash,
repair commit, actual execution baseline, provider hash, harness identity, and
bounded outcome/telemetry fields. No hidden reasoning is stored.

## Frozen membership and resume

The manifest admits exactly the historical tranche's 12 Plan case IDs at
repetitions 1--5: 60 replacement identities. MIND, Direct, ReAct, remaining
pilot cases, formal cases, unknown IDs, duplicate IDs, and any mismatched
provenance fail closed. A result counts complete only after full record and
linkage validation; a filename alone is insufficient.

## Scientific boundary

Later analysis must retain both the original provider-failure 60 and any
separately persisted repair 60. A repaired cell may be descriptively compared
with the other conditions only with explicit post-hoc repair disclosure. This
provenance freeze performs no provider call, benchmark execution, remaining
pilot execution, or formal execution.
