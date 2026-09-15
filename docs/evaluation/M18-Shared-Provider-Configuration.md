# M18 Shared Real-Provider Configuration

## Scope

This document freezes the one shared real-provider condition for M18. It is a
provider-contract artifact, not a pilot or benchmark result. It does not make
any comparative-performance, quality, capability, or agent-superiority claim.

## Frozen Condition

| Setting | Value |
| --- | --- |
| Provider | DeepSeek API |
| API surface | OpenAI-compatible Chat Completions |
| Base URL | `https://api.deepseek.com` |
| Requested model | `deepseek-flash` |
| Documented model identity | DeepSeek-V4.1-Flash |
| Thinking | explicitly disabled: `{"type":"disabled"}` |
| Temperature / top-p | `0` / `1` |
| Output cap | 512 tokens |
| Structured output | `response_format={"type":"json_object"}` |
| Streaming | disabled |
| Timeout | 60 seconds per transport attempt |
| Transport attempts | at most 3 per logical provider call |
| Application response cache | disabled |

The canonical configuration is serialized in
`evaluation/m18/manifests/provider_config_v1.json`. Its SHA-256 identity is
`0f251e14722603e6e39416374467a3598cd72e1d28673e60daf8440dd6115ee2`.
Credentials, authorization headers, machine paths, timestamps, and response
telemetry are excluded from this identity.

## Logical Calls and Transport Attempts

One architecture decision is one logical provider call. It can use up to three
transport attempts only for connect/read timeout, connection reset/EOF,
temporary DNS failure, and HTTP 500/502/503/504. Backoff is 0.5 then 1.0
seconds. HTTP 4xx, certificate errors, malformed completed responses,
schema-invalid output, length-truncated output, and unsupported output are not
retried.

No retry creates a second logical model decision. There is no fallback model,
fallback parser, output repair, or application-level semantic cache.

## Response and Telemetry Boundary

The shared response envelope records requested model, returned model when
exposed, strict response content for local decoding, finish reason and token or
cache telemetry when exposed, logical-call ID, transport attempts, status, and
latency. Missing provider telemetry remains unavailable (`null`); it is never
fabricated as zero. Reasoning content is neither requested nor persisted.

Strict local decoders for MIND-Lite v1.1, Direct Tool-Calling, ReAct, and
Plan-and-Execute remain the semantic authority. JSON-object mode only assures
the response syntax boundary; it does not repair or admit an invalid schema.
If a completed response exposes a model identifier other than `deepseek-flash`,
the client rejects it as `model_identity_mismatch`; it does not substitute a
model or continue the affected condition.

## Synthetic Smoke Gate

`python -m src.evaluation.m18_provider_smoke` is an explicit, development-only
command. It uses fresh synthetic objects and writes metadata-only evidence to
`evaluation/m18/provider_smoke/`. It has no suite import and must not access
the pilot or formal directories. The required calls are MIND, Direct, ReAct,
Plan planner, and Plan executor. Each must pass its local strict decoder before
pilot execution is allowed.

**THIS IS NOT A PILOT OR BENCHMARK RESULT.**

## Synthetic Smoke Result

The explicit development-only smoke passed on the frozen configuration:

- MIND action decoder: PASS.
- Direct action decoder: PASS.
- ReAct action decoder: PASS.
- Plan-and-Execute planner decoder: PASS.
- Plan-and-Execute executor decoder: PASS.

It made five logical provider calls and five transport attempts. Every completed
response returned model identifier `deepseek-flash`, used `finish_reason=stop`,
and exposed prompt, completion, total, and cached-token telemetry. The compact
metadata-only evidence is stored at
`evaluation/m18/provider_smoke/m18_shared_provider_smoke_v1.json`; it contains
no task-suite input, prompt text, credentials, or reasoning content.

## Freeze Rule

After the four-adapter smoke passes, this configuration identity is frozen for
M18 pilot and formal execution. Changing provider, model, thinking, sampling,
output cap, JSON mode, timeout, retry policy, or caching requires a new
configuration hash and a new result namespace.
