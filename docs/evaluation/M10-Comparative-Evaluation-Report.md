# M10 Comparative Evaluation Report

## 1. Evaluation Objective

M10 evaluated the observable behavior of deterministic Meta-Inference without
changing the Agent architecture.

- **Baseline A:** `GoalDirectedAgent(tool_registry)`.
- **Baseline B:** `GoalDirectedAgent(tool_registry, meta_inference_engine)`.

The only intended baseline difference was Meta-Inference injection. Each
scenario used equivalent local tool configuration, serialized Task data, and
cycle budget for both baselines.

## 2. Experimental Protocol

The experiment used only `get_default_evaluation_scenarios()`. Every scenario
ran three times for each baseline: 10 scenarios × 2 baselines × 3 repetitions
produced 60 compact run summaries.

Execution was deterministic and local: no network, LLM, external dataset,
randomness, or silent retry. Retained data was limited to status, termination
reason, selected strategy, semantic signature, compact evidence, repetition
index, and descriptive elapsed duration. No RuntimeState, Agent, Tool, strategy
implementation, or trajectory was retained.

## 3. Scenario Coverage

The frozen suite covered direct success, Calculator success (`17 * 23 = 391`),
unique strategy match, unavailable strategy, ambiguous strategy, and M8
compatibility for direct, Calculator, unsupported, tool-failure, and bounded
execution paths.

## 4. Results

Across 60 recorded runs, 36 were successful and 24 were non-successful. The
existing metrics therefore reported a success rate of `0.60` and a failure rate
of `0.40`; the latter treats both failed and incomplete outcomes as
non-successful.

| Metric | Observed result |
| --- | ---: |
| Strategy selection correctness | 1.00 |
| Unavailable correctness | 1.00 |
| Ambiguity rejection correctness | 1.00 |
| Semantic determinism | 1.00 |
| Evidence consistency | 1.00 |

The first three values apply to their corresponding frozen Meta-Inference
scenarios. Consistency compares repetitions within each `(scenario, baseline)`
group, excluding UUIDs, timestamps, and descriptive elapsed duration.

## 5. Observed Outcomes

The unique-match fixture selected the configured strategy for Baseline B. The
unavailable and ambiguous fixtures followed their explicit policy-failure paths
for Baseline B. Baseline A continued to use the M8 task flow without
Meta-Inference. The M8 compatibility fixtures retained their specified direct,
Calculator, unsupported-task, tool-failure, and bounded-run outcomes.

These are observations from a fixed deterministic protocol only. They do not
establish intelligence improvement, reasoning improvement, generalization, or
superiority of either baseline.

## 6. Limitations

- Scenarios are deterministic and handcrafted.
- Task diversity is limited.
- No external benchmark or dataset was used.
- No LLM was used.
- No adaptive learning was evaluated.
- The protocol compares only the M8-style Agent and the same Agent with
  deterministic Meta-Inference injection.

## 7. Conclusion

Under the frozen M10 protocol, Meta-Inference followed the specified selection,
unavailable, and ambiguity semantics, and recorded M8 compatibility paths
remained available. This conclusion is limited to the stated local fixtures,
repetitions, and metrics.
