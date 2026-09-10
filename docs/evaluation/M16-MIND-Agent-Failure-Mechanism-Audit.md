# M16 MIND-Lite Agent Failure-Mechanism Audit

## Executive Summary

The valid M16 restart1 result records establish a uniform visible MIND terminal pattern: 480/480 `agent_fail`, one agent step, zero tool calls, one provider request attempt, and one logical model call. The audit maps six synthetic candidate FAIL mechanisms and demonstrates valid synthetic direct-answer and calculator actions. It does **not** identify the exact internal cause of the 480 formal outcomes because the required stage/action evidence was not persisted.

## Formal Evidence Boundary

This audit reads only `evaluation/results/m16_deepseek_v4_flash_restart1/`. It does not alter #90 formal records or #91 analysis. The observed formal outcome remains 480 MIND `agent_fail` records.

## Missing Formal Evidence

Formal records do not preserve terminal action/reason, session phase, provider payload/error/status, parser outcome, proposal, validation result, Meta-Inference decision, admission evidence, projected task, policy, action request, or evaluator payload. A logical model-call counter does not prove that the structured proposal parsed or was admitted.

## MIND Runtime Path

Public Task → M16 MIND session adapter → CognitiveAgentSession admission → M13 resolver → TaskInterpreter/provider decode → validation → Meta-Inference adapter/selection → IntegrationSelected → private compatibility projection → private CognitiveAgentSession → immutable RuntimeController transition → GoalAwarePolicyEngine → EvaluationAction → runner category mapping.

## agent_fail Source Mapping

The runner maps a terminal `FAIL` evaluation action to `agent_fail`. The adapter can return `FAIL` when M13 does not yield `IntegrationSelected`, when its private session terminates without completion, or when policy projection fails. Those paths collapse into one record category; see `agent_fail_source_mapping.csv`.

## Synthetic Diagnostic Matrix

Synthetic-only controls distinguish provider/interpreter failure, malformed proposal, validation failure, Meta-Inference non-selection, private-session max-cycle termination, and a private unsupported-policy path. Each yields adapter `FAIL` and runner `agent_fail`. These are candidate paths, not per-formal-run attributions.

## Direct-Answer Positive Control

A valid invented direct-answer task with a provider-compatible valid proposal produced `IntegrationSelected`, reached the private session and policy, and returned an `answer` action—not adapter `FAIL`.

## Calculator Positive Control

A valid invented calculator task with the same selected path produced a `tool_call` action and reached a deterministic synthetic calculator `tool_response` boundary—not adapter `FAIL`.

## Provider Boundary Diagnostics

All provider behavior in this audit is a local counting mock. A valid structured proposal, malformed structured payload, semantic validation failure, and non-selection are locally distinguishable. No DeepSeek request was made.

## Admission / Meta-Inference Diagnostics

The valid synthetic `IntegrationSelected` path works. Provider/interpreter, validation, and non-selection paths are independently reproducible as admission failures.

## Session / Policy Diagnostics

A valid synthetic private session produces supported actions. Max-cycles and unsupported private policy paths produce `FAIL` deterministically. The unsupported-policy control is intentionally not M16-eligible and documents a source branch, not a formal-task simulation.

## Direct Path Comparison

Direct bypasses M13 interpretation, deterministic validation, Meta-Inference admission, private compatibility projection, and CognitiveAgentSession. This explains a path difference, not a design prescription or causal attribution.

## Candidate Mechanisms

Six local candidate FAIL mechanisms are mapped: provider/interpreter failure; malformed proposal; validation failure; Meta-Inference non-selection; private-session max-cycle termination; and unsupported private policy.

## Ruled-Out Mechanisms

No deterministic defect prevents every valid synthetic MIND path from producing a public answer or calculator action. The audit therefore rules out a universal valid-path block in the frozen local adapter/session/policy path.

## Formal Attribution Limit

The formal cause remains unidentifiable: the stored visible pattern is consistent with multiple mapped candidate paths. No candidate is assigned to any individual formal run.

## Classification

Formal attribution: **G. INSUFFICIENT PERSISTED EVIDENCE**. Synthetic finding: valid MIND admission/session/policy positive controls work; candidate failure branches are locally distinguishable.

## Implications for #90/#91

#90 remains a valid measurement of the frozen executed artifact. #91 remains the authoritative statistical analysis. Neither taxonomy, denominator, result record, nor result claim is changed.

## Post-Hoc Follow-Up Recommendation

Any remediation or enhanced stage telemetry requires a new explicitly post-hoc experiment with a new result identity. It must not overwrite restart1.
