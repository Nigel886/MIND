"""DEVELOPMENT ONLY fixtures for M16 runner validation; never formal cases."""
from __future__ import annotations
from dataclasses import dataclass
from src.core.task import Goal, Task
from src.evaluation.contracts import EvaluationCase
from src.evaluation.m16_leakage_free import M16PrivateEnvironmentSpecification, M16PrivateTruth

@dataclass(frozen=True)
class M16BenchmarkDevelopmentCase:
    case: EvaluationCase
    private_truth: M16PrivateTruth
    environment: M16PrivateEnvironmentSpecification
    task_family: str
    difficulty: str
    eligibility: str = "development_only"

def get_m16_benchmark_dry_run_cases() -> tuple[M16BenchmarkDevelopmentCase, ...]:
    direct = Task(Goal("Return the supplied public value", ("answer",)), {"value": "copper-fern"}, metadata={"m16_cohort_a":{"task_family":"direct_answer","tool_call_limit":0,"requires_planning":False,"requires_multi_tool":False,"requires_dependent_multistep":False,"requires_recovery":False}})
    calculator = Task(Goal("Calculate the requested sum", ("answer",)), {"operation":"add","operands":[19,-7]}, metadata={"m16_cohort_a":{"task_family":"controlled_single_tool","tool_call_limit":1,"requires_planning":False,"requires_multi_tool":False,"requires_dependent_multistep":False,"requires_recovery":False}})
    return (
        M16BenchmarkDevelopmentCase(EvaluationCase("development.m16.runner.direct", direct), M16PrivateTruth("copper-fern","development-exact"), M16PrivateEnvironmentSpecification("development-calculator"), "direct_answer", "easy"),
        M16BenchmarkDevelopmentCase(EvaluationCase("development.m16.runner.calculator", calculator), M16PrivateTruth(12,"development-exact"), M16PrivateEnvironmentSpecification("development-calculator"), "controlled_single_tool", "medium"),
    )
