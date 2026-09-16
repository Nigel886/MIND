# M18 Benchmark v2 Pilot Runner

`src.evaluation.m18_v2_pilot_runner` is the sole execution entry point for the
frozen `m18_suite_v2` **pilot**. It loads written suite and split manifests,
written pilot fixtures, and the v2 run-provenance contract before it can invoke
a provider. It does not support formal or all-split execution.

Run a provider-free inspection with:

```text
python -m src.evaluation.m18_v2_pilot_runner --suite m18_suite_v2 --split pilot
```

The command reports the 360 expected pilot identities and existing/missing
admitted records without creating a result namespace or making a provider call.
Real execution requires the explicit `--execute` flag and separate execution
authorization. This documentation does not authorize a pilot run.

The runner uses the frozen namespace
`evaluation/m18/results/v2/pilot/m18_suite_v2`. Each record is validated
against its expected suite, case, comparator condition, repetition,
environment, evaluator, budget, runtime, provider configuration, and execution
baseline before atomic creation. It is then read back and re-admitted. Existing
valid records are skipped on resume; invalid, unexpected, duplicate, or
filename-mismatched records fail closed and are never overwritten.

The order is frozen as pilot case order, comparator-condition order, then
repetition `1..5`. The runner dispatches MIND, Direct, ReAct, and Plan through
their existing concrete v2 adapters and shared provider boundary. It does not
introduce a parallel budget, prompt, schema, or comparator path.

Raw pilot evidence remains separate from tracked summaries. A later authorized
execution must produce a deterministic digest from admitted records only, retain
typed provider/integrity failures separately from benchmark outcomes, and leave
formal-v2 and historical namespaces untouched.

## Provider failure diagnostics and operational stops

An ordinary bounded provider failure is admitted as a valid
`provider_failure` result only when its frozen run provenance is valid. Its
record may carry a safe diagnostic projection: normalized provider category,
comparator and stage, logical provider-call index, transport attempts,
retry-exhaustion state, and a sanitized short message. It never stores API
credentials, authorization headers, cookies, raw prompts, or private fixture
data. Diagnostic metadata is not part of the scientific run ID.

Integrity conditions—frozen artifact drift, provenance mismatch, duplicate or
conflicting identity, malformed persistence, and mixed runtime identity—remain
fail-closed integrity errors and are never reclassified as provider results.

The pilot runner persists a separate operational stop event after **two
independent** provider failures with the same structural contract category,
comparator, and stage. Current structural categories include `http_400`,
`invalid_request_error`, `provider_result_contract`, `malformed_json`, and
`model_identity_mismatch`. A single transient (`http_503`, timeout, connection
reset, or rate limit) is admitted as ordinary provider-failure evidence and
does not stop scheduling. A persisted systematic-stop event blocks an ordinary
restart before new provider execution; a later explicit operator authorization
is required to override it. The stop event is operational evidence, not a
benchmark result.
