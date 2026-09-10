"""DeepSeek-backed M13 interpretation provider; it has no execution authority."""
from __future__ import annotations
import json
from typing import Callable, Iterable
from src.core.task import Task
from src.evaluation.deepseek_transport import DeepSeekRestTransport,DeepSeekTransportSuccess,DeepSeekTransportFailure,DeepSeekTransportFailureCategory
from src.evaluation.m16_gemini_assets import MIND_PROMPT_ID,load_schema,read_prompt
from src.evaluation.provider_observation import ProviderCallObservation
from src.integration.gemini_m13_provider import _public_task_view
from src.integration.llm_provider import ProviderFailure,ProviderFailureCategory,ProviderResponse

class DeepSeekM13InterpretationProvider:
    prompt_id=MIND_PROMPT_ID
    def __init__(self,transport:DeepSeekRestTransport,capability_vocabulary:Iterable[str]=( "calculator",),observation_sink:Callable[[ProviderCallObservation],None]|None=None)->None:
        if not isinstance(transport,DeepSeekRestTransport): raise TypeError("transport must be DeepSeekRestTransport")
        vocabulary=tuple(capability_vocabulary)
        if not vocabulary or any(not isinstance(x,str) or not x.strip() for x in vocabulary) or len(set(vocabulary))!=len(vocabulary): raise ValueError("invalid capability_vocabulary")
        self._transport,self._vocabulary,self._sink=transport,vocabulary,observation_sink
    def interpret(self,task:Task)->ProviderResponse|ProviderFailure:
        if not isinstance(task,Task): raise TypeError("task must be Task")
        request=json.dumps({"public_task":_public_task_view(task),"capability_vocabulary":list(self._vocabulary)},sort_keys=True,separators=(",",":"),ensure_ascii=False)
        result=self._transport.generate(f"{read_prompt('m16_mind_interpretation_v1.txt')}\n{request}")
        if self._sink: self._sink(result.observation)
        if isinstance(result,DeepSeekTransportSuccess): return ProviderResponse(result.payload)
        return ProviderFailure(ProviderFailureCategory.TIMEOUT if result.category is DeepSeekTransportFailureCategory.TIMEOUT else ProviderFailureCategory.MALFORMED_RESPONSE if result.category is DeepSeekTransportFailureCategory.MALFORMED_RESPONSE else ProviderFailureCategory.UNAVAILABLE,{"reason":result.reason})
