# M18 Plan Planner Provider Contract Repair

## Confirmed defect

The historical M18 operational tranche used JSON-object response mode through
the frozen shared DeepSeek provider configuration. Its Plan planner prompt
required a strict ordered plan but did not explicitly request JSON. DeepSeek
rejected a synthetic reproduction of that exact planner boundary with HTTP 400
(`invalid_request_error`): JSON-object mode requires a JSON instruction in the
prompt. This occurred before response admission, planner decoding, or Plan
executor invocation.

## Minimal repair

The repaired planner prompt adds only: “Return only a JSON object matching the
required planner schema.” It adds no examples, task hints, strategy advice,
planning behavior, schema fields, decoder tolerance, or execution behavior.
The shared provider configuration remains unchanged: `deepseek-flash`,
thinking disabled, temperature 0, top-p 1, output cap 512, JSON-object mode,
60-second timeout, and the frozen retry policy.

## Comparator and provenance boundary

This restores the already-specified Plan-and-Execute comparator rather than
introducing a new comparator design: a strict explicit planner, immutable
public plan, separate executor, observation-derived execution, and at most one
replan. The repaired condition is explicitly identified as
`m18_plan_provider_contract_repair_v1`, with artifact identity
`423ffc5dfd11be4a96d0a016019b22f420355c7cde9df2b5d232474101e2183d`.

The original historical condition remains
`m18_plan_and_execute_baseline_v1` with artifact identity
`0c0decad89793d2b8b1b9d943febd23b9b377759`. Its 60 recorded
`provider_failure` outcomes are immutable historical evidence and are neither
rewritten nor reclassified. Any future repaired execution must use the new
condition identity; it is not bit-identical to the executed tranche.

## Diagnostic preservation

Plan provider errors now retain a bounded, safe category in
`raw_artifact_references`, for example `m18_plan_provider:http_400`,
`m18_plan_provider:read_timeout`, or
`m18_plan_provider:connection_reset_or_eof`. A strict planner decoder
rejection is separately represented as
`m18_plan_decoder:planner_decoder_rejection`. These references contain no
request text, credentials, headers, provider payload, or hidden reasoning.
The neutral scientific taxonomy remains unchanged.

## Non-benchmark contract smoke

One synthetic non-benchmark planner call used the repaired real shared-provider
path. It was accepted in one transport attempt, admitted a `deepseek-flash`
response, and passed the unchanged strict planner decoder. The call exposed
435 prompt tokens, 33 completion tokens, 468 total tokens, and 1086 ms client
latency. This validates only provider-contract conformance; it is not a pilot
or formal benchmark result and makes no performance claim.

## Execution boundary

This repair did not rerun any benchmark identity, execute remaining pilot
identities, execute formal evaluation, or modify an M18 result namespace.
