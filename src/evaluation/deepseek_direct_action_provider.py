"""DeepSeek structured Direct action provider without tool execution authority."""
from __future__ import annotations
import json
from typing import Callable
from src.evaluation.deepseek_transport import DeepSeekRestTransport,DeepSeekTransportSuccess,DeepSeekTransportFailureCategory
from src.evaluation.direct_tool_calling import DirectActionProviderFailure,DirectActionProviderFailureCategory,DirectActionProviderResponse,DirectActionRequest,DirectActionResourceMetadata
from src.evaluation.m16_gemini_assets import DIRECT_PROMPT_ID,read_prompt
from src.evaluation.provider_observation import ProviderCallObservation
from src.evaluation.contracts import EvaluationActionType
from src.evaluation.gemini_direct_action_provider import _reject_private_keys

DIRECT_JSON_WRAPPER="Return valid JSON only. The top-level key must be action_type, never type."
class DeepSeekDirectActionProvider:
    prompt_id=DIRECT_PROMPT_ID
    def __init__(self,transport:DeepSeekRestTransport,observation_sink:Callable[[ProviderCallObservation],None]|None=None)->None:
        if not isinstance(transport,DeepSeekRestTransport): raise TypeError("transport must be DeepSeekRestTransport")
        self._transport,self._sink=transport,observation_sink
    def decide(self,request:DirectActionRequest)->DirectActionProviderResponse|DirectActionProviderFailure:
        if not isinstance(request,DirectActionRequest): raise TypeError("request must be DirectActionRequest")
        public=request.to_dict(); public["task"].pop("id",None); _reject_private_keys(public)
        result=self._transport.generate(f"{read_prompt('m16_direct_action_v1.txt')}\n{DIRECT_JSON_WRAPPER}\n{json.dumps(public,sort_keys=True,separators=(',',':'),ensure_ascii=False)}")
        if self._sink: self._sink(result.observation)
        if not isinstance(result,DeepSeekTransportSuccess):
            category=DirectActionProviderFailureCategory.PROVIDER_TIMEOUT if result.category is DeepSeekTransportFailureCategory.TIMEOUT else DirectActionProviderFailureCategory.MALFORMED_RESPONSE if result.category is DeepSeekTransportFailureCategory.MALFORMED_RESPONSE else DirectActionProviderFailureCategory.PROVIDER_UNAVAILABLE
            return DirectActionProviderFailure(category,{"reason":result.reason})
        try: return DirectActionProviderResponse(EvaluationActionType(result.payload["action_type"]),result.payload["payload"],DirectActionResourceMetadata(model_calls=result.observation.model_calls,input_tokens=result.observation.prompt_tokens,output_tokens=result.observation.output_tokens,latency_ms=result.observation.latency_ms))
        except (KeyError,TypeError,ValueError): return DirectActionProviderFailure(DirectActionProviderFailureCategory.MALFORMED_RESPONSE,{"reason":"invalid_direct_action"})
