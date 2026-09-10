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
        schema=load_schema("m16_mind_interpretation_v1.json")
        request=json.dumps({"public_task":_public_task_view(task),"capability_vocabulary":list(self._vocabulary),"response_schema":schema},sort_keys=True,separators=(",",":"),ensure_ascii=False)
        result=self._transport.generate(f"{read_prompt('m16_mind_interpretation_v1.txt')}\n{request}")
        if self._sink: self._sink(result.observation)
        if isinstance(result,DeepSeekTransportSuccess):
            if _matches_schema(result.payload,schema): return ProviderResponse(result.payload)
            return ProviderFailure(ProviderFailureCategory.INVALID_OUTPUT_FORMAT,{"reason":"schema_nonconforming_response"})
        return ProviderFailure(ProviderFailureCategory.TIMEOUT if result.category is DeepSeekTransportFailureCategory.TIMEOUT else ProviderFailureCategory.MALFORMED_RESPONSE if result.category is DeepSeekTransportFailureCategory.MALFORMED_RESPONSE else ProviderFailureCategory.UNAVAILABLE,{"reason":result.reason})

def _matches_schema(value:object,schema:object)->bool:
    """Validate only the existing canonical JSON-schema subset at this boundary."""
    if not isinstance(schema,dict): return False
    if "enum" in schema and value not in schema["enum"]: return False
    kind=schema.get("type")
    if kind=="string": return isinstance(value,str)
    if kind=="array": return isinstance(value,list) and all(_matches_schema(item,schema.get("items",{})) for item in value)
    if kind!="object" or not isinstance(value,dict): return False
    properties=schema.get("properties",{})
    if not isinstance(properties,dict): return False
    required=schema.get("required",())
    if not isinstance(required,(list,tuple)) or any(key not in value for key in required): return False
    if schema.get("additionalProperties") is False and set(value)-set(properties): return False
    return all(key not in properties or _matches_schema(item,properties[key]) for key,item in value.items())
