"""Narrow DeepSeek Chat Completions transport for the isolated M16 experiment."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json, os, time
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.evaluation.provider_observation import ProviderCallObservation

DEEPSEEK_REQUEST_MODEL = "deepseek-v4-flash"
DEEPSEEK_RETURNED_MODEL = "deepseek-flash"
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"

class DeepSeekTransportFailureCategory(str, Enum):
    CONFIGURATION="configuration"; UNAVAILABLE="unavailable"; TIMEOUT="timeout"; MALFORMED_RESPONSE="malformed_response"

@dataclass(frozen=True)
class DeepSeekGenerationConfig:
    request_model_id: str = DEEPSEEK_REQUEST_MODEL
    expected_returned_model: str = DEEPSEEK_RETURNED_MODEL
    temperature: int = 0
    top_p: int = 1
    candidate_count: int = 1
    max_output_tokens: int = 512
    max_attempts: int = 3
    timeout_seconds: int = 30
    thinking_type: str = "disabled"
    response_format_type: str = "json_object"
    def __post_init__(self) -> None:
        if (self.request_model_id,self.expected_returned_model)!=(DEEPSEEK_REQUEST_MODEL,DEEPSEEK_RETURNED_MODEL): raise ValueError("DeepSeek model identity is frozen")
        if (self.temperature,self.top_p,self.candidate_count,self.max_output_tokens)!=(0,1,1,512): raise ValueError("DeepSeek sampling/output configuration is frozen")
        if self.max_attempts!=3 or self.timeout_seconds<=0 or self.thinking_type!="disabled" or self.response_format_type!="json_object": raise ValueError("DeepSeek provider configuration is frozen")

@dataclass(frozen=True)
class DeepSeekTransportSuccess:
    payload: dict[str, Any]; observation: ProviderCallObservation
@dataclass(frozen=True)
class DeepSeekTransportFailure:
    category: DeepSeekTransportFailureCategory; observation: ProviderCallObservation; reason: str
DeepSeekTransportResult = DeepSeekTransportSuccess | DeepSeekTransportFailure
HttpPost = Callable[[str, Mapping[str,str], bytes, int], dict[str,Any]]

def _post_json(url: str, headers: Mapping[str,str], body: bytes, timeout: int) -> dict[str,Any]:
    with urlopen(Request(url,data=body,headers=dict(headers),method="POST"),timeout=timeout) as response: # nosec B310
        data=json.loads(response.read().decode("utf-8"))
    if not isinstance(data,dict): raise ValueError("DeepSeek response must be object")
    return data
def _count(value: Any) -> int|None: return value if isinstance(value,int) and not isinstance(value,bool) and value>=0 else None

class DeepSeekRestTransport:
    def __init__(self, configuration: DeepSeekGenerationConfig=DeepSeekGenerationConfig(), *, http_post: HttpPost=_post_json, environment: Mapping[str,str]|None=None, sleeper: Callable[[float],None]=time.sleep, clock_ns: Callable[[],int]=time.monotonic_ns) -> None:
        if not isinstance(configuration,DeepSeekGenerationConfig): raise TypeError("configuration must be DeepSeekGenerationConfig")
        self._configuration,self._http_post,self._environment,self._sleeper,self._clock_ns=configuration,http_post,os.environ if environment is None else environment,sleeper,clock_ns
    @property
    def configuration(self) -> DeepSeekGenerationConfig: return self._configuration
    def generate(self,instruction: str) -> DeepSeekTransportResult:
        if not isinstance(instruction,str) or not instruction.strip(): raise ValueError("instruction must be non-empty str")
        key=self._environment.get("DEEPSEEK_API_KEY")
        if not isinstance(key,str) or not key: return DeepSeekTransportFailure(DeepSeekTransportFailureCategory.CONFIGURATION,ProviderCallObservation(0,0,0),"missing_deepseek_api_key")
        body={"model":self._configuration.request_model_id,"messages":[{"role":"user","content":instruction}],"temperature":self._configuration.temperature,"top_p":self._configuration.top_p,"n":self._configuration.candidate_count,"max_tokens":self._configuration.max_output_tokens,"thinking":{"type":self._configuration.thinking_type},"response_format":{"type":self._configuration.response_format_type}}
        encoded=json.dumps(body,sort_keys=True,separators=(",",":")).encode(); started=self._clock_ns()
        for attempt in range(1,self._configuration.max_attempts+1):
            try: return self._decode(self._http_post(DEEPSEEK_ENDPOINT,{"Content-Type":"application/json","Authorization":"Bearer "+key},encoded,self._configuration.timeout_seconds),attempt,started)
            except HTTPError as error: status=error.code
            except TimeoutError: return self._failure(DeepSeekTransportFailureCategory.TIMEOUT,attempt,started,"timeout")
            except (URLError,OSError,ValueError,json.JSONDecodeError): status=None
            if status not in {None,429,500,502,503,504}: return self._failure(DeepSeekTransportFailureCategory.UNAVAILABLE,attempt,started,"http_error")
            if attempt<self._configuration.max_attempts: self._sleeper(float(2**(attempt-1)))
        return self._failure(DeepSeekTransportFailureCategory.UNAVAILABLE,self._configuration.max_attempts,started,"retry_exhausted")
    def _decode(self,response: dict[str,Any],attempts:int,started:int) -> DeepSeekTransportResult:
        obs=self._observation(response,attempts,started,1,1); returned=response.get("model")
        if returned!=self._configuration.expected_returned_model: raise RuntimeError("unreviewed DeepSeek returned-model observation")
        try:
            content=response["choices"][0]["message"]["content"]
            if not isinstance(content,str) or not content.strip(): raise ValueError("empty_content")
            payload=json.loads(content)
            if not isinstance(payload,dict): raise ValueError("json_not_object")
        except (KeyError,IndexError,TypeError,ValueError,json.JSONDecodeError): return DeepSeekTransportFailure(DeepSeekTransportFailureCategory.MALFORMED_RESPONSE,obs,"invalid_structured_response")
        return DeepSeekTransportSuccess(payload,obs)
    def _failure(self,category:DeepSeekTransportFailureCategory,attempts:int,started:int,reason:str)->DeepSeekTransportFailure: return DeepSeekTransportFailure(category,self._observation({},attempts,started,0,0),reason)
    def _observation(self,response:Mapping[str,Any],attempts:int,started:int,successes:int,calls:int)->ProviderCallObservation:
        usage=response.get("usage") if isinstance(response.get("usage"),Mapping) else {}; details=usage.get("completion_tokens_details") if isinstance(usage.get("completion_tokens_details"),Mapping) else {}
        return ProviderCallObservation(attempts,successes,calls,prompt_tokens=_count(usage.get("prompt_tokens")),output_tokens=_count(usage.get("completion_tokens")),total_tokens=_count(usage.get("total_tokens")),thinking_tokens=_count(details.get("reasoning_tokens")),cached_tokens=_count(usage.get("prompt_cache_hit_tokens")),latency_ms=max(0,(self._clock_ns()-started)//1_000_000),model_version=response.get("model") if isinstance(response.get("model"),str) else None,provider_request_id=response.get("id") if isinstance(response.get("id"),str) else None)
