"""Deterministic M18 task-generation and evaluator foundations; no formal suite."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json, random
from typing import Any

CASE_SCHEMA_VERSION="m18_case_schema_v1"; GENERATION_PROTOCOL_VERSION="m18_generation_v1"; ENVIRONMENT_VERSION="m18_environment_v1"; EVALUATOR_VERSION="m18_evaluator_v1"
class M18Cohort(str,Enum): A="multi_step"; B="distractor_selection"; C="recovery_correction"
class M18Difficulty(str,Enum): EASY="easy"; MEDIUM="medium"; HARD="hard"
class M18Namespace(str,Enum): PILOT="pilot"; FORMAL="formal"
class M18FailureSubtype(str,Enum): RECOVERABLE="recoverable_failure"; INVALID="invalid_action"
class M18EnvironmentCategory(str,Enum): SUCCESS="success"; RECOVERABLE_FAILURE="recoverable_failure"; INVALID_ACTION="invalid_action"; UNRECOVERABLE_FAILURE="unrecoverable_failure"
class M18EvaluationCategory(str,Enum): SUCCESS="success"; WRONG_ANSWER="wrong_answer"; BUDGET_EXHAUSTED="budget_exhausted"; INVALID_ACTION_EXHAUSTED="invalid_action_exhausted"; UNRECOVERABLE_ENVIRONMENT_FAILURE="unrecoverable_environment_failure"; AGENT_INTERNAL_FAILURE="agent_internal_failure"; PROVIDER_FAILURE="provider_failure"; INFRASTRUCTURE_INVALID="infrastructure_invalid"
def canonical_json(v:Any)->str:return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
def canonical_hash(v:Any)->str:return sha256(canonical_json(v).encode()).hexdigest()
def _public(v:Any)->Any:
 if v is None or isinstance(v,(str,int,bool)):return v
 if isinstance(v,float):return v
 if isinstance(v,dict):return {k:_public(x) for k,x in v.items() if k not in {"difficulty","target_answer","target_state","correct_tool","correct_action","evaluator_rule","failure_schedule","generation_seed","cohort","private"}}
 if isinstance(v,(list,tuple)):return [_public(x) for x in v]
 raise TypeError("JSON-compatible values required")
@dataclass(frozen=True)
class M18PublicCase:
 case_id:str; task_text:str; tools:tuple[dict[str,Any],...]; environment_config:dict[str,Any]
 def to_dict(self):return {"case_id":self.case_id,"task_text":self.task_text,"tools":[_public(x) for x in self.tools],"environment_config":_public(self.environment_config)}
@dataclass(frozen=True)
class M18EvaluatorFixture:
 target_answer:Any; target_state:dict[str,Any]; evaluator_rule:str; failure_schedule:dict[str,Any]
 def __post_init__(self):
  if not isinstance(self.target_state,dict) or not isinstance(self.failure_schedule,dict):raise TypeError("private fixture mappings required")
  if self.evaluator_rule!="exact_answer_or_target_state_v1":raise ValueError("unknown evaluator rule")
@dataclass(frozen=True)
class M18Case:
 case_id:str; namespace:M18Namespace; cohort:M18Cohort; difficulty:M18Difficulty; public:M18PublicCase; evaluator:M18EvaluatorFixture; generation_seed:int; generation_protocol_version:str=GENERATION_PROTOCOL_VERSION; environment_version:str=ENVIRONMENT_VERSION; evaluator_version:str=EVALUATOR_VERSION
 def __post_init__(self):
  if not self.case_id.startswith(self.namespace.value+"."):raise ValueError("case id must use namespace prefix")
  if self.public.case_id!=self.case_id:raise ValueError("public case id mismatch")
  if not isinstance(self.generation_seed,int):raise TypeError("generation_seed must be int")
 def to_dict(self):return {"case_id":self.case_id,"namespace":self.namespace.value,"cohort":self.cohort.value,"difficulty":self.difficulty.value,"public":self.public.to_dict(),"evaluator":{"target_answer":self.evaluator.target_answer,"target_state":self.evaluator.target_state,"evaluator_rule":self.evaluator.evaluator_rule,"failure_schedule":self.evaluator.failure_schedule},"generation_seed":self.generation_seed,"case_schema_version":CASE_SCHEMA_VERSION,"generation_protocol_version":self.generation_protocol_version,"environment_version":self.environment_version,"evaluator_version":self.evaluator_version}
 def public_view(self):return self.public
@dataclass(frozen=True)
class M18EnvironmentOutcome:
 category:M18EnvironmentCategory; payload:dict[str,Any]
 def to_dict(self):return {"category":self.category.value,"payload":_public(self.payload)}
@dataclass(frozen=True)
class M18EvaluationResult:
 category:M18EvaluationCategory; success:bool
 def to_dict(self):return {"category":self.category.value,"success":self.success}
@dataclass(frozen=True)
class M18SuiteDesign:
 cases_per_cell:int
 def __post_init__(self):
  if self.cases_per_cell not in {10,18}:raise ValueError("supported designs are 90 and 162 cases")
 @property
 def case_count(self):return 3*3*self.cases_per_cell

def _tools(seed:int,count:int,correct_position:int)->tuple[dict[str,Any],...]:
 tools=[]
 for i in range(count):
  tool_id=f"tool_{seed%97:02d}_{i:02d}"
  tools.append({"tool_id":tool_id,"display_name":f"Operation {chr(65+i)}","description":"Apply a public numeric transformation.","parameter_schema":{"type":"object","properties":{"value":{"type":"integer"}},"required":["value"]}})
 tools[correct_position]={**tools[correct_position],"description":"Apply the requested public transformation to the supplied value."}
 return tuple(tools)

def generate_m18_case(cohort:M18Cohort,difficulty:M18Difficulty,generation_seed:int,namespace:M18Namespace,index:int=0,failure_subtype:M18FailureSubtype|None=None)->M18Case:
 if not isinstance(generation_seed,int):raise TypeError("generation_seed must be int")
 rng=random.Random(f"m18:{generation_seed}:{cohort.value}:{difficulty.value}:{namespace.value}:{index}")
 depth={M18Difficulty.EASY:1,M18Difficulty.MEDIUM:2,M18Difficulty.HARD:3}[difficulty]
 count={M18Difficulty.EASY:2,M18Difficulty.MEDIUM:3,M18Difficulty.HARD:4}[difficulty]
 pos=(generation_seed+index)%count; base=rng.randrange(1000,9000); target=base*(depth+1)
 case_id=f"{namespace.value}.{cohort.value}.{difficulty.value}.{generation_seed}.{index}"
 tools=_tools(generation_seed,count,pos)
 env={"environment_version":ENVIRONMENT_VERSION,"transition_depth":depth,"public_tool_count":count}
 schedule={}
 if cohort is M18Cohort.A:
  text=f"Use the available operations sequentially. Later operation arguments must use the prior public result; complete depth {depth}."
  env["requires_observation_dependency"]=True
 elif cohort is M18Cohort.B:
  text="Select the operation whose public description satisfies the requested transformation, then return its public result."
  env["requires_observation_dependency"]=False
 else:
  subtype=failure_subtype or (M18FailureSubtype.RECOVERABLE if (generation_seed+index)%2==0 else M18FailureSubtype.INVALID)
  text="Complete the public operation after handling any legitimate environment feedback."
  schedule={"subtype":subtype.value,"trigger":"first_eligible_action"}
  env["requires_observation_dependency"]=difficulty is M18Difficulty.HARD
 fixture=M18EvaluatorFixture(target,{"target":target},"exact_answer_or_target_state_v1",schedule)
 return M18Case(case_id,namespace,cohort,difficulty,M18PublicCase(case_id,text,tools,env),fixture,generation_seed)

class M18DeterministicEnvironment:
 def apply(self,case:M18Case,action:dict[str,Any],system_identity:str|None=None)->M18EnvironmentOutcome:
  if not isinstance(case,M18Case) or not isinstance(action,dict):raise TypeError("case and action required")
  # system_identity is deliberately ignored; outcome derives only from case/action.
  schedule=case.evaluator.failure_schedule
  if schedule and action.get("action")=="tool_call":
   subtype=schedule.get("subtype")
   if subtype==M18FailureSubtype.RECOVERABLE.value:return M18EnvironmentOutcome(M18EnvironmentCategory.RECOVERABLE_FAILURE,{"reason":"tool_transient_failure"})
   if subtype==M18FailureSubtype.INVALID.value:return M18EnvironmentOutcome(M18EnvironmentCategory.INVALID_ACTION,{"reason":"invalid_arguments"})
  if action.get("action") not in {"answer","tool_call"}:return M18EnvironmentOutcome(M18EnvironmentCategory.INVALID_ACTION,{"reason":"unsupported_action"})
  return M18EnvironmentOutcome(M18EnvironmentCategory.SUCCESS,{"public_value":case.generation_seed%100+1})

class M18Evaluator:
 def evaluate(self,case:M18Case,final_answer:Any=None,terminal_reason:str|None=None)->M18EvaluationResult:
  try:
   if not isinstance(case,M18Case):raise TypeError
   if terminal_reason=="budget_exhausted":return M18EvaluationResult(M18EvaluationCategory.BUDGET_EXHAUSTED,False)
   if terminal_reason=="unrecoverable_environment_failure":return M18EvaluationResult(M18EvaluationCategory.UNRECOVERABLE_ENVIRONMENT_FAILURE,False)
   if final_answer==case.evaluator.target_answer or final_answer==case.evaluator.target_state:return M18EvaluationResult(M18EvaluationCategory.SUCCESS,True)
   return M18EvaluationResult(M18EvaluationCategory.WRONG_ANSWER,False)
  except Exception:return M18EvaluationResult(M18EvaluationCategory.INFRASTRUCTURE_INVALID,False)

def case_hash(case:M18Case)->str:return canonical_hash(case.to_dict())
def public_case_hash(case:M18Case)->str:return canonical_hash(case.public_view().to_dict())
def collection_hash(cases:tuple[M18Case,...],public:bool=False)->str:return canonical_hash([c.public_view().to_dict() if public else c.to_dict() for c in cases])
