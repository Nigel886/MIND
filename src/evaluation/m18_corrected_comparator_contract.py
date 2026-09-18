"""Provider-free identity and namespace contract for corrected M18 comparators.

This module deliberately has no provider construction or execution entry point.
It domain-separates future corrected evidence from the immutable M18 v3 pilot.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.evaluation.m18_task_generation import canonical_hash
from src.evaluation.m18_v3_runtime import M18_V3_SYSTEMS
from src.evaluation.m18_v3_semantics import (
    M18_V3_BUDGET_ID, M18_V3_ENVIRONMENT_ID, M18_V3_EVALUATOR_ID,
    M18_V3_PUBLIC_ACTION_CONTRACT_ID, M18_V3_RUNTIME_ID, M18_V3_SUITE_VERSION,
)


M18_CORRECTED_COMPARATOR_CONTRACT_ID = "m18_v3_comparator_contract_v2"
M18_CORRECTED_RUN_ID_SCHEMA = "m18_v3_comparator_contract_v2_logical_run_id_v1"
M18_CORRECTED_PILOT_RESULT_NAMESPACE = Path("evaluation/m18/results/m18_v3_comparator_contract_v2/pilot")
M18_CORRECTED_FORMAL_RESULT_NAMESPACE = Path("evaluation/m18/results/m18_v3_comparator_contract_v2/formal")


@dataclass(frozen=True)
class M18CorrectedRunIdentity:
    case_id: str
    comparator_id: str
    repetition: int
    provider_config_hash: str = "provider_free_v3"
    execution_baseline: str = "provider_free_v3"
    comparator_contract_id: str = M18_CORRECTED_COMPARATOR_CONTRACT_ID
    schema: str = M18_CORRECTED_RUN_ID_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != M18_CORRECTED_RUN_ID_SCHEMA or self.comparator_contract_id != M18_CORRECTED_COMPARATOR_CONTRACT_ID:
            raise ValueError("corrected identity is closed and domain-separated")
        if not self.case_id or self.comparator_id not in M18_V3_SYSTEMS or not isinstance(self.repetition, int) or isinstance(self.repetition, bool) or self.repetition < 1:
            raise ValueError("corrected case, comparator, and repetition are required")
        if not self.provider_config_hash or not self.execution_baseline:
            raise ValueError("corrected provider provenance is required")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema, "comparator_contract_id": self.comparator_contract_id,
            "suite_identity": M18_V3_SUITE_VERSION, "environment_id": M18_V3_ENVIRONMENT_ID,
            "evaluator_id": M18_V3_EVALUATOR_ID, "budget_id": M18_V3_BUDGET_ID,
            "runtime_id": M18_V3_RUNTIME_ID, "public_action_contract_id": M18_V3_PUBLIC_ACTION_CONTRACT_ID,
            "case_id": self.case_id, "comparator_id": self.comparator_id, "repetition": self.repetition,
            "provider_config_hash": self.provider_config_hash, "execution_baseline": self.execution_baseline,
        }

    @property
    def run_id(self) -> str:
        return "m18ccv2-" + canonical_hash(self.to_dict())


def corrected_namespace_counts(repository_root: Path) -> tuple[int, int]:
    """Return corrected pilot/formal record counts without creating either namespace."""
    root = repository_root.resolve()
    return tuple(sum(1 for item in root.joinpath(namespace).rglob("*.json") if item.is_file())
                 if root.joinpath(namespace).exists() else 0
                 for namespace in (M18_CORRECTED_PILOT_RESULT_NAMESPACE, M18_CORRECTED_FORMAL_RESULT_NAMESPACE))


def select_corrected_condition(condition_id: str) -> str:
    """Closed future-runner selection; the historical v3 condition is rejected."""
    if condition_id != M18_CORRECTED_COMPARATOR_CONTRACT_ID:
        raise ValueError("only the corrected comparator contract is selectable here")
    return condition_id
