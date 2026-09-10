# M16 DeepSeek Schema-Bearing Adapter

## Purpose

Issue #95 adds a strict DeepSeek M13 provider compatibility adapter. It
transmits the existing canonical M16 task-interpretation schema with the
public DeepSeek request so that JSON-object output is instructed to use the
same shape required by local M13 decoding.

## Root cause

Before this change, the DeepSeek request used JSON-object mode but did not send
the schema named by the M13 prompt. DeepSeek could therefore return a valid
JSON object using keys such as `type` and `capability`, while the local M13
contract required `intent`, `required_capabilities`, `constraints`, and
`evidence`.

## Canonical schema and request boundary

The sole schema source is
`evaluation/schemas/m16_mind_interpretation_v1.json`, loaded through
`load_schema("m16_mind_interpretation_v1.json")`. The DeepSeek M13 provider
adds that exact object as `response_schema` in its deterministic public request
data beside `public_task` and `capability_vocabulary`.

DeepSeek still receives `response_format={"type":"json_object"}`. That
setting ensures JSON-object syntax only; it is not native JSON-schema
enforcement. The provider-boundary adapter checks the returned payload against
the loaded canonical schema, and local `TaskInterpreter` plus semantic proposal
validation remain authoritative.

## Strictness and non-expansion

The generic M13 decoder is unchanged. No aliases, fallback parsing, inferred
capabilities, or dropped fields were added. A response using `type`,
`capability`, or `goal` instead of the canonical fields remains invalid.

The adapter also rejects canonical-schema violations such as missing required
capabilities or forbidden extra fields. It continues to reject malformed JSON,
arrays, null or empty content, missing envelope fields, and provider failures.
Hidden/reasoning fields are never treated as public structured proposal data.

## Validation boundary

Local mocked tests verify deterministic schema transmission, canonical proposal
construction and semantic validation, legacy-shape rejection, transport failure
handling, and preserved Direct/telemetry regression coverage. No formal M16
case or Diagnostic v1 case is used for these tests.

The effective request now includes the schema even though the tracked prompt
text and frozen provider configuration are unchanged. Consequently, this is a
new implementation state; any evaluation of it requires a new, explicitly
post-hoc protocol, manifest, run IDs, and result namespace.

## Development-only provider smoke

One invented integer-parity request was sent through the repaired M13 path
after local tests passed. It used no M16 public, formal, held-out, or
Diagnostic v1 text. The observed model was `deepseek-flash`; one transport
request and one model call produced a provider response, strict decode,
`TaskInterpretationProposal` construction, and semantic validation success.
This is a compatibility smoke only, not benchmark evidence.

## Historical integrity

This adapter does not modify or reinterpret the #90 formal experiment, #91
analysis, #92 attribution boundary, or #93 diagnostic artifacts. The historical
MIND-Lite formal result remains 0/480 success. A future repaired evaluation
must remain separate from those results.
