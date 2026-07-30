# ADR-011 - Deterministic Meta-Inference Engine

**Status:** Accepted

## Decision

Introduce a state-free MetaInferenceEngine with
select(task: Task, runtime_state: RuntimeState) -> MetaInferenceDecision. It
receives an explicit InferenceStrategyRegistry at construction and selects only:
it never retrieves implementations, calls infer, creates observations, alters
Belief/RuntimeState, calls RuntimeController, or integrates with Agent.

Required capabilities come only from Task.metadata under
required_inference_capabilities. A strategy matches when this explicit
requirement set is a subset of its capabilities. One match is selected; no
match is unavailable; multiple matches are rejected as ambiguous. Compact
deterministic evidence records requirements and candidate names only.

No semantic inference, metadata matching, LLM, embedding, score, probability,
confidence, uncertainty, priority, or execution is introduced. InferenceEngine
remains unchanged; Issue #33 owns Agent use of an approved decision.
