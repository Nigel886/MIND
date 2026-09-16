"""Evaluation-side M18 Plan-and-Execute condition with one bounded replan."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

from src.core.policy_context import PolicyTaskContext
from src.core.tool import CapabilityDescriptor
from src.evaluation.contracts import EvaluationAction, EvaluationActionType, EvaluationFeedback, EvaluationFeedbackType
from src.evaluation.execution import AgentStepInput, AgentStepResult
from src.evaluation.m18_direct_tool_calling import M18_DIRECT_RESPONSE_SCHEMA, decode_m18_direct_response

_PRIVATE = frozenset({"expected_answer","ground_truth","correct_tool","correct_action","difficulty","cohort","cohort_label","cohort_routing_label","evaluator_success","judge_metadata","private_judge_metadata","completion_status","completion_label","benchmark_completion_state","chain_of_thought","hidden_reasoning","thought","rationale","plan","confidence","credentials","api_key"})

def _freeze(v: Any) -> Any:
    if v is None or isinstance(v,(bool,str,int)): return v
    if isinstance(v,float):
        if not isfinite(v): raise ValueError("public float must be finite")
        return v
    if isinstance(v,Mapping):
        out={}
        for k,x in v.items():
            if not isinstance(k,str): raise TypeError("mapping keys must be strings")
            if k not in _PRIVATE: out[k]=_freeze(x)
        return MappingProxyType(out)
    if isinstance(v,(list,tuple)): return tuple(_freeze(x) for x in v)
    raise TypeError("value must be JSON-compatible")
def _thaw(v: Any) -> Any:
    if isinstance(v,Mapping): return {k:_thaw(x) for k,x in v.items()}
    if isinstance(v,tuple): return [_thaw(x) for x in v]
    return deepcopy(v)
def _hash(v: Any) -> str: return sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

M18_PLAN_EXECUTE_ID="m18_plan_provider_contract_repair_v1"
M18_PLANNER_PROMPT="Create only a strict public ordered execution plan from the supplied public task, tools, and budget. Return only a JSON object matching the required planner schema. Do not include reasoning, rationale, evaluator information, or extra fields."
M18_EXECUTOR_PROMPT="Select exactly one next action using the supplied public task, explicit plan, cursor, current public feedback, tools, and budget. Return only strict action JSON; no reasoning, rationale, plan, confidence, or extra fields."
M18_PLAN_SCHEMA={"type":"object","additionalProperties":False,"required":["steps"],"properties":{"steps":{"type":"array","minItems":1,"items":{"type":"object","additionalProperties":False,"required":["step_id","subgoal","capability_id"],"properties":{"step_id":{"type":"string","minLength":1},"subgoal":{"type":"string","minLength":1},"capability_id":{"type":["string","null"]}}}}}}

class M18PlanConditionError(ValueError):
    """Strict planner-output rejection with a safe diagnostic category."""
    category="planner_decoder_rejection"

class M18PlanProviderError(RuntimeError):
    """Planner provider failure retaining only its bounded public category."""
    def __init__(self,message:str,category:str="provider_wrapper_exception"):
        super().__init__(message); self.category=category
class M18PlanTerminationReason(str,Enum):
    ANSWER_SUBMITTED="answer_submitted"; BUDGET_EXHAUSTED="budget_exhausted"; UNRECOVERABLE_ENVIRONMENT_FAILURE="unrecoverable_environment_failure"; REPLAN_LIMIT_REACHED="replan_limit_reached"

@dataclass(frozen=True)
class PlanStep:
    step_id:str; subgoal:str; capability_id:str|None
    def __post_init__(self):
        for name in ("step_id","subgoal"):
            value=getattr(self,name)
            if not isinstance(value,str) or not value.strip() or value!=value.strip(): raise ValueError(f"{name} must be trimmed non-empty")
        if self.capability_id is not None and (not isinstance(self.capability_id,str) or not self.capability_id.strip() or self.capability_id!=self.capability_id.strip()): raise ValueError("capability_id must be a trimmed string or None")
    def to_dict(self): return {"step_id":self.step_id,"subgoal":self.subgoal,"capability_id":self.capability_id}

@dataclass(frozen=True)
class PublicExecutionPlan:
    steps:tuple[PlanStep,...]
    def __post_init__(self):
        if not isinstance(self.steps,tuple) or not self.steps or any(not isinstance(x,PlanStep) for x in self.steps): raise TypeError("steps must be a non-empty PlanStep tuple")
        if len({x.step_id for x in self.steps})!=len(self.steps): raise ValueError("plan step ids must be unique")
    def to_dict(self): return {"steps":[x.to_dict() for x in self.steps]}
    @classmethod
    def from_dict(cls,data):
        if not isinstance(data,dict) or set(data)!={"steps"} or not isinstance(data["steps"],list): raise M18PlanConditionError("plan must contain only ordered steps")
        steps=[]
        for item in data["steps"]:
            if not isinstance(item,dict) or set(item)!={"step_id","subgoal","capability_id"}: raise M18PlanConditionError("plan step has invalid fields")
            try: steps.append(PlanStep(item["step_id"],item["subgoal"],item["capability_id"]))
            except (TypeError,ValueError) as error: raise M18PlanConditionError("invalid public plan step") from error
        return cls(tuple(steps))

@dataclass(frozen=True)
class M18PlannerRequest:
    prompt:str; public_task:dict[str,Any]; capabilities:tuple[dict[str,Any],...]; budget:dict[str,Any]; response_schema:dict[str,Any]; current_plan:dict[str,Any]|None=None; cursor:int|None=None; current_feedback:dict[str,Any]|None=None
    def __post_init__(self):
        if not isinstance(self.prompt,str) or not self.prompt.strip(): raise ValueError("prompt must be non-empty")
        for n in ("public_task","budget","response_schema"):
            if not isinstance(getattr(self,n),dict): raise TypeError(f"{n} must be dict")
        if not isinstance(self.capabilities,tuple) or any(not isinstance(x,dict) for x in self.capabilities): raise TypeError("capabilities must be ordered dicts")
        if self.current_plan is not None and not isinstance(self.current_plan,dict): raise TypeError("current_plan must be dict or None")
        if self.cursor is not None and (isinstance(self.cursor,bool) or not isinstance(self.cursor,int) or self.cursor<0): raise ValueError("cursor must be nonnegative int or None")
        if self.current_feedback is not None and not isinstance(self.current_feedback,dict): raise TypeError("current_feedback must be dict or None")
        for n in ("public_task","budget","response_schema","current_plan","current_feedback"): object.__setattr__(self,n,_freeze(getattr(self,n)) if getattr(self,n) is not None else None)
        object.__setattr__(self,"capabilities",tuple(_freeze(x) for x in self.capabilities))
    def to_dict(self): return {"prompt":self.prompt,"public_task":_thaw(self.public_task),"capabilities":_thaw(self.capabilities),"budget":_thaw(self.budget),"response_schema":_thaw(self.response_schema),"current_plan":_thaw(self.current_plan) if self.current_plan else None,"cursor":self.cursor,"current_feedback":_thaw(self.current_feedback) if self.current_feedback else None}

@dataclass(frozen=True)
class M18ExecutorRequest:
    prompt:str; public_task:dict[str,Any]; plan:PublicExecutionPlan; cursor:int; current_feedback:dict[str,Any]; capabilities:tuple[dict[str,Any],...]; budget:dict[str,Any]; response_schema:dict[str,Any]
    def __post_init__(self):
        if not isinstance(self.plan,PublicExecutionPlan) or isinstance(self.cursor,bool) or not isinstance(self.cursor,int) or self.cursor<0 or self.cursor>=len(self.plan.steps): raise ValueError("invalid explicit plan or cursor")
        for n in ("public_task","current_feedback","budget","response_schema"):
            if not isinstance(getattr(self,n),dict): raise TypeError(f"{n} must be dict")
            object.__setattr__(self,n,_freeze(getattr(self,n)))
        if not isinstance(self.capabilities,tuple) or any(not isinstance(x,dict) for x in self.capabilities): raise TypeError("capabilities must be ordered dicts")
        object.__setattr__(self,"capabilities",tuple(_freeze(x) for x in self.capabilities))
    def to_dict(self): return {"prompt":self.prompt,"public_task":_thaw(self.public_task),"plan":self.plan.to_dict(),"cursor":self.cursor,"current_feedback":_thaw(self.current_feedback),"capabilities":_thaw(self.capabilities),"budget":_thaw(self.budget),"response_schema":_thaw(self.response_schema)}

@runtime_checkable
class M18PlanProvider(Protocol):
    def plan(self,request:M18PlannerRequest)->str: ...
    def execute(self,request:M18ExecutorRequest)->str: ...

@dataclass(frozen=True)
class M18PlanArtifacts:
    implementation_hash:str; planner_prompt_hash:str; planner_schema_hash:str; planner_decoder_hash:str; executor_prompt_hash:str; action_schema_hash:str; executor_decoder_hash:str; plan_serializer_hash:str; replanning_policy_hash:str; provider_call_policy_hash:str
    def to_dict(self): return self.__dict__.copy()
def m18_plan_artifacts()->M18PlanArtifacts:
    values=[_hash({"planner_prompt":M18_PLANNER_PROMPT}),_hash(M18_PLAN_SCHEMA),_hash({"planner_decoder":"strict_public_plan_v1"}),_hash({"executor_prompt":M18_EXECUTOR_PROMPT}),_hash(M18_DIRECT_RESPONSE_SCHEMA),_hash({"executor_decoder":"shared_strict_action_v1"}),_hash({"plan_serializer":"typed_plan_to_dict_v1"}),_hash({"replanning":"one_replan_after_recoverable_or_invalid_v1"}),_hash({"calls":"initial_planner_executor_replan_separate_v1"})]
    return M18PlanArtifacts(_hash({"id":M18_PLAN_EXECUTE_ID,"artifacts":values}),*values)

class M18PlanAndExecuteBaseline:
    max_replans=1
    def __init__(self,provider:M18PlanProvider,capabilities:tuple[CapabilityDescriptor,...]):
        if not isinstance(provider,M18PlanProvider): raise TypeError("provider must implement planner and executor")
        if not isinstance(capabilities,tuple) or any(not isinstance(x,CapabilityDescriptor) for x in capabilities): raise TypeError("capabilities must be ordered descriptor tuple")
        self._provider=provider; self._capabilities=capabilities; self._plan:PublicExecutionPlan|None=None; self._cursor=0; self._pending_tool=False
        self._planner_calls=0; self._executor_calls=0; self._replan_calls=0; self._tool_calls=0; self._invalid_actions=0; self._recoverable_failures=0; self._action_cycles=0
    @property
    def plan(self): return self._plan
    @property
    def cursor(self): return self._cursor
    @property
    def planner_calls(self): return self._planner_calls
    @property
    def executor_calls(self): return self._executor_calls
    @property
    def replan_calls(self): return self._replan_calls
    @property
    def tool_calls(self): return self._tool_calls
    @property
    def action_cycles(self): return self._action_cycles
    def _public(self,si): return PolicyTaskContext.from_task(si.case.task).to_dict(),tuple(x.to_dict() for x in self._capabilities),si.budget_state.to_dict()
    def _parse_plan(self,raw):
        if not isinstance(raw,str): raise M18PlanProviderError("plan provider result must be JSON string","provider_result_contract")
        try: data=json.loads(raw,parse_constant=lambda _: (_ for _ in ()).throw(M18PlanConditionError("nonfinite")))
        except (json.JSONDecodeError,M18PlanConditionError) as e: raise M18PlanConditionError("planner output is not strict JSON") from e
        return PublicExecutionPlan.from_dict(data)
    @staticmethod
    def _provider_error(message,error):
        category=getattr(error,"category",None)
        return M18PlanProviderError(message,category if isinstance(category,str) and category else "provider_wrapper_exception")
    def _initial_plan(self,si):
        task,caps,budget=self._public(si); request=M18PlannerRequest(M18_PLANNER_PROMPT,task,caps,budget,M18_PLAN_SCHEMA); self._planner_calls+=1
        try: self._plan=self._parse_plan(self._provider.plan(request))
        except M18PlanConditionError: raise
        except Exception as e: raise self._provider_error("initial planning failed",e) from e
    def _replan(self,si):
        task,caps,budget=self._public(si); request=M18PlannerRequest(M18_PLANNER_PROMPT,task,caps,budget,M18_PLAN_SCHEMA,self._plan.to_dict(),self._cursor,si.previous_feedback.to_dict()); self._replan_calls+=1
        try: self._plan=self._parse_plan(self._provider.plan(request)); self._cursor=0
        except M18PlanConditionError: raise
        except Exception as e: raise self._provider_error("replanning failed",e) from e
    def _termination(self,si):
        if si.budget_state.remaining_steps==0:return M18PlanTerminationReason.BUDGET_EXHAUSTED
        fb=si.previous_feedback
        if fb.feedback_type is EvaluationFeedbackType.TOOL_FAILURE and fb.to_dict()["payload"].get("category")=="unrecoverable_failure":return M18PlanTerminationReason.UNRECOVERABLE_ENVIRONMENT_FAILURE
        return None
    def step(self,si:AgentStepInput)->AgentStepResult:
        if not isinstance(si,AgentStepInput): raise TypeError("step_input must be AgentStepInput")
        termination=self._termination(si)
        if termination:return AgentStepResult(EvaluationAction(EvaluationActionType.FAIL,{"reason":termination.value}),True)
        fb=si.previous_feedback
        eligible=fb.feedback_type is EvaluationFeedbackType.INVALID_ACTION or (fb.feedback_type is EvaluationFeedbackType.TOOL_FAILURE and fb.to_dict()["payload"].get("category")=="recoverable_failure")
        if eligible and self._plan is not None:
            if fb.feedback_type is EvaluationFeedbackType.INVALID_ACTION:self._invalid_actions+=1
            else:self._recoverable_failures+=1
            if self._replan_calls>=self.max_replans:return AgentStepResult(EvaluationAction(EvaluationActionType.FAIL,{"reason":M18PlanTerminationReason.REPLAN_LIMIT_REACHED.value}),True)
            self._replan(si)
        elif self._pending_tool and fb.feedback_type is EvaluationFeedbackType.TOOL_RESPONSE:
            self._cursor+=1; self._pending_tool=False
        if self._plan is None:self._initial_plan(si)
        if self._cursor>=len(self._plan.steps): return AgentStepResult(EvaluationAction(EvaluationActionType.FAIL,{"reason":"plan_exhausted"}),True)
        task,caps,budget=self._public(si); req=M18ExecutorRequest(M18_EXECUTOR_PROMPT,task,self._plan,self._cursor,fb.to_dict(),caps,budget,M18_DIRECT_RESPONSE_SCHEMA); self._executor_calls+=1; self._action_cycles+=1
        try: action=decode_m18_direct_response(self._provider.execute(req))
        except Exception as e: raise M18PlanConditionError("executor output rejected") from e
        if action.action_type is EvaluationActionType.TOOL_CALL:self._tool_calls+=1;self._pending_tool=True
        return AgentStepResult(action,action.action_type is not EvaluationActionType.TOOL_CALL)
