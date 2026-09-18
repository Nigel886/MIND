"""Domain-separated logical run identity for the M18 v3 contract."""
from __future__ import annotations

from dataclasses import dataclass
from src.evaluation.m18_task_generation import canonical_hash
from src.evaluation.m18_v3_semantics import M18_V3_SUITE_VERSION
from src.evaluation.m18_v3_semantics import (
    M18_V3_BUDGET_ID, M18_V3_ENVIRONMENT_ID, M18_V3_EVALUATOR_ID,
    M18_V3_PUBLIC_ACTION_CONTRACT_ID, M18_V3_RUNTIME_ID,
)


@dataclass(frozen=True)
class M18V3RunIdentity:
    case_id: str
    comparator_id: str
    repetition: int
    provider_config_hash: str = "provider_free_v3"
    execution_baseline: str = "provider_free_v3"
    schema: str = "m18_v3_logical_run_id_v1"
    suite_identity: str = M18_V3_SUITE_VERSION
    def __post_init__(self) -> None:
        if self.schema != "m18_v3_logical_run_id_v1" or self.suite_identity != M18_V3_SUITE_VERSION:
            raise ValueError("M18 v3 run identity is domain-separated and closed")
        if not self.case_id or not self.comparator_id or not self.provider_config_hash or not self.execution_baseline or not isinstance(self.repetition, int) or self.repetition < 1:
            raise ValueError("case, comparator, and positive repetition are required")
    def to_dict(self) -> dict[str, object]:
        return {"schema": self.schema, "suite_identity": self.suite_identity,
                "environment_id": M18_V3_ENVIRONMENT_ID, "evaluator_id": M18_V3_EVALUATOR_ID,
                "budget_id": M18_V3_BUDGET_ID, "runtime_id": M18_V3_RUNTIME_ID,
                "public_action_contract_id": M18_V3_PUBLIC_ACTION_CONTRACT_ID,
                "case_id": self.case_id, "comparator_id": self.comparator_id,
                "repetition": self.repetition, "provider_config_hash": self.provider_config_hash,
                "execution_baseline": self.execution_baseline}
    @property
    def run_id(self) -> str:
        return "m18v3-" + canonical_hash(self.to_dict())
