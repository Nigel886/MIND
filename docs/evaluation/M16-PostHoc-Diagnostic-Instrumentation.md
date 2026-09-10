# M16 Post-Hoc Diagnostic Instrumentation

## Objective

This opt-in instrumentation records normalized stage events for a future, separate post-hoc MIND diagnostic replication. It does not execute that replication and does not alter #90, #91, or #92.

## Scope Boundary

Instrumentation observes M16 MIND composition boundaries only. It never changes task input, provider request construction, prompt, model, sampling, retry, timeout, budget, Meta-Inference outcome, session transition, policy, action, environment, judge, or terminal category.

## Instrumentation Locations

`M13SessionAdmissionResolver` observes admission boundaries; `M16MINDSessionEvaluationAdapter` observes private projection, session, policy, and public-action boundaries; `M16BenchmarkRunner` supports optional MIND actor observation of tool/evaluator/terminal boundaries. MIND core and Direct remain unchanged.

## Behavior-Preservation Contract

For fixed synthetic inputs and mocked provider outputs, telemetry OFF and ON must yield identical public admission, session/action serialization, provider-call count, and evaluation-facing behavior. Sink return values and sink exceptions are ignored so telemetry cannot feed back into execution.

## Stage Schema

Schema version: `m16-mind-diagnostic-stage-v1`. It supports 24 ordered, normalized events: provider request/response/decode; proposal/validation; Meta-Inference/admission; private projection/session/policy/action; tool/evaluator; and terminal action/reason events. Unreached stages are absent.

## Telemetry Payload

Events retain only normalized structural fields: stage/ordinal, success, diagnostic reason, selected strategy/capability, action/tool, counters, session phase, and terminal category. They exclude provider text, prompts, credentials, headers, private truth, environment-private state, and hidden reasoning.

## Reason Taxonomy

`m16-mind-diagnostic-reason-v1` defines provider transport/decode, malformed output, validation, non-selection, admission, private-session, policy, unsupported projection, completion/evaluator/tool, and unknown codes. These codes never change historical `failure_category`.

## Diagnostic Identity and Result Isolation

Future runs use `m16diag:v1:<manifest>:<public-case>:mind_lite_v1:r<repeat>` and may use only `evaluation/results/m16_mind_failure_diagnostic_v1/`. Historical M16 result namespaces are rejected. This phase does not initialize or write the diagnostic directory.

## Positive and Failure Controls

Telemetry-preserving synthetic direct-answer control returns `answer`; calculator returns `tool_call`. Failure controls cover provider/interpreter, malformed proposal, semantic validation, Meta-Inference non-selection, admission, and private-session termination.

## OFF vs ON Equivalence

Focused tests compare public outputs and provider-call counts with sinks disabled, recording, returning arbitrary values, and failing. Event ordinals increase strictly and event presence matches reached boundaries.

## Provider Preservation

No provider call was made. The future configuration remains frozen: DeepSeek API, `deepseek-v4-flash`, documented `DeepSeek-V4-Flash-0731`, observed `deepseek-flash`, JSON object mode, thinking disabled, temperature 0, top_p 1, max output 512, and unchanged retry/timeout settings.

## Remaining Review Gate

An independent instrumentation review must verify behavior preservation, schema completeness, empty isolated namespace, frozen diagnostic manifest, and provider/configuration identity before any diagnostic provider call.

## Explicitly Not Executed

REAL DIAGNOSTIC RUNS EXECUTED: 0

REAL PROVIDER CALLS: 0

FORMAL RESULTS MODIFIED: NO

MIND CORE SEMANTICS MODIFIED: NO

DIRECT SEMANTICS MODIFIED: NO
