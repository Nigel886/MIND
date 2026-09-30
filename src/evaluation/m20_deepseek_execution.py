"""M20-native DeepSeek bridge and v2-manifest calibration planning; no implicit network execution."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
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
M20_PROVIDER_VISIBLE_STATE_FIELDS = ("progress", "observed", "recovered", "resource_note")
Transport = Callable[[Mapping[str, Any], int], Mapping[str, Any]]

class M20ResponseRejection(str, Enum):
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    NON_JSON_RESPONSE = "NON_JSON_RESPONSE"
    JSON_TOP_LEVEL_TYPE_INVALID = "JSON_TOP_LEVEL_TYPE_INVALID"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    UNKNOWN_RESPONSE_KIND = "UNKNOWN_RESPONSE_KIND"
    UNKNOWN_ACTION_ID = "UNKNOWN_ACTION_ID"
    ACTION_PAYLOAD_INVALID = "ACTION_PAYLOAD_INVALID"
    ACTION_NOT_LEGAL_IN_PUBLIC_STATE = "ACTION_NOT_LEGAL_IN_PUBLIC_STATE"
    ANSWER_PAYLOAD_INVALID = "ANSWER_PAYLOAD_INVALID"
    PROVIDER_TRANSPORT_FAILURE = "PROVIDER_TRANSPORT_FAILURE"
    OTHER_CONTRACT_REJECTION = "OTHER_CONTRACT_REJECTION"


def _public_request(case: Any, state: Mapping[str, Any]) -> dict[str, Any]:
    """The only wire payload: public task, legal actions, and current public state."""
    if not isinstance(state, Mapping):
        raise M20ProviderAttemptError("invalid_public_state", False)
    # This explicit projection is deliberately not a copy of initial/current state:
    # evaluator success predicates can exist in the case model but have no wire path.
    projected_state = {key: state[key] for key in M20_PROVIDER_VISIBLE_STATE_FIELDS if key in state}
    public = {"task": case.task_text, "actions": sorted(case.actions), "state": projected_state}
    instruction = ("Return exactly one JSON object with either {\"kind\":\"act\",\"action_id\":<legal action>} "
                   "or {\"kind\":\"answer\",\"payload\":<answer>}. Use only listed actions. "
                   "No explanation. Public input: " + json.dumps(public, sort_keys=True, separators=(",", ":")))
    return {"model": M20_REAL_PROVIDER_CONFIGURATION.model, "messages": [{"role": "system", "content":
            "M20 public proposal contract " + M20_DEEPSEEK_REQUEST_CONTRACT}, {"role": "user", "content": instruction}],
            "temperature": 0, "top_p": 1.0, "max_tokens": 512, "response_format": {"type": "json_object"},
            "stream": False, "thinking": {"type": "disabled"}}


def _parse(raw: Mapping[str, Any], case: Any) -> tuple[M20Proposal, dict[str, Any]]:
    """Parse only the frozen public contract and retain no raw response content."""
    diagnostic = {
        "response_present": bool(raw), "response_mode": "json_object",
        "json_parse_success": False, "top_level_type": None, "field_names": [],
        "kind": None, "required_field_mask": [], "payload_top_level_type": None,
        "parser_stage": "envelope", "rejection_category": None,
        "legality_result": None, "admitted_proposal": False,
    }
    try:
        if set(raw) - {"model", "choices", "usage"} or raw["model"] != M20_REAL_PROVIDER_CONFIGURATION.model:
            raise ValueError("unexpected provider envelope")
        content = raw["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError(M20ResponseRejection.EMPTY_RESPONSE.value)
        diagnostic["parser_stage"] = "json_decode"
        value = json.loads(content)
        diagnostic["json_parse_success"] = True
        diagnostic["top_level_type"] = type(value).__name__
        if not isinstance(value, dict):
            raise ValueError(M20ResponseRejection.JSON_TOP_LEVEL_TYPE_INVALID.value)
        diagnostic["field_names"] = sorted(value)
        diagnostic["kind"] = value.get("kind")
        diagnostic["parser_stage"] = "schema"
        if "kind" not in value:
            raise ValueError(M20ResponseRejection.MISSING_REQUIRED_FIELD.value)
        if value["kind"] == "act":
            diagnostic["required_field_mask"] = ["kind", "action_id"]
            if "action_id" not in value:
                raise ValueError(M20ResponseRejection.MISSING_REQUIRED_FIELD.value)
            if set(value) != {"kind", "action_id"} or not isinstance(value["action_id"], str):
                raise ValueError(M20ResponseRejection.ACTION_PAYLOAD_INVALID.value)
            diagnostic["parser_stage"] = "legality"
            diagnostic["legality_result"] = value["action_id"] in case.actions
            if not diagnostic["legality_result"]:
                raise ValueError(M20ResponseRejection.ACTION_NOT_LEGAL_IN_PUBLIC_STATE.value)
            diagnostic["admitted_proposal"] = True
            return M20Proposal(M20ProposalKind.ACT, value["action_id"]), diagnostic
        if value["kind"] == "answer":
            diagnostic["required_field_mask"] = ["kind", "payload"]
            if "payload" not in value:
                raise ValueError(M20ResponseRejection.MISSING_REQUIRED_FIELD.value)
            if set(value) != {"kind", "payload"}:
                raise ValueError(M20ResponseRejection.ANSWER_PAYLOAD_INVALID.value)
            diagnostic["payload_top_level_type"] = type(value["payload"]).__name__
            diagnostic["admitted_proposal"] = True
            return M20Proposal(M20ProposalKind.ANSWER, payload=value["payload"]), diagnostic
        raise ValueError(M20ResponseRejection.UNKNOWN_RESPONSE_KIND.value)
    except json.JSONDecodeError as error:
        diagnostic["rejection_category"] = M20ResponseRejection.NON_JSON_RESPONSE.value
        raise M20ProviderAttemptError(diagnostic["rejection_category"], False, diagnostic) from error
    except (KeyError, IndexError, TypeError, ValueError) as error:
        category = str(error)
        diagnostic["rejection_category"] = (
            category if category in M20ResponseRejection._value2member_map_
            else M20ResponseRejection.OTHER_CONTRACT_REJECTION.value
        )
        raise M20ProviderAttemptError(diagnostic["rejection_category"], False, diagnostic) from error


class M20DeepSeekProposalAdapter:
    """A provider boundary that cannot receive evaluator/private case objects."""
    retry_ceiling = 2

    def __init__(self, transport: Transport) -> None:
        if not callable(transport) or M20_REAL_PROVIDER_CONFIGURATION.identity_hash != "522fcf28714e168ce9854069468c51d3d3cb565404d7bdad3317e4fcc8f199ad":
            raise ValueError("frozen DeepSeek configuration mismatch")
        self._transport = transport
        self.requests: list[dict[str, Any]] = []
        self.last_diagnostic: dict[str, Any] | None = None

    def propose(self, public_case: Any, public_state: Mapping[str, Any]) -> M20Proposal:
        request = _public_request(public_case, public_state)
        self.requests.append(request)
        try:
            raw = self._transport(request, M20_REAL_PROVIDER_CONFIGURATION.timeout_seconds)
        except M20ProviderAttemptError as error:
            self.last_diagnostic = dict(error.diagnostic)
            raise
        except (TimeoutError, OSError) as error:
            self.last_diagnostic = {
                "response_present": False, "response_mode": "json_object",
                "json_parse_success": False, "top_level_type": None, "field_names": [],
                "kind": None, "required_field_mask": [], "payload_top_level_type": None,
                "parser_stage": "transport", "rejection_category": M20ResponseRejection.PROVIDER_TRANSPORT_FAILURE.value,
                "legality_result": None, "admitted_proposal": False,
            }
            raise M20ProviderAttemptError(M20ResponseRejection.PROVIDER_TRANSPORT_FAILURE.value, True,
                                          self.last_diagnostic) from error
        try:
            proposal, self.last_diagnostic = _parse(raw, public_case)
            return proposal
        except M20ProviderAttemptError as error:
            self.last_diagnostic = dict(error.diagnostic)
            raise


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
