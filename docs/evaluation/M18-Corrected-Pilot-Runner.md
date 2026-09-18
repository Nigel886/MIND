# M18 Corrected-Condition Pilot Runner

## Scope

Issue #190 prepares a distinct corrected-condition pilot runner. It is provider-free implementation and validation only: no real corrected pilot, formal execution, provider call, benchmark execution, or historical evidence change is authorized.

## Identity and Namespace

The entry point is:

    python -m src.evaluation.m18_corrected_pilot_runner --condition m18_v3_comparator_contract_v2 --split pilot --execute

Only the corrected condition is accepted. It uses the m18_v3_comparator_contract_v2 logical-ID schema, m18ccv2- run-ID prefix, corrected provenance, and the corrected pilot namespace evaluation/m18/results/m18_v3_comparator_contract_v2/pilot. Formal, diagnostic, historical, and foreign conditions are rejected.

The provider-free plan reconstructs exactly 360 unique logical IDs: 18 cases × 4 comparators × 5 repetitions. Each identity binds the corrected comparator-contract ID, suite, case, comparator, repetition, environment, evaluator, runtime, budget, provider configuration, and manifest hash. It cannot admit original-v3 provenance.

## Guard and Lifecycle

Importing and invocation without --execute are provider-free and do not create a result namespace. Execution is pilot-only; it schedules missing corrected identities only. The corrected store retains atomic create-only admission, re-read validation, duplicate rejection, tamper rejection, and missing-only resume. Temporary roots are normalized to a pilot child, preserving the store's pilot/formal namespace discriminator.

The runner dispatches the current MIND, Direct, ReAct, and Plan adapters through the corrected code path. Therefore strict integer answers and Plan answer-pending behavior are active through the same provider-facing adapters used in the frozen runtime. This runner changes neither runtime, evaluator, cases, provider configuration, nor the 6 action-cycle/4 tool-attempt budget.

## Operational Safeguards

Structural provider-contract failures are sanitized and, after two matching comparator/stage/category occurrences, persist a typed systematic-stop control artifact and halt scheduling. Timeout/5xx categories do not meet that structural-stop predicate. Control artifacts contain only typed diagnostic fields, never provider text or secrets.

Before a real corrected execution, preflight must show 360 expected, 0 valid, 360 missing, 0 duplicate, 0 invalid, and 0 unexpected corrected pilot records, with the corrected formal namespace empty. The runner does not analyze results or enable formal execution. Corrected pilot evidence remains operational/design evidence under the frozen #188/#189 protocol.
