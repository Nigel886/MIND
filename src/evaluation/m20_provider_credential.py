"""Non-network, secret-safe M20 OpenAI credential readiness check."""
from __future__ import annotations
import os
from collections.abc import Mapping

M20_PROVIDER_CREDENTIAL_ENV = "DEEPSEEK_API_KEY"

def credential_status(environment: Mapping[str, str] | None = None) -> str:
    value = (os.environ if environment is None else environment).get(M20_PROVIDER_CREDENTIAL_ENV)
    return "CREDENTIAL READY" if isinstance(value, str) and bool(value.strip()) else "CREDENTIAL NOT READY"

def require_credential(environment: Mapping[str, str] | None = None) -> None:
    if credential_status(environment) != "CREDENTIAL READY":
        raise RuntimeError("M20 provider credential is not ready")
