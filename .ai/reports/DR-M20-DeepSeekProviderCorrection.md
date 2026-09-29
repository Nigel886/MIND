# DR-M20 DeepSeek Provider Correction

The prior M20 OpenAI configuration was superseded before empirical execution. The corrected provider is DeepSeek official API at `https://api.deepseek.com/`, request model `deepseek-flash`, documented version `DeepSeek-V4.1-Flash`, OpenAI-compatible chat-completions API, thinking disabled, JSON-object response mode, temperature 0, top-p 1, max output 512, timeout 60 seconds, provider-client retry owner, 2 retries (3 physical attempts maximum), no seed emulation, and `DEEPSEEK_API_KEY` credential source.

The corrected provider hash is `522fcf28714e168ce9854069468c51d3d3cb565404d7bdad3317e4fcc8f199ad`. The old OpenAI hash `910b2b5bf28308d6491af4010e3cc108a38e6dbb49613e27bbc9e4493d41c8f1` is superseded. The old manifest `31ce468ca217e7ea8ddc813c5740def250baa99f31871102b786f6bcbb2a71d8` is preserved as historical evidence but invalid for future execution because it binds that old provider identity. #240/#241 OpenAI-bound authorization/credential decisions are likewise historical only.

The case-source digest remains `4a00cb4128ef747419c601ed6696dd042cba7d4b45d09407e3fb68eb2a42ca12`; shared ceiling identity remains `m20_real_ceiling_v1:6d497729bdb5d5fd87639a690b3d35064f8588e56268770ccbbecf143f5d1423`. Provider calls, pilot, calibration, formal, and empirical records remain 0. Provider execution is unauthorized pending a new DeepSeek-bound manifest and authorization gate.

Focused validation: `6 passed in 0.034s`.

Full unittest: exit `0`; `Ran 768 tests in 133.911s`; `OK`. Pytest: exit `0`; `768 passed in 228.51s`. `git diff --check`: PASS.
