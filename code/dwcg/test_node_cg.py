"""Node Phase I and restricted pricing against an independently built full LP."""
import copy
from dataclasses import asdict
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

from common import blocks,empty_pool,make_column,compact
from node_state import NodeRestrictions,NumericPolicy,NodePricingResult,PricingCertificate
from node_pricing import fixed_records
from node_pricing import price_node
from node_master import build_node_master,solve_node
import node_master as node_module
from node_state import NumericalUncertain
from solver_backend import BackendConfig,use_backend

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'docs/branch_and_price'))
from independent_bp_verify import oracle,full_node,node_pool


def small():
    def t(i):return {'id':i,'value':6,'weight':1,'modes':{'H':dict(time=2,cost=1,beta=.1),'R':dict(time=2,cost=1,beta=0)}}
    return {'human_limit':2,'robot_limit':2,'lines':[{'id':'L','cycle_time':4,'fatigue_limit':.5,
        'stations':[dict(fixed_cost=1,human_cost=1,robot_cost=1) for _ in range(2)],
        'tasks':[t('a'),t('b')],'required_tasks':[],'precedence':[],'min_recovery':0}]}


class NodeCGTests(unittest.TestCase):
    def compare(self,data,r=None,parent=None,solver='cbc'):
        r=r or NodeRestrictions()
        answer=solve_node(data,r,parent,solver=solver)
        with use_backend(BackendConfig(name=solver)):
            expected,model,pool=full_node(data,r.to_records())
        if expected['status']=='infeasible':
            self.assertIn(answer.status,('local_infeasible_proven','phase1_infeasible_proven'),asdict(answer.certificate))
        else:
            self.assertEqual(answer.status,'node_lp_optimal_proven',asdict(answer.certificate))
            self.assertAlmostEqual(answer.lp_objective,expected['objective'],places=5)
            self.assertGreaterEqual(answer.lp_upper_bound+1e-5,expected['objective'])
        return answer

    def test_all_coupling_rows_elastic_convexity_hard(self):
        d=small();d['lines'][0]['required_tasks']=['a'];d['lines'][0]['precedence']=[['a','b']]
        m=build_node_master(d,empty_pool(d),NodeRestrictions(),1)
        keys={k for k,s,v in m.elastic}
        self.assertEqual(keys,{k for k in m.rows if k[0]!='station'})
        for key,row in m.rows.items():
            signs=[sign for k,sign,v in m.elastic if k==key]
            self.assertEqual(signs,[] if key[0]=='station' else [1,-1] if row.sense==0 else [-1])
        self.assertTrue(all(m.objective.get(v)==-1 for k,s,v in m.elastic))
        self.assertTrue(all(m.objective.get(v,0)==0 for v in m.variables.values()))

    def test_branch_one_no_empty_and_local_infeasible(self):
        d=small();r=NodeRestrictions().add(d,('L','a',1,'H'),1)
        answer=self.compare(d,r)
        self.assertTrue(all(('a','H') in c.assignments for c in answer.pool['L',1]))
        d['lines'][0]['tasks'][0]['modes']['H']['time']=5
        answer=self.compare(d,r)
        self.assertEqual(answer.status,'local_infeasible_proven')
        d['lines'][0]['tasks'][0]['modes']['H']['time']=2;d['lines'][0]['fatigue_limit']=0
        self.assertEqual(self.compare(d,r).status,'local_infeasible_proven')

    def test_inherited_duplicate_optional_task_recovered(self):
        d=small();l=d['lines'][0];r=NodeRestrictions().add(d,('L','a',1,'H'),1)
        parent={('L',s):[make_column(l,s,[('a','H')])] for s in (1,2)}
        before={k:tuple(v) for k,v in parent.items()}
        answer=self.compare(d,r,parent)
        first=answer.certificate.rounds[0]
        self.assertGreater(first['artificial_sum'],0)
        self.assertTrue(any(a['row']==['task','L','a'] and a['value']>0 for a in first['artificials']))
        self.assertEqual(before,{k:tuple(v) for k,v in parent.items()})

    def test_initial_human_resource_conflict_recovered_by_missing_column(self):
        d=small();l=d['lines'][0];d['human_limit']=1;l['required_tasks']=['a','b']
        r=NodeRestrictions().add(d,('L','a',1,'H'),1)
        parent={('L',1):[make_column(l,1,[('a','H')])],('L',2):[make_column(l,2,[('b','H')])]}
        answer=self.compare(d,r,parent)
        self.assertGreater(answer.certificate.rounds[0]['artificial_sum'],0)
        self.assertTrue(answer.certificate.phase1_status=='feasible_real_RMP_confirmed')

    def test_global_resource_infeasible_and_AND_inconsistent(self):
        for mode,limit in (('H','human_limit'),('R','robot_limit')):
            d=small();d[limit]=1
            r=NodeRestrictions().add(d,('L','a',1,mode),1).add(d,('L','b',2,mode),1)
            self.assertEqual(self.compare(d,r).status,'phase1_infeasible_proven')
        d=small();d['lines'][0]['precedence']=[['a','b']]
        r=NodeRestrictions().add(d,('L','b',1,'H'),1).add(d,('L','a',2,'H'),1)
        self.assertEqual(self.compare(d,r).status,'phase1_infeasible_proven')

    def test_branch_zero_and_sibling_pool_isolation(self):
        d=small();root=self.compare(d);before={k:tuple(v) for k,v in root.pool.items()}
        r=NodeRestrictions().add(d,('L','a',1,'H'),0);left=self.compare(d,r,root.pool)
        r1=NodeRestrictions().add(d,('L','a',1,'H'),1);right=self.compare(d,r1,root.pool)
        self.assertEqual(before,{k:tuple(v) for k,v in root.pool.items()})
        self.assertTrue(all(('a','H') not in c.assignments for c in left.pool['L',1]))
        left.pool['L',1].clear();self.assertTrue(right.pool['L',1])

    def test_restricted_pricing_against_independent_enumeration_both_phases(self):
        d=small();d['lines'][0]['precedence']=[['a','b']];r=NodeRestrictions().add(d,('L','a',1,'R'),0)
        complete=node_pool(d,r.to_records());rng=random.Random(321)
        with use_backend(BackendConfig(name='cbc')):
            for phase in (1,2):
                for trial in range(3):
                    dual={k:rng.uniform(0,2) if sense=='<=' else rng.uniform(-2,2) for k,(sense,b) in oracle.rowspec(d).items()}
                    for line,s in blocks(d):
                        a=price_node(line,s,dual,phase,r)
                        self.assertIsInstance(a,NodePricingResult);self.assertTrue(a.certificate.optimal)
                        self.assertAlmostEqual(a.certificate.reduced_cost,max(oracle.rc(line,s,p,dual,phase) for p in complete[line['id'],s]),places=5)

    def test_plain_pricing_pair_is_rejected_and_phase_switch_failure_not_pruned(self):
        d=small();col=empty_pool(d)['L',1][0]
        with patch.object(node_module,'price_node',return_value=(col,0.)):
            r=solve_node(d)
        self.assertEqual(r.status,'numerical_uncertain');self.assertIsNone(r.lp_upper_bound)
        original=node_module.solve_node_master
        def fail_phase2(m,*args,**kwargs):
            if m.phase==2:
                e=NumericalUncertain('Injected real RMP infeasible after artificial phase')
                e.solver_result={'status':'infeasible'};raise e
            return original(m,*args,**kwargs)
        with patch.object(node_module,'solve_node_master',side_effect=fail_phase2):
            r=solve_node(d)
        self.assertEqual(r.status,'numerical_uncertain')
        self.assertNotEqual(r.certificate.phase1_status,'infeasible_proven')

    def test_infeasible_or_optimal_labels_without_solver_domain_proof_rejected(self):
        d=small();r=NodeRestrictions().add(d,('L','a',1,'H'),1)
        cert=PricingCertificate('L',1,1,'local_feasibility',fixed_variables=fixed_records(r,'L',1),status='infeasible')
        with patch.object(node_module,'price_node',return_value=NodePricingResult(cert)):
            result=solve_node(d,r)
        self.assertEqual(result.status,'numerical_uncertain')
        self.assertNotEqual(result.status,'local_infeasible_proven')


if __name__=='__main__':unittest.main()
