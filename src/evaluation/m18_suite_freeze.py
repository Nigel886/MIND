"""Deterministic M18 pilot/formal suite construction and freeze audits."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from src.evaluation.m18_task_generation import *

M18_SUITE_VERSION="m18_suite_v1"; PILOT_SEED_NAMESPACE="m18_pilot_seed_v1"; FORMAL_SEED_NAMESPACE="m18_formal_seed_v1"
def _ordered(cases):
 return tuple(sorted(cases,key=lambda c:(c.cohort.value,c.difficulty.value,c.evaluator.failure_schedule.get("subtype",""),c.case_id)))
def _make(namespace:M18Namespace,per_cell:int,base:int):
 cases=[]; n=0
 for cohort in M18Cohort:
  for difficulty in M18Difficulty:
   for i in range(per_cell):
    subtype=None
    if cohort is M18Cohort.C: subtype=M18FailureSubtype.RECOVERABLE if i%2==0 else M18FailureSubtype.INVALID
    cases.append(generate_m18_case(cohort,difficulty,base+n,namespace,i,subtype));n+=1
 return _ordered(cases)
def pilot_suite():return _make(M18Namespace.PILOT,2,21000)
def formal_suite():return _make(M18Namespace.FORMAL,18,51000)
def public_records(cases):return [c.public_view().to_dict() for c in cases]
def private_records(cases):return [c.to_dict() for c in cases]
def _hash(v):return canonical_hash(v)
def _counts(cases,key):
 out={}
 for c in cases:
  value=key(c);out[value]=out.get(value,0)+1
 return dict(sorted(out.items()))
def audit_suite(cases):
 if len({c.case_id for c in cases})!=len(cases):raise ValueError("duplicate case id")
 private=private_records(cases);public=public_records(cases)
 if len({canonical_json(x) for x in private})!=len(cases) or len({canonical_json(x) for x in public})!=len(cases):raise ValueError("duplicate canonical case")
 forbidden={"difficulty","target_answer","expected_answer","ground_truth","hidden_target","correct_tool","correct_action","required_action_sequence","evaluator_rule","failure_schedule","generation_seed","cohort"}
 def keys(v):
  if isinstance(v,dict):return set(v)|set().union(*(keys(x) for x in v.values()))
  if isinstance(v,list):return set().union(*(keys(x) for x in v)) if v else set()
  return set()
 if forbidden & keys(public):raise ValueError("public leakage")
 for c in cases:
  if c.cohort is M18Cohort.A and not c.public.environment_config.get("requires_observation_dependency"):raise ValueError("degenerate cohort A")
  if c.cohort is M18Cohort.C and c.evaluator.failure_schedule.get("subtype") not in {x.value for x in M18FailureSubtype}:raise ValueError("invalid cohort C schedule")
  if M18Evaluator().evaluate(c,c.evaluator.target_answer).success is not True or M18Evaluator().evaluate(c,"__wrong__").success:raise ValueError("evaluator validation failed")
  action={"action":"tool_call","tool_name":c.public.tools[0]["tool_id"],"parameters":{}}
  if M18DeterministicEnvironment().apply(c,action,"MIND").to_dict()!=M18DeterministicEnvironment().apply(c,action,"ReAct").to_dict():raise ValueError("system-dependent environment")
 return {"case_count":len(cases),"cohort_counts":_counts(cases,lambda c:c.cohort.value),"difficulty_counts":_counts(cases,lambda c:c.difficulty.value),"subtype_counts":_counts([c for c in cases if c.cohort is M18Cohort.C],lambda c:c.evaluator.failure_schedule["subtype"]),"private_hash":_hash(private),"public_hash":_hash(public)}
def manifest(pilot,formal,generation_commit):
 pa,fa=audit_suite(pilot),audit_suite(formal)
 split={"pilot_ids":[c.case_id for c in pilot],"formal_ids":[c.case_id for c in formal]}
 if set(split["pilot_ids"])&set(split["formal_ids"]):raise ValueError("pilot/formal overlap")
 core={"suite_name":"m18_advanced_agent_benchmark","suite_version":M18_SUITE_VERSION,"generation_protocol_version":GENERATION_PROTOCOL_VERSION,"case_schema_version":CASE_SCHEMA_VERSION,"environment_version":ENVIRONMENT_VERSION,"evaluator_version":EVALUATOR_VERSION,"generation_commit":generation_commit,"pilot_seed_namespace":PILOT_SEED_NAMESPACE,"formal_seed_namespace":FORMAL_SEED_NAMESPACE,"pilot_case_count":len(pilot),"formal_case_count":len(formal),"pilot":pa,"formal":fa,"split_hash":_hash(split),"environment_evaluator_hash":_hash({"environment":ENVIRONMENT_VERSION,"evaluator":EVALUATOR_VERSION}),"freeze_status":"FROZEN"}
 return {**core,"manifest_hash":_hash(core)},split
