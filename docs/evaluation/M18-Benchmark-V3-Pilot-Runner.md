# M18 v3 Pilot Execution Runner

## Boundary

`python -m src.evaluation.m18_v3_pilot_runner --suite m18_suite_v3 --split pilot --execute`
is the only execution entry point introduced here. Importing the module and
running without `--execute` are provider-free and do not create result files.
Formal, diagnostic, historical, unknown-split, and v2-suite requests fail
closed.

The runner admits only the frozen 360-run pilot universe: 18 cases × four
comparators × five repetitions. It binds the exact suite manifest
`2f88a22a25118d93b30fa3e399562deb21e0034164c04e3fa30caa3103da0db9`,
`m18_suite_v3`, `m18_environment_v3`, `m18_evaluator_v3`,
`m18_shared_execution_runtime_v3`, `m18_budget_v3`, and
`m18_v3_logical_run_id_v1`.

## Persistence and resume

Canonical pilot records are reserved for
`evaluation/m18/results/v3/pilot/m18_suite_v3/`, separate from every v1/v2,
diagnostic, repair, and formal namespace. The store uses create-only atomic
writes, re-reads every written artifact, enforces a closed schema/integrity
hash, and rejects duplicates, tampering, unexpected fields, and provenance
drift.

Preflight reports `expected`, `valid`, `missing`, `duplicates`, `invalid`, and
`unexpected`; the pristine canonical state is 360/0/360/0/0/0. Resume schedules
only missing admitted identities. A crash before commit leaves an ID missing;
a crash after commit preserves the admitted record and does not rerun it.

## Runtime and provider safety

The runner dispatches the actual v3 MIND, Direct, ReAct, and Plan adapters via
`m18_shared_execution_runtime_v3`, including the corrected current-step public
action context. It does not auto-answer or alter the six-action/four-tool
budget.

Repeated structural provider-contract diagnostics for the same
comparator/stage/category persist a typed stop and halt later scheduling.
Transient 503/timeout categories do not create that stop. Diagnostics use the
existing finite-category and sanitization boundary; raw credentials, prompts,
and hidden reasoning are never persisted.

## Authorization

This implementation does not itself authorize execution. The v3 formal suite
remains prohibited. Real-provider pilot execution requires separate explicit
authorization and is not performed by this issue.
