"""M20-native DeepSeek bridge and v2-manifest calibration planning; no implicit network execution."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.evaluation.m20_calibration_manifest import build_deepseek_manifest, validate_deepseek_manifest
from src.evaluation.m20_harness import (M20AdaptiveAdapter, M20Case, M20Condition, M20ConditionRegistry,
    M20EvidenceStore, M20ExecutionSpec, M20FixedAdapter, M20Harness, M20Manifest, M20PairingMetadata,
    M20Proposal, M20ProposalKind, M20ProviderAttemptError, M20ResourceCeiling, M20Namespace)
from src.evaluation.m20_real_case_source import M20RealEnvironment, M20RealEvaluator, real_cases
from src.evaluation.m20_real_execution_configuration import M20_REAL_PROVIDER_CONFIGURATION, M20_REAL_RESOURCE_CEILING

M20_DEEPSEEK_REQUEST_CONTRACT = "m20_deepseek_public_proposal_v1"
M20_DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
Transport = Callable[[Mapping[str, Any], int], Mapping[str, Any]]


def _public_request(case: Any, state: Mapping[str, Any]) -> dict[str, Any]:
    """The only wire payload: public task, legal actions, and current public state."""
    public = {"case_id": case.case_id, "task": case.task_text, "actions": sorted(case.actions), "state": dict(state)}
    instruction = ("Return exactly one JSON object with either {\"kind\":\"act\",\"action_id\":<legal action>} "
                   "or {\"kind\":\"answer\",\"payload\":<answer>}. Use only listed actions. "
                   "No explanation. Public input: " + json.dumps(public, sort_keys=True, separators=(",", ":")))
    return {"model": M20_REAL_PROVIDER_CONFIGURATION.model, "messages": [{"role": "system", "content":
            "M20 public proposal contract " + M20_DEEPSEEK_REQUEST_CONTRACT}, {"role": "user", "content": instruction}],
            "temperature": 0, "top_p": 1.0, "max_tokens": 512, "response_format": {"type": "json_object"},
            "stream": False, "thinking": {"type": "disabled"}}


def _parse(raw: Mapping[str, Any], case: Any) -> M20Proposal:
    try:
        if set(raw) - {"model", "choices", "usage"} or raw["model"] != M20_REAL_PROVIDER_CONFIGURATION.model:
            raise ValueError("unexpected provider envelope")
        content = raw["choices"][0]["message"]["content"]
        value = json.loads(content)
        if not isinstance(value, dict) or set(value) not in ({"kind", "action_id"}, {"kind", "payload"}):
            raise ValueError("unexpected proposal shape")
        if value["kind"] == "act" and isinstance(value["action_id"], str) and value["action_id"] in case.actions:
            return M20Proposal(M20ProposalKind.ACT, value["action_id"])
        if value["kind"] == "answer" and "payload" in value:
            return M20Proposal(M20ProposalKind.ANSWER, payload=value["payload"])
        raise ValueError("illegal proposal")
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise M20ProviderAttemptError("malformed_or_illegal_m20_proposal", False) from error


class M20DeepSeekProposalAdapter:
    """A provider boundary that cannot receive evaluator/private case objects."""
    retry_ceiling = 2

    def __init__(self, transport: Transport) -> None:
        if not callable(transport) or M20_REAL_PROVIDER_CONFIGURATION.identity_hash != "522fcf28714e168ce9854069468c51d3d3cb565404d7bdad3317e4fcc8f199ad":
            raise ValueError("frozen DeepSeek configuration mismatch")
        self._transport = transport
        self.requests: list[dict[str, Any]] = []

    def propose(self, public_case: Any, public_state: Mapping[str, Any]) -> M20Proposal:
        request = _public_request(public_case, public_state)
        self.requests.append(request)
        try:
            raw = self._transport(request, M20_REAL_PROVIDER_CONFIGURATION.timeout_seconds)
        except M20ProviderAttemptError:
            raise
        except (TimeoutError, OSError) as error:
            raise M20ProviderAttemptError("transport_failure", True) from error
        return _parse(raw, public_case)


def live_deepseek_transport(body: Mapping[str, Any], timeout_seconds: int) -> Mapping[str, Any]:
    """Explicit future-use transport; it is inert unless a caller invokes it after authorization."""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not isinstance(key, str) or not key.strip():
        raise M20ProviderAttemptError("missing_deepseek_api_key", False)
    request = Request(M20_DEEPSEEK_ENDPOINT, data=json.dumps(dict(body), separators=(",", ":")).encode("utf-8"),
                      headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise M20ProviderAttemptError("http_" + str(error.code), error.code in {429, 500, 502, 503, 504}) from error
    except (URLError, TimeoutError, OSError) as error:
        raise M20ProviderAttemptError("transport_failure", True) from error


@dataclass(frozen=True)
class M20CalibrationWorkItem:
    pair_id: str
    adaptive: M20ExecutionSpec
    fixed: M20ExecutionSpec


class M20DeepSeekCalibrationRunner:
    """Manifest-bound runner. A caller supplies a transport; this module never calls a provider itself."""
    def __init__(self, manifest: Mapping[str, Any] | None = None) -> None:
        self.frozen = dict(build_deepseek_manifest() if manifest is None else manifest)
        validate_deepseek_manifest(self.frozen)
        if self.frozen["provider_hash"] != M20_REAL_PROVIDER_CONFIGURATION.identity_hash or self.frozen["resource_ceiling_identity"] != M20_REAL_RESOURCE_CEILING.identity:
            raise ValueError("frozen provider/ceiling binding mismatch")
        ceiling = M20ResourceCeiling(M20_REAL_RESOURCE_CEILING.identity, 8, 4, 4, 8)
        cases = real_cases()
        by_id = {case.public.case_id: case for case in cases}
        pairs = tuple(M20PairingMetadata(case.public.case_id, case.cluster_id, case.payload_digest,
                    case.environment_id, case.evaluator_id, ceiling.identity) for case in cases)
        self.manifest = M20Manifest("m20_suite_v1", "m20_environment_v1", "m20_evaluator_v1", cases,
                                    "m20_real_case_source_v1", pairs, ceiling,
                                    execution_manifest_digest=self.frozen["digest"])
        self.harness = M20Harness(self.manifest, M20ConditionRegistry(self.frozen["provider_hash"]), M20RealEnvironment(), M20RealEvaluator())
        self._by_id = by_id

    def work_items(self) -> tuple[M20CalibrationWorkItem, ...]:
        items: list[M20CalibrationWorkItem] = []
        for pair in self.frozen["pairs"]:
            case = self._by_id.get(pair["case_id"])
            if case is None or pair["payload_digest"] != case.payload_digest or pair["cluster_id"] != case.cluster_id:
                raise ValueError("manifest case identity mismatch")
            specs = []
            for name in pair["conditions"]:
                condition = M20Condition(name)
                if condition not in (M20Condition.MIND_ADAPTIVE, M20Condition.MIND_FIXED): raise ValueError("manifest condition mismatch")
                specs.append(M20ExecutionSpec("m20_suite_v1", case.public.case_id, pair["repetition"], condition,
                    M20Namespace.CALIBRATION, self.frozen["digest"], self.frozen["provider_hash"], case.cluster_id,
                    case.payload_digest, case.environment_id, case.evaluator_id, M20_REAL_RESOURCE_CEILING.identity,
                    frozen_pair_id=pair["pair_id"]))
            adaptive = next(spec for spec in specs if spec.condition is M20Condition.MIND_ADAPTIVE)
            fixed = next(spec for spec in specs if spec.condition is M20Condition.MIND_FIXED)
            self.harness.admit_pair(adaptive, fixed)
            items.append(M20CalibrationWorkItem(pair["pair_id"], adaptive, fixed))
        if len(items) != 60 or len({item.pair_id for item in items}) != 60: raise ValueError("manifest pair enumeration mismatch")
        return tuple(items)

    def dry_run(self) -> dict[str, int]:
        items = self.work_items()
        return {"pairs": len(items), "executions": len(items) * 2, "duplicates": 0, "missing": 0}

    def run_work_item(self, item: M20CalibrationWorkItem, transport: Transport, store: M20EvidenceStore) -> tuple[Any, Any]:
        """Future authorized callers may invoke this with the same bridge for both conditions."""
        provider = M20DeepSeekProposalAdapter(transport)
        adaptive = self.harness.run(item.adaptive, M20AdaptiveAdapter(provider), store)
        fixed = self.harness.run(item.fixed, M20FixedAdapter(provider), store)
        return adaptive, fixed
