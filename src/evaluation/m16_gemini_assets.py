"""Read and hash the frozen tracked M16 Gemini prompt and schema artifacts."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any


_ROOT = Path(__file__).resolve().parents[2]
_PROMPTS = _ROOT / "evaluation" / "prompts"
_SCHEMAS = _ROOT / "evaluation" / "schemas"

MIND_PROMPT_ID = "m16.mind_interpretation.v1"
DIRECT_PROMPT_ID = "m16.direct_action.v1"
MIND_SCHEMA_ID = "m16.mind_interpretation.schema.v1"
DIRECT_SCHEMA_ID = "m16.direct_action.schema.v1"
CALCULATOR_SCHEMA_ID = "m16.calculator.schema.v1"


def read_prompt(filename: str) -> str:
    """Read one LF-normalized tracked prompt without silently normalizing it."""

    text = (_PROMPTS / filename).read_text(encoding="utf-8")
    if "\r" in text or not text.endswith("\n"):
        raise ValueError("M16 prompt must use LF and exactly one terminal newline")
    return text


def prompt_hash(filename: str) -> str:
    """Hash exact effective UTF-8 prompt bytes."""

    return sha256(read_prompt(filename).encode("utf-8")).hexdigest()


def load_schema(filename: str) -> dict[str, Any]:
    """Load one canonical JSON schema artifact."""

    value = json.loads((_SCHEMAS / filename).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("M16 schema must be an object")
    return value


def canonical_json(value: dict[str, Any]) -> str:
    """Use frozen canonical JSON serialization for schema and manifest hashes."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def schema_hash(filename: str) -> str:
    """Hash canonical JSON semantic content rather than file whitespace."""

    return sha256(canonical_json(load_schema(filename)).encode("utf-8")).hexdigest()
