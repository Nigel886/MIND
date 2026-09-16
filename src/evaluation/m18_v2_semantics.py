"""Provider-free, reachable semantics for the un-frozen M18 benchmark v2."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from src.evaluation.m18_task_generation import M18Cohort, M18Difficulty, M18FailureSubtype, M18Namespace, canonical_hash, generate_m18_case

M18_V2_SUITE_VERSION = "m18_suite_v2"
M18_V2_ENVIRONMENT_ID = "m18_environment_v2"
M18_V2_EVALUATOR_ID = "m18_evaluator_v2"
M18_V2_BUDGET_ID = "m18_budget_v2"

class M18V2OutcomeCategory(str, Enum):
    SUCCESS="success"; RECOVERABLE_FAILURE="recoverable_failure"; INVALID_ACTION="invalid_action"; BUDGET_EXHAUSTED="budget_exhausted"; TIMEOUT="timeout"
class M18V2EvaluationCategory(str, Enum):
    SUCCESS="success"; WRONG_ANSWER="wrong_answer"; MALFORMED_ANSWER="malformed_answer"; INTERACTION_INCOMPLETE="interaction_incomplete"; BUDGET_EXHAUSTED="budget_exhausted"; TIMEOUT="timeout"
class M18V2BudgetError(RuntimeError): pass

def _freeze(value: Any) -> Any:
    if value is None or isinstance(value,(bool,int,float,str)): return value
    if isinstance(value,Mapping): return tuple(sorted((str(k),_freeze(v)) for k,v in value.items()))
    if isinstance(value,(tuple,list)): return tuple(_freeze(v) for v in value)
    raise TypeError("JSON-compatible value required")
def _thaw(value: Any) -> Any:
    if isinstance(value,tuple):
        if all(isinstance(v,tuple) and len(v)==2 and isinstance(v[0],str) for v in value): return {k:_thaw(v) for k,v in value}
        return [_thaw(v) for v in value]
    return value

@dataclass(frozen=True)
class M18V2Budget:
    identity:str=M18_V2_BUDGET_ID; max_action_cycles:int=6; max_tool_attempts:int=4
    invalid_action_threshold:int=2; recoverable_failure_threshold:int=2
    max_logical_provider_calls:int=8; episode_timeout_seconds:int=180
    answer_consumes_action_cycle:bool=True; failed_and_invalid_attempts_consume_tool_attempt:bool=True
    plan_replans_consume_public_action_cycle:bool=False
    def __post_init__(self):
        if self.identity!=M18_V2_BUDGET_ID or (self.max_action_cycles,self.max_tool_attempts,self.invalid_action_threshold,self.recoverable_failure_threshold,self.max_logical_provider_calls,self.episode_timeout_seconds)!=(6,4,2,2,8,180): raise ValueError("m18_budget_v2 is immutable")
        if not self.answer_consumes_action_cycle or not self.failed_and_invalid_attempts_consume_tool_attempt or self.plan_replans_consume_public_action_cycle: raise ValueError("invalid m18_budget_v2 accounting")
    def to_dict(self): return self.__dict__.copy()
    @property
    def budget_hash(self): return canonical_hash(self.to_dict())

@dataclass(frozen=True)
class M18V2BudgetState:
    action_cycles:int=0; tool_attempts:int=0; invalid_actions:int=0; recoverable_failures:int=0; logical_provider_calls:int=0
    def consume_action(self,tool_attempt:bool=False):
        b=M18V2Budget()
        if self.action_cycles>=b.max_action_cycles: raise M18V2BudgetError("action_cycle_limit")
        if tool_attempt and self.tool_attempts>=b.max_tool_attempts: raise M18V2BudgetError("tool_attempt_limit")
        return M18V2BudgetState(self.action_cycles+1,self.tool_attempts+int(tool_attempt),self.invalid_actions,self.recoverable_failures,self.logical_provider_calls)
    def record_outcome(self,category:M18V2OutcomeCategory):
        invalid=self.invalid_actions+int(category is M18V2OutcomeCategory.INVALID_ACTION); recovery=self.recoverable_failures+int(category is M18V2OutcomeCategory.RECOVERABLE_FAILURE)
        state=M18V2BudgetState(self.action_cycles,self.tool_attempts,invalid,recovery,self.logical_provider_calls); b=M18V2Budget()
        return state, "invalid_action_threshold_reached" if invalid>=b.invalid_action_threshold else ("recoverable_failure_threshold_reached" if recovery>=b.recoverable_failure_threshold else None)
    def record_logical_provider_call(self):
        if self.logical_provider_calls>=M18V2Budget().max_logical_provider_calls: raise M18V2BudgetError("logical_provider_call_limit")
        return M18V2BudgetState(self.action_cycles,self.tool_attempts,self.invalid_actions,self.recoverable_failures,self.logical_provider_calls+1)
    def to_dict(self): return self.__dict__.copy()

@dataclass(frozen=True)
class M18V2PublicCase:
    case_id:str; task_text:str; capabilities:tuple[Any,...]; task_config:Any
    def to_dict(self): return {"case_id":self.case_id,"task_text":self.task_text,"capabilities":[_thaw(v) for v in self.capabilities],"task_config":_thaw(self.task_config)}
@dataclass(frozen=True)
class M18V2EvaluatorFixture:
    expected_final_result:int; evaluator_id:str=M18_V2_EVALUATOR_ID
@dataclass(frozen=True)
class M18V2Case:
    case_id:str; namespace:M18Namespace; cohort:M18Cohort; difficulty:M18Difficulty; generation_seed:int; public:M18V2PublicCase; evaluator:M18V2EvaluatorFixture; failure_subtype:M18FailureSubtype|None=None; suite_version:str=M18_V2_SUITE_VERSION; environment_id:str=M18_V2_ENVIRONMENT_ID; evaluator_id:str=M18_V2_EVALUATOR_ID
    def __post_init__(self):
        if (self.suite_version,self.environment_id,self.evaluator_id)!=(M18_V2_SUITE_VERSION,M18_V2_ENVIRONMENT_ID,M18_V2_EVALUATOR_ID): raise ValueError("M18 v2 identity mismatch")
        if self.case_id!=self.public.case_id: raise ValueError("public case identity mismatch")
        if (self.cohort is M18Cohort.C)!=(self.failure_subtype is not None): raise ValueError("Cohort C subtype mismatch")
    def public_view(self): return self.public
    def to_dict(self): return {"case_id":self.case_id,"namespace":self.namespace.value,"cohort":self.cohort.value,"difficulty":self.difficulty.value,"generation_seed":self.generation_seed,"failure_subtype":self.failure_subtype.value if self.failure_subtype else None,"suite_version":self.suite_version,"environment_id":self.environment_id,"evaluator_id":self.evaluator_id,"public":self.public.to_dict(),"evaluator":{"expected_final_result":self.evaluator.expected_final_result,"evaluator_id":self.evaluator.evaluator_id}}

@dataclass(frozen=True)
class M18V2EnvironmentOutcome:
    category:M18V2OutcomeCategory; payload:Any; state:Any
    def to_dict(self): return {"category":self.category.value,"payload":_thaw(self.payload),"state":_thaw(self.state)}
def _config(case): return _thaw(case.public.task_config)
def initial_public_state(case): return {"current_value":_config(case)["initial_value"],"completed_steps":0,"failure_consumed":False}
def _transform(value,transformation): return {"increment":value+3,"double":value*2,"decrement":value-1}[transformation]

def m18_v2_public_transition(case:M18V2Case, public_state:Mapping[str,Any], action:Mapping[str,Any])->M18V2EnvironmentOutcome:
    """The single pure public formula used by the v2 environment and target replay."""
    c=_config(case); state=dict(public_state); completed,current,consumed=int(state["completed_steps"]),int(state["current_value"]),bool(state["failure_consumed"])
    if action.get("action")!="tool_call": return M18V2EnvironmentOutcome(M18V2OutcomeCategory.INVALID_ACTION,_freeze({"reason":"unsupported_public_action"}),_freeze(state))
    if completed>=c["required_successful_steps"]: return M18V2EnvironmentOutcome(M18V2OutcomeCategory.INVALID_ACTION,_freeze({"reason":"interaction_already_complete"}),_freeze(state))
    schedule=c["failure_schedule"]
    if schedule is not None and not consumed and completed==schedule["after_successful_steps"]:
        state["failure_consumed"]=True; category=M18V2OutcomeCategory.RECOVERABLE_FAILURE if schedule["subtype"]==M18FailureSubtype.RECOVERABLE.value else M18V2OutcomeCategory.INVALID_ACTION
        return M18V2EnvironmentOutcome(category,_freeze({"reason":schedule["subtype"],"retry_permitted":True}),_freeze(state))
    step=c["steps"][completed]; p=action.get("parameters")
    if action.get("tool_name")!=step["tool_id"] or not isinstance(p,Mapping) or p.get("value")!=current: return M18V2EnvironmentOutcome(M18V2OutcomeCategory.INVALID_ACTION,_freeze({"reason":"public_action_does_not_match_state"}),_freeze(state))
    result=_transform(current,step["transformation_id"]); state={"current_value":result,"completed_steps":completed+1,"failure_consumed":consumed}
    return M18V2EnvironmentOutcome(M18V2OutcomeCategory.SUCCESS,_freeze({"public_value":result,"completed_steps":completed+1}),_freeze(state))

class M18DeterministicEnvironmentV2:
    identity=M18_V2_ENVIRONMENT_ID
    def apply(self,case,public_state,action):
        if not isinstance(case,M18V2Case): raise TypeError("M18 v2 case required")
        return m18_v2_public_transition(case,public_state,action)
class M18EvaluatorV2:
    identity=M18_V2_EVALUATOR_ID
    def evaluate(self,case,candidate,public_state,terminal_reason=None):
        if terminal_reason=="timeout": return M18V2EvaluationCategory.TIMEOUT
        if terminal_reason is not None: return M18V2EvaluationCategory.BUDGET_EXHAUSTED
        if not isinstance(candidate,int) or isinstance(candidate,bool): return M18V2EvaluationCategory.MALFORMED_ANSWER
        if int(public_state.get("completed_steps",-1))!=_config(case)["required_successful_steps"]: return M18V2EvaluationCategory.INTERACTION_INCOMPLETE
        return M18V2EvaluationCategory.SUCCESS if candidate==case.evaluator.expected_final_result else M18V2EvaluationCategory.WRONG_ANSWER

@dataclass
class M18V2Episode:
    case:M18V2Case; budget_state:M18V2BudgetState=field(default_factory=M18V2BudgetState); public_state:dict[str,Any]=field(init=False); terminal_reason:str|None=None
    def __post_init__(self): self.public_state=initial_public_state(self.case); self._environment=M18DeterministicEnvironmentV2()
    def submit_tool(self,action):
        if self.terminal_reason: raise M18V2BudgetError("episode_terminated")
        try: self.budget_state=self.budget_state.consume_action(True)
        except M18V2BudgetError as e: self.terminal_reason=str(e); return M18V2EnvironmentOutcome(M18V2OutcomeCategory.BUDGET_EXHAUSTED,_freeze({"reason":str(e)}),_freeze(self.public_state))
        result=self._environment.apply(self.case,self.public_state,action); self.public_state=_thaw(result.state); self.budget_state,stop=self.budget_state.record_outcome(result.category); self.terminal_reason=stop or self.terminal_reason; return result
    def submit_answer(self,candidate):
        if not self.terminal_reason:
            try: self.budget_state=self.budget_state.consume_action()
            except M18V2BudgetError as e: self.terminal_reason=str(e)
        return M18EvaluatorV2().evaluate(self.case,candidate,self.public_state,self.terminal_reason)
    def submit_invalid_action(self):
        """Account for a submitted non-tool public action without a tool slot."""
        if self.terminal_reason: raise M18V2BudgetError("episode_terminated")
        try: self.budget_state=self.budget_state.consume_action()
        except M18V2BudgetError as e: self.terminal_reason=str(e); return M18V2EnvironmentOutcome(M18V2OutcomeCategory.BUDGET_EXHAUSTED,_freeze({"reason":str(e)}),_freeze(self.public_state))
        outcome=M18V2EnvironmentOutcome(M18V2OutcomeCategory.INVALID_ACTION,_freeze({"reason":"invalid_public_action"}),_freeze(self.public_state))
        self.budget_state,stop=self.budget_state.record_outcome(outcome.category); self.terminal_reason=stop or self.terminal_reason
        return outcome
    def record_logical_provider_call(self): self.budget_state=self.budget_state.record_logical_provider_call()
    def enforce_elapsed_seconds(self,elapsed):
        if elapsed>=M18V2Budget().episode_timeout_seconds:self.terminal_reason="timeout"

@dataclass(frozen=True)
class M18V2ReferenceTrajectory:
    actions:tuple[dict[str,Any],...]; observations:tuple[dict[str,Any],...]; final_public_result:int; action_cycles:int; tool_attempts:int; evaluation:M18V2EvaluationCategory
def reference_public_trajectory(case):
    """Reference action choice reads public configuration/state, never the target."""
    episode=M18V2Episode(case); actions=[]; observations=[]
    while episode.public_state["completed_steps"]<_config(case)["required_successful_steps"]:
        step=_config(case)["steps"][episode.public_state["completed_steps"]]; action={"action":"tool_call","tool_name":step["tool_id"],"parameters":{"value":episode.public_state["current_value"]}}
        result=episode.submit_tool(action); actions.append(action); observations.append(result.to_dict())
        if episode.terminal_reason: raise AssertionError("reference trajectory threshold failure")
    final=int(episode.public_state["current_value"]); evaluation=episode.submit_answer(final)
    return M18V2ReferenceTrajectory(tuple(actions),tuple(observations),final,episode.budget_state.action_cycles,episode.budget_state.tool_attempts,evaluation)
def _required(cohort,difficulty):
    if cohort is M18Cohort.A:return {M18Difficulty.EASY:2,M18Difficulty.MEDIUM:3,M18Difficulty.HARD:4}[difficulty]
    return 1 if cohort is M18Cohort.B or difficulty is M18Difficulty.EASY else 2
def generate_m18_v2_case(cohort,difficulty,generation_seed,namespace,index=0,failure_subtype=None):
    """New semantics retain historical membership identity, not v1 behavior."""
    v1=generate_m18_case(cohort,difficulty,generation_seed,namespace,index,failure_subtype); subtype=(failure_subtype or (M18FailureSubtype.RECOVERABLE if (generation_seed+index)%2==0 else M18FailureSubtype.INVALID)) if cohort is M18Cohort.C else None
    transforms=("increment","double","decrement","increment"); tools=[]
    for pos,tool in enumerate(v1.public.tools): tools.append({"tool_id":tool["tool_id"],"display_name":tool["display_name"],"description":"Apply the named public transformation to the current public value.","parameter_schema":tool["parameter_schema"],"transformation_id":transforms[pos%4]})
    required=_required(cohort,difficulty); steps=tuple({"tool_id":tools[pos]["tool_id"],"transformation_id":tools[pos]["transformation_id"]} for pos in range(required))
    if cohort is M18Cohort.B:
        relevant=(generation_seed+index)%len(tools); steps=({"tool_id":tools[relevant]["tool_id"],"transformation_id":tools[relevant]["transformation_id"]},)
    schedule=None if subtype is None else {"subtype":subtype.value,"after_successful_steps":0 if difficulty is M18Difficulty.EASY else 1}
    config={"environment_id":M18_V2_ENVIRONMENT_ID,"initial_value":generation_seed%89+11,"required_successful_steps":required,"steps":steps,"failure_schedule":schedule,"requires_observation_dependency":cohort is M18Cohort.A or (cohort is M18Cohort.C and difficulty is M18Difficulty.HARD),"task_transformation_id":steps[-1]["transformation_id"]}
    public=M18V2PublicCase(v1.case_id,"Use public observations to submit each required operation, then submit the final public result.",tuple(_freeze(tool) for tool in tools),_freeze(config)); provisional=M18V2Case(v1.case_id,namespace,cohort,difficulty,generation_seed,public,M18V2EvaluatorFixture(0),subtype)
    target=reference_public_trajectory(provisional).final_public_result
    return M18V2Case(v1.case_id,namespace,cohort,difficulty,generation_seed,public,M18V2EvaluatorFixture(target),subtype)
def v2_case_hash(case): return canonical_hash(case.to_dict())
