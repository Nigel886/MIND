# ADR-012 - Meta-Inference Agent Integration

**Status:** Accepted

GoalDirectedAgent accepts an explicit optional MetaInferenceEngine dependency:
GoalDirectedAgent(tool_registry, meta_inference_engine=None). None preserves
the completed M8 legacy flow; an injected engine is selected after initial Task
Observation inference and before any task policy cycle.

Selected decisions add one compact AgentResult evidence entry containing type
meta_inference, status, selected strategy name, and serialized compact decision
evidence. The Agent does not execute the selected implementation in M9 v1; it
continues the existing InferenceEngine-based task flow. Unavailable and rejected
decisions are explicit zero-cycle FAILED/POLICY_FAILURE results with compact
meta-inference evidence, never hidden default-strategy fallback. This reuses
the existing terminal taxonomy without changing AgentResult.

MetaInferenceEngine remains state-free and selection-only. Agent remains the
orchestrator; RuntimeController, Registry, and InferenceEngine APIs remain
unchanged. Future strategy execution mapping is deferred.
