"""Frozen public contracts for the M16 Cohort A benchmark runner.

These contracts deliberately contain no task truth and do not import the
held-out suite.  They are reusable for development dry runs and the later
formally authorized run.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any


RESULT_SCHEMA_VERSION = "m16-attempt-record-v1"
FAILURE_TAXONOMY_VERSION = "m16-failure-taxonomy-v1"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class M16BaselineID(str, Enum):
    MIND_LITE_V1 = "mind_lite_v1"
    DIRECT_TOOL_CALLING = "direct_tool_calling"


class M16FailureCategory(str, Enum):
    SUCCESS = "success"
    WRONG_ANSWER = "wrong_answer"
    AGENT_FAIL = "agent_fail"
    INVALID_ACTION = "invalid_action"
    TIMEOUT = "timeout"
    STEP_BUDGET_EXHAUSTED = "step_budget_exhausted"
    TOOL_BUDGET_EXHAUSTED = "tool_budget_exhausted"
    PROVIDER_INFRASTRUCTURE_INVALID_RUN = "provider_infrastructure_invalid_run"
    INTERRUPTED_INCOMPLETE = "interrupted_incomplete"


@dataclass(frozen=True)
class M16FormalBudget:
    max_agent_steps: int = 2
    max_tool_calls: int = 1
    wall_timeout_seconds: int = 240
    transport_max_attempts: int = 3
    mind_logical_model_calls: int = 1
    direct_logical_model_calls: int = 2

    def __post_init__(self) -> None:
        if any(isinstance(value, bool) or not isinstance(value, int) for value in self.__dict__.values()):
            raise TypeError("budget values must be integers")
        if min(self.__dict__.values()) < 1:
            raise ValueError("budget values must be positive")

    def to_dict(self) -> dict[str, int]: return dict(self.__dict__)


@dataclass(frozen=True)
class M16FormalExecutionManifest:
    protocol_version: str
    suite_version: str
    suite_hash: str
    split_hash: str
    provider_config_version: str
    provider_config_hash: str
    suite_generation_protocol_version: str = "1.1.0"
    completion_semantics_version: str = "m16_completion_v2"
    provider: str = "Google Gemini API"
    model: str = "gemini-2.5-flash"
    formal_classification: str = "STOCHASTIC"
    repetition_count: int = 5
    baseline_ids: tuple[M16BaselineID, ...] = (M16BaselineID.MIND_LITE_V1, M16BaselineID.DIRECT_TOOL_CALLING)
    execution_order_policy: str = "repetition-major/case-major/counterbalanced-v1"
    budget_contract: M16FormalBudget = field(default_factory=M16FormalBudget)
    result_schema_version: str = RESULT_SCHEMA_VERSION
    failure_taxonomy_version: str = FAILURE_TAXONOMY_VERSION
    runner_version: str = "m16-runner-v1"
    evaluated_mind_tag: str = "v1.0.0"
    evaluated_mind_commit: str = "2a3fa4472f5b74690810d9b6fe12f59ad735a9de"
    mind_prompt_hash: str = "development-unset"
    direct_prompt_hash: str = "development-unset"
    mind_schema_hash: str = "development-unset"
    direct_schema_hash: str = "development-unset"
    calculator_schema_hash: str = "development-unset"
    provider_request_model_id: str | None = None
    official_documented_model_version: str | None = None
    returned_model_observation_policy: str | None = None
    execution_attempt_identity: str | None = None

    def __post_init__(self) -> None:
        if self.repetition_count < 1 or len(self.baseline_ids) != 2 or set(self.baseline_ids) != set(M16BaselineID):
            raise ValueError("M16 manifest has invalid frozen baseline/repetition configuration")
        if not all(isinstance(v, str) and v for v in self.to_dict().values() if isinstance(v, str)):
            raise ValueError("manifest strings must not be empty")

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.__dict__)
        data["baseline_ids"] = [x.value for x in self.baseline_ids]
        data["budget_contract"] = self.budget_contract.to_dict()
        for name in ("provider_request_model_id", "official_documented_model_version", "returned_model_observation_policy", "execution_attempt_identity"):
            if data[name] is None:
                del data[name]
        return data

    @property
    def manifest_hash(self) -> str:
        return hashlib.sha256(_canonical(self.to_dict()).encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "M16FormalExecutionManifest":
        data = dict(data); data["baseline_ids"] = tuple(M16BaselineID(x) for x in data["baseline_ids"])
        data["budget_contract"] = M16FormalBudget(**data["budget_contract"])
        return cls(**data)


def _load_manifest_from_config(config_name: str) -> M16FormalExecutionManifest:
    """Construct a formal manifest from one explicit tracked provider config."""
    root = Path(__file__).resolve().parents[2]
    config_bytes = (root / "evaluation" / "config" / config_name).read_bytes()
    config = json.loads(config_bytes.decode("utf-8"))
    tool = config["tool"]
    return M16FormalExecutionManifest(
        protocol_version="1.2.0", suite_version=config["suite"]["version"],
        suite_hash=config["suite"]["hash"], split_hash=config["split_hash"],
        provider_config_version=config["configuration_version"],
        provider_config_hash=hashlib.sha256(config_bytes).hexdigest(),
        provider=config.get("formal_provider_identity", "Google Gemini API"), model=config["model"], formal_classification=config["formal_classification"],
        repetition_count=config["formal_repetitions"], mind_prompt_hash=config["MIND"]["prompt_hash"],
        direct_prompt_hash=config["Direct"]["prompt_hash"], mind_schema_hash=config["MIND"]["schema_hash"],
        direct_schema_hash=config["Direct"]["schema_hash"], calculator_schema_hash=tool["tool_schema_hash"],
        suite_generation_protocol_version=config["protocol"], completion_semantics_version="m16_completion_v2",
        provider_request_model_id=config.get("request_model_id"),
        official_documented_model_version=config.get("official_documented_model_version"),
        returned_model_observation_policy=config.get("returned_model_observation_policy"),
    )


def load_frozen_m16_manifest() -> M16FormalExecutionManifest:
    """Construct the historical Gemini 2.5 Flash formal manifest for audit."""
    return _load_manifest_from_config("m16_gemini_flash_v1.json")


def load_frozen_m16_flash_lite_manifest() -> M16FormalExecutionManifest:
    """Construct the isolated Gemini 3.1 Flash-Lite replacement manifest."""
    return _load_manifest_from_config("m16_gemini_31_flash_lite_v1.json")


def load_frozen_m16_deepseek_manifest() -> M16FormalExecutionManifest:
    """Construct the isolated DeepSeek V4 Flash formal manifest."""
    return _load_manifest_from_config("m16_deepseek_v4_flash_v1.json")


def load_frozen_m16_deepseek_restart1_manifest() -> M16FormalExecutionManifest:
    """Construct the clean replacement identity for the invalidated DeepSeek run."""
    return replace(load_frozen_m16_deepseek_manifest(), execution_attempt_identity="restart1")


@dataclass(frozen=True)
class M16FormalRunDefinition:
    manifest_hash: str
    evaluation_id: str
    baseline_id: M16BaselineID
    repetition: int
    case_index: int

    @property
    def run_id(self) -> str:
        return f"m16:{self.manifest_hash}:{self.evaluation_id}:{self.baseline_id.value}:r{self.repetition}"

    def attempt_id(self, attempt_number: int) -> str:
        if attempt_number < 1: raise ValueError("attempt_number begins at 1")
        return f"{self.run_id}:a{attempt_number}"


def counterbalanced_schedule(manifest: M16FormalExecutionManifest, evaluation_ids: tuple[str, ...]) -> tuple[M16FormalRunDefinition, ...]:
    ordered = tuple(sorted(evaluation_ids))
    output: list[M16FormalRunDefinition] = []
    for repetition in range(1, manifest.repetition_count + 1):
        for index, evaluation_id in enumerate(ordered):
            baselines = manifest.baseline_ids if (index + repetition) % 2 == 0 else tuple(reversed(manifest.baseline_ids))
            output.extend(M16FormalRunDefinition(manifest.manifest_hash, evaluation_id, baseline, repetition, index) for baseline in baselines)
    return tuple(output)


@dataclass(frozen=True)
class M16RunAttemptRecord:
    schema_version: str
    run_id: str
    attempt_id: str
    attempt_number: int
    evaluation_id: str
    baseline_id: M16BaselineID
    repetition: int
    task_family: str
    difficulty: str
    eligibility: str
    completion_mode: str
    success: bool
    failure_category: M16FailureCategory
    agent_steps: int
    tool_calls: int
    provider_request_attempts: int = 0
    model_calls: int = 0
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    thinking_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None
    latency_ms: int | None = None
    provider_model_version: str | None = None
    manifest_hash: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != RESULT_SCHEMA_VERSION: raise ValueError("unknown result schema")
        if self.attempt_number < 1 or self.agent_steps < 0 or self.tool_calls < 0: raise ValueError("invalid result counters")
        if self.success != (self.failure_category is M16FailureCategory.SUCCESS): raise ValueError("success must match category")

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.__dict__); data["baseline_id"] = self.baseline_id.value; data["failure_category"] = self.failure_category.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "M16RunAttemptRecord":
        data = dict(data); data["baseline_id"] = M16BaselineID(data["baseline_id"]); data["failure_category"] = M16FailureCategory(data["failure_category"])
        return cls(**data)
