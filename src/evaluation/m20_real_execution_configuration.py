"""Frozen prospective M20 execution identities; deliberately no provider client."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.evaluation.m20_harness import M20Condition, canonical_hash
from src.evaluation.m20_real_case_source import real_case_source_digest


M20_REAL_EXECUTION_CONFIG_VERSION = "m20_real_execution_configuration_v1"
M20_PROVIDER_RETRY_OWNER = "provider_client"


@dataclass(frozen=True)
class M20FrozenProviderConfiguration:
    provider: str
    model: str
    api_mode: str
    reasoning_effort: str
    temperature: float
    top_p: float
    max_output_tokens: int
    structured_output: str
    tool_mode: str
    hosted_tools: str
    streaming: bool
    timeout_seconds: int
    retry_owner: str
    retry_ceiling: int
    deterministic_seed: int | None
    service_tier: str
    version: str = M20_REAL_EXECUTION_CONFIG_VERSION

    def __post_init__(self) -> None:
        required = ("provider", "model", "api_mode", "reasoning_effort", "structured_output", "tool_mode",
                    "hosted_tools", "retry_owner", "service_tier", "version")
        if any(not isinstance(getattr(self, key), str) or not getattr(self, key) for key in required):
            raise ValueError("provider configuration is incomplete")
        if self.temperature != 0 or self.top_p != 1.0 or self.max_output_tokens < 1 or self.timeout_seconds < 1:
            raise ValueError("provider configuration violates frozen settings")
        if self.retry_owner != M20_PROVIDER_RETRY_OWNER or self.retry_ceiling != 1:
            raise ValueError("provider retry ownership/ceiling mismatch")
        if self.streaming or self.hosted_tools != "disabled" or self.service_tier != "standard/default":
            raise ValueError("provider execution tier/tool/streaming mismatch")

    def canonical(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def identity_hash(self) -> str:
        return canonical_hash(self.canonical())


@dataclass(frozen=True)
class M20FrozenResourceCeiling:
    reasoning_steps: int
    tool_attempts: int
    logical_provider_interactions: int
    decision_cycles: int
    version: str = M20_REAL_EXECUTION_CONFIG_VERSION

    def __post_init__(self) -> None:
        if any(getattr(self, key) < 1 for key in ("reasoning_steps", "tool_attempts", "logical_provider_interactions", "decision_cycles")):
            raise ValueError("resource ceiling must be positive")

    def canonical(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def identity_hash(self) -> str:
        return canonical_hash(self.canonical())

    @property
    def identity(self) -> str:
        return "m20_real_ceiling_v1:" + self.identity_hash


M20_REAL_PROVIDER_CONFIGURATION = M20FrozenProviderConfiguration(
    provider="openai_api", model="gpt-5.6-sol", api_mode="responses_api", reasoning_effort="medium",
    temperature=0, top_p=1.0, max_output_tokens=2048, structured_output="enabled_when_contract_required",
    tool_mode="frozen_m20_public_surface_only", hosted_tools="disabled", streaming=False, timeout_seconds=60,
    retry_owner=M20_PROVIDER_RETRY_OWNER, retry_ceiling=1, deterministic_seed=None, service_tier="standard/default",
)
M20_REAL_RESOURCE_CEILING = M20FrozenResourceCeiling(8, 4, 4, 8)


def primary_condition_bindings() -> dict[M20Condition, dict[str, str]]:
    """Parity identity only; this module neither exposes nor calls a provider."""
    return {condition: {"provider_hash": M20_REAL_PROVIDER_CONFIGURATION.identity_hash,
                        "resource_ceiling_identity": M20_REAL_RESOURCE_CEILING.identity,
                        "environment_id": "m20_environment_v1", "evaluator_id": "m20_evaluator_v1",
                        "case_source_digest": real_case_source_digest()}
            for condition in (M20Condition.MIND_ADAPTIVE, M20Condition.MIND_FIXED)}
