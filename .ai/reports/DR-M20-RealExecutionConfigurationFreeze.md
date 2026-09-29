# DR-M20 Real Execution Configuration Freeze

## Frozen provider configuration

Prospectively frozen before any empirical M20 execution: provider/backend `OpenAI API` (`openai_api`); model `gpt-5.6-sol`; API `Responses API`; reasoning effort `medium`; temperature `0`; top-p `1.0`; max output tokens `2048`; structured output enabled where the frozen provider contract requires it; tool/function mode limited to the frozen M20 public surface; hosted provider tools disabled; streaming disabled; timeout `60` seconds per physical attempt; provider-client retry owner; retry ceiling `1` (two physical attempts maximum per logical operation); deterministic seed `null` unless natively supported; and service tier `standard/default`.

The canonical provider hash is `910b2b5bf28308d6491af4010e3cc108a38e6dbb49613e27bbc9e4493d41c8f1`. The closed schema contains no credentials, API keys, or secret fields.

## Frozen shared resource ceiling

Both primary conditions bind the identical ceiling: reasoning steps `8`, tool attempts `4`, logical provider interactions `4`, and decision cycles `8`. Its canonical identity is `m20_real_ceiling_v1:6d497729bdb5d5fd87639a690b3d35064f8588e56268770ccbbecf143f5d1423`.

These are new prospective real-execution decisions, not a derivation of the fake fixture. Eight decision cycles and reasoning steps allow bounded stateful, recovery, acquisition, distractor, early-stop, and resource-constrained paths; four logical provider interactions permit multi-step behavior while retaining primary-endpoint pressure; and four tool attempts provide bounded public action/acquisition capacity. The ceiling is condition-neutral and must not be changed after calibration outcomes.

## Parity, case source, and boundary

Adaptive and Fixed share provider hash, ceiling identity, retry/failure semantics, environment, evaluator, and public action/tool surface; only their previously frozen control policies differ. The case source remains `m20_real_case_source_v1` with digest `4a00cb4128ef747419c601ed6696dd042cba7d4b45d09407e3fb68eb2a42ca12`.

Provider calls, pilot records, calibration records, formal records, and nuisance estimates remain `0/0/0/0/NONE`. This freeze does not authorize provider execution, create an execute-after-freeze path, or authorize calibration-manifest creation outside a separate issue.

## Focused validation

- `python -m unittest tests.test_m20_real_execution_configuration tests.test_m20_real_case_source tests.test_m20_evaluation_harness`: `26 passed in 0.080s`.
- `python -m unittest`: exit `0`; `Ran 765 tests in 131.643s`; `OK`.
- `pytest`: exit `0`; `765 passed in 154.77s (0:02:34)`.
- `git diff --check`: PASS.
