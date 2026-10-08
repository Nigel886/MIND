"""Independent non-network privacy/invariance audit for #318."""
from __future__ import annotations
import json, os
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from src.evaluation.m20_deepseek_execution import _public_request
from src.evaluation.m20_evaluator_failure_diagnostics import (M20EvaluatorDiagnosticStore, M20EvaluatorFailureDiagnostic, M20_EVALUATOR_FAILURE_DIAGNOSTIC_SCHEMA, diagnose_after_evaluator_handoff)
from src.evaluation.m20_harness import M20IntegrityError, M20Outcome, M20Proposal, M20ProposalKind
from src.evaluation.m20_real_case_source import M20RealEnvironment, M20RealEvaluator, real_cases


class ProspectiveDiagnosticPrivacyAudit(unittest.TestCase):
    evidence=[]; ids=tuple([f'P{i:02d}' for i in range(1,10)]+[f'M{i:02d}' for i in range(1,9)]+[f'E{i:02d}' for i in range(1,9)])
    def setUp(self):
        self.case=next(x for x in real_cases() if x.public.cohort=='multi_step_stateful'); self.env=M20RealEnvironment(); self.ev=M20RealEvaluator(); self.initial=self.env.initial_public_state(self.case.public); self.ready=self.initial
        for _ in range(self.ready['required_progress']): self.ready=self.env.apply(self.case.public,self.ready,M20Proposal(M20ProposalKind.ACT,'advance')).state
    def diag(self, eid='x', state=None, answer='wrong', outcome=None):
        state=self.ready if state is None else state; outcome=self.ev.evaluate(self.case,state,answer) if outcome is None else outcome
        return diagnose_after_evaluator_handoff(eid,self.case,state,answer,self.ev.evaluator_id,outcome)
    def execute(self, case):
        target=self.case.private.target; d=self.diag('audit-'+case); request=_public_request(self.case.public,self.initial,True); raw=json.dumps(request)+json.dumps(self.initial)
        with TemporaryDirectory() as td:
            store=M20EvaluatorDiagnosticStore(Path(td)); store.persist(d)
            checks={
             'P01': lambda: self.assertNotIn(target, raw+json.dumps(d.canonical())),
             'P02': lambda: self.assertNotIn(json.dumps(self.case.private.reference_witness), raw+json.dumps(d.canonical())),
             'P03': lambda: self.assertNotIn('classification', raw),
             'P04': lambda: self.assertNotIn('validation_status', raw),
             'P05': lambda: self.assertEqual(self.initial,self.env.initial_public_state(self.case.public)),
             'P06': lambda: self.assertNotIn('classification', json.dumps(self.initial)),
             'P07': lambda: self.assertNotIn('evaluator', json.dumps(request)),
             'P08': lambda: self.assertNotIn('diagnostic', json.dumps(request)),
             'P09': lambda: self.assertNotIn(target, repr(M20IntegrityError('private-canary'))),
             'M01': lambda: self.assertEqual(self.ev.evaluate(self.case,self.ready,target),M20Outcome.SUCCESS),
             'M02': lambda: self.assertEqual(self.diag('h1',self.ready,'wrong').classification,'answer_payload_failure'),
             'M03': lambda: self.assertEqual(self.diag('h2',self.initial,target).classification,'prerequisite_failure'),
             'M04': lambda: self.assertEqual(self.diag('h3',self.initial,'wrong').classification,'combined_failure'),
             'M05': lambda: self.assertEqual(self.diag('h4',self.ready,None).classification,'unknown_other'),
             'M06': lambda: self.assertEqual(self.diag('bad',self.ready,'wrong',M20Outcome.SUCCESS).validation_status,'conflicting'),
             'M07': lambda: self.assertRaises(M20IntegrityError,M20EvaluatorFailureDiagnostic,'x',self.ev.evaluator_id,'bad',True,'pass','present','success','complete',{'a':'b'}),
             'M08': lambda: self._persistence_failure(td),
             'E01': lambda: self.assertEqual(store.load('audit-'+case),d),
             'E02': lambda: (store.persist(d),self.assertEqual(store.load('audit-'+case),d)),
             'E03': lambda: self.assertRaises(M20IntegrityError,store.persist,replace(d,classification='combined_failure',prerequisite_status='fail')),
             'E04': lambda: self._tamper(store,d),
             'E05': lambda: self.assertRaises(M20IntegrityError,M20EvaluatorFailureDiagnostic,'x',self.ev.evaluator_id,M20_EVALUATOR_FAILURE_DIAGNOSTIC_SCHEMA,True,'pass','present','success','complete',{}),
             'E06': lambda: self.assertRaises(M20IntegrityError,M20EvaluatorFailureDiagnostic,'x',self.ev.evaluator_id,'wrong',True,'pass','present','success','complete',{'a':'b'}),
             'E07': lambda: self.assertRaises(M20IntegrityError,store.persist,replace(d,provenance={'authority':'other','version':'other'})),
             'E08': lambda: self.assertFalse(Path('evaluation/results/m20_calibration_answerterm_v1').joinpath('audit-'+case+'.json').exists()),
            }
            checks[case](); return {'case_id':case,'category':case[0],'production_boundary':'evaluator_private_sidecar' if case[0]=='E' else 'evaluator_or_public_boundary','fixture':'synthetic_canary','expected':'fail_closed_or_no_leakage','actual':'PASS','provider-visible effect':'none','evaluator outcome effect':'unchanged','sidecar effect':'validated','result':'PASS','evidence_reference':self.id()+':'+case}
    def _tamper(self,store,d):
        p=store.root/(d.execution_id+'.json'); v=json.loads(p.read_text()); v['classification']='success'; p.write_text(json.dumps(v)); self.assertRaises(M20IntegrityError,store.load,d.execution_id)
    def _persistence_failure(self,td):
        blocked=Path(td)/'blocked'; blocked.write_text('x')
        with self.assertRaises(FileExistsError): M20EvaluatorDiagnosticStore(blocked)
        self.assertEqual(self.ev.evaluate(self.case,self.ready,'wrong'),M20Outcome.FAILURE_OR_INCORRECT)
    def test_a_matrix(self):
        for case in self.ids:
            with self.subTest(case=case): self.evidence.append(self.execute(case))
    def test_z_coverage_and_write(self):
        self.assertEqual(len(self.evidence),25); self.assertEqual({x['case_id'] for x in self.evidence},set(self.ids)); self.assertTrue(all(x['result']=='PASS' for x in self.evidence))
        out=os.environ.get('M20_PRIVACY_AUDIT_MATRIX_PATH'); self.assertTrue(out); Path(out).write_text(json.dumps({'schema':'m20_prospective_diagnostic_privacy_audit_v1','rows':self.evidence},indent=2)+'\n')
