"""Static and development-only tests for the isolated M16 Flash-Lite migration."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from src.evaluation.gemini_transport import (
    GEMINI_FLASH_LITE_ENDPOINT, GEMINI_FLASH_LITE_MODEL,
    GeminiFlashLiteGenerationConfig, GeminiRestTransport, GeminiTransportSuccess,
)
from src.evaluation.m16_benchmark_contracts import (
    counterbalanced_schedule, load_frozen_m16_flash_lite_manifest, load_frozen_m16_manifest,
)
from src.evaluation.m16_flash_lite_formal_execution import (
    DEFAULT_RESULT_DIRECTORY, EXPECTED_MANIFEST_HASH, execute_flash_lite_formal_benchmark,
    validate_flash_lite_formal_preflight,
)
from src.evaluation.m16_gemini_assets import prompt_hash, schema_hash
from src.evaluation.m16_result_store import M16ResultStore
from src.core.task import Goal, Task
from src.integration.gemini_m13_provider import GeminiM13InterpretationProvider


ROOT = Path(__file__).resolve().parents[1]
OLD_MANIFEST_HASH = "588a36257623b4d4b9001db41ea03dfc46b1503eeebaca04b986fdcde8e5f663"


class _Post:
    def __init__(self) -> None: self.calls = []
    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, dict(headers), json.loads(body), timeout))
        return {"candidates": [{"content": {"parts": [{"text": '{"status":"ok"}'}]}}],
                "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2, "totalTokenCount": 5},
                "modelVersion": GEMINI_FLASH_LITE_MODEL}


class FlashLiteMigrationTests(unittest.TestCase):
    def test_exact_transport_configuration_omits_sampling_and_freezes_thinking(self) -> None:
        post = _Post()
        transport = GeminiRestTransport(GeminiFlashLiteGenerationConfig(), http_post=post,
                                        environment={"GEMINI_API_KEY": "development"}, sleeper=lambda _: None)
        result = transport.generate("Return status ok.", {"type": "object"})
        self.assertIsInstance(result, GeminiTransportSuccess)
        url, _, body, timeout = post.calls[0]
        self.assertEqual((url, timeout), (GEMINI_FLASH_LITE_ENDPOINT, 30))
        config = body["generationConfig"]
        self.assertEqual(config["responseMimeType"], "application/json")
        self.assertEqual(config["candidateCount"], 1)
        self.assertEqual(config["maxOutputTokens"], 512)
        self.assertEqual(config["thinkingConfig"], {"thinkingLevel": "minimal", "includeThoughts": False})
        self.assertFalse({"temperature", "topP", "seed"} & set(config))
        self.assertEqual(result.observation.model_version, GEMINI_FLASH_LITE_MODEL)

    def test_tracked_config_preserves_prompt_schema_suite_and_split_identity(self) -> None:
        path = ROOT / "evaluation/config/m16_gemini_31_flash_lite_v1.json"
        raw = path.read_bytes(); config = json.loads(raw)
        self.assertEqual(config["model"], GEMINI_FLASH_LITE_MODEL)
        self.assertEqual(config["api_path"], "raw_rest_generateContent")
        self.assertEqual(config["thinking"], {"includeThoughts": False, "thinkingLevel": "minimal"})
        self.assertEqual(config["omitted_sampling_fields"], ["temperature", "topP", "seed"])
        self.assertEqual(config["formal_classification"], "STOCHASTIC")
        self.assertEqual(config["formal_repetitions"], 5)
        self.assertEqual(config["MIND"]["prompt_hash"], prompt_hash("m16_mind_interpretation_v1.txt"))
        self.assertEqual(config["Direct"]["prompt_hash"], prompt_hash("m16_direct_action_v1.txt"))
        self.assertEqual(config["MIND"]["schema_hash"], schema_hash("m16_mind_interpretation_v1.json"))
        self.assertEqual(config["Direct"]["schema_hash"], schema_hash("m16_direct_action_v1.json"))
        self.assertEqual(config["tool"]["tool_schema_hash"], schema_hash("m16_calculator_tool_v1.json"))
        self.assertEqual(config["suite"]["hash"], "a450c6fa2955136da5d4db08b892af442ab7be66034412739d91e7cbf076445c")
        self.assertEqual(config["split_hash"], "a41ca5a326da4f722de1fcca4c7a4b85fcf860767ba1bb0311aa6cc4176aefe3")
        self.assertEqual(sha256(raw).hexdigest(), "66d372c89f7c2aa5c33328bc93e5d3788a1e4b283693dce8b766a861784c25e2")

    def test_new_manifest_and_schedule_are_isolated_and_stable(self) -> None:
        manifest = load_frozen_m16_flash_lite_manifest(); old = load_frozen_m16_manifest()
        self.assertEqual(manifest.manifest_hash, EXPECTED_MANIFEST_HASH)
        self.assertNotEqual(manifest.manifest_hash, OLD_MANIFEST_HASH)
        self.assertNotEqual(manifest.manifest_hash, old.manifest_hash)
        self.assertEqual((manifest.protocol_version, manifest.completion_semantics_version), ("1.2.0", "m16_completion_v2"))
        _, cases, definitions = validate_flash_lite_formal_preflight()
        self.assertEqual((len(cases), len(definitions), len({item.run_id for item in definitions})), (96, 960, 960))
        self.assertNotEqual(definitions[0].run_id, counterbalanced_schedule(old, tuple(item.case.evaluation_id for item in cases))[0].run_id)

    def test_fresh_store_is_zero_of_960_and_rejects_old_manifest(self) -> None:
        manifest = load_frozen_m16_flash_lite_manifest()
        with tempfile.TemporaryDirectory() as directory:
            store = M16ResultStore(directory, manifest); store.initialize()
            self.assertEqual(len(store.load_records()), 0)
            self.assertEqual(len(store.completed_run_ids()), 0)
            with self.assertRaises(ValueError):
                M16ResultStore(directory, load_frozen_m16_manifest()).initialize()

    def test_old_result_directory_is_excluded_without_formal_execution(self) -> None:
        self.assertEqual(DEFAULT_RESULT_DIRECTORY, "evaluation/results/m16_flash_lite")
        with self.assertRaises(ValueError):
            execute_flash_lite_formal_benchmark("evaluation/results/m16")

    def test_both_formal_factories_are_explicitly_bound_to_flash_lite(self) -> None:
        source = (ROOT / "src/evaluation/m16_flash_lite_formal_execution.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("GeminiFlashLiteGenerationConfig()"), 2)
        self.assertNotIn("GeminiGenerationConfig()", source)
        self.assertIn('Path(result_dir) == Path("evaluation/results/m16")', source)

    def test_flash_lite_mind_path_rejects_private_truth_before_transport(self) -> None:
        post = _Post()
        provider = GeminiM13InterpretationProvider(
            GeminiRestTransport(GeminiFlashLiteGenerationConfig(), http_post=post,
                                environment={"GEMINI_API_KEY": "development"}),
        )
        with self.assertRaises(ValueError):
            provider.interpret(Task(Goal("return", ("development",)), {"expected_answer": "private"}))
        self.assertEqual(post.calls, [])


if __name__ == "__main__":
    unittest.main()
