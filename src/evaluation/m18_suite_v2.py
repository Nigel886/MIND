"""Version-routed case construction; this module intentionally freezes no suite."""
from __future__ import annotations
from src.evaluation.m18_task_generation import generate_m18_case
from src.evaluation.m18_v2_semantics import M18_V2_SUITE_VERSION, generate_m18_v2_case

M18_V1_SUITE_VERSION = "m18_suite_v1"

def generate_m18_case_for_version(suite_version: str, *args, **kwargs):
    """Make v1/v2 selection explicit and fail closed for unknown semantics."""
    if suite_version == M18_V1_SUITE_VERSION:
        return generate_m18_case(*args, **kwargs)
    if suite_version == M18_V2_SUITE_VERSION:
        return generate_m18_v2_case(*args, **kwargs)
    raise ValueError("unknown M18 suite version")

__all__ = ["M18_V1_SUITE_VERSION", "M18_V2_SUITE_VERSION", "generate_m18_case_for_version"]
