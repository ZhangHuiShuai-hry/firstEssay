import json,sys,unittest
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'stage1')]
from branch_price import run
from line_bp_node import solve_node,NodeRestrictions
from line_bp_pricing import allows,solve_line
from bp_verify import audit,node_audit
from gap_case import instance
from cases import lp_yes_ip_no
from line_cg import BackendConfig,use_backend

class Tests(unittest.TestCase):
    def test_real_gap_complete_tree(self):
        r=run(instance(),time_limit=10);audit(instance(),r)
        self.assertTrue(r['global_integer_optimal_proven']);self.assertAlmostEqual(r['global_lower_bound'],2)
        self.assertGreater(r['total_nodes_created'],1)
    def test_full_lp_feasible_integer_infeasible(self):
        d=lp_yes_ip_no();r=run(d,time_limit=15);checked=audit(d,r)
        self.assertTrue(checked['full']['LP']['optimal']);self.assertTrue(r['global_infeasibility_proven'])
        self.assertGreater(r['total_nodes_created'],1)
    def test_branch_domains_and_missing_inherited_columns(self):
        d=instance();parent=solve_node(d,time_limit=5);before=deepcopy(parent['pool'])
        for v in (0,1):
            restrictions=NodeRestrictions().add(d,('A','t',1,'J'),v)
            r=solve_node(d,restrictions,parent['pool'],time_limit=5);node_audit(d,r)
            self.assertTrue(all(allows(c,restrictions) for cols in r['pool'].values() for c in cols))
        self.assertEqual(before,parent['pool'])
        r=solve_node(d,NodeRestrictions().add(d,('A','t',1,'J'),1),{},time_limit=5)
        node_audit(d,r);self.assertTrue(r['global_infeasibility_proven'])
    def test_local_empty_domain(self):
        d=instance();fix=NodeRestrictions().add(d,('B','t',1,'H'),0).add(d,('B','t',1,'R'),0)
        r=solve_node(d,fix,time_limit=5);node_audit(d,r)
        self.assertEqual(r['termination_reason'],'local_domain_empty')
    def test_limits_unknown_and_inherited_bounds(self):
        d=instance()
        for budget,limit in ((1e-9,100),(5,0),(5,1)):
            r=run(d,time_limit=budget,node_limit=limit);audit(d,r)
            self.assertFalse(r['global_integer_optimal_proven']);self.assertTrue(r['open_nodes'])
        r=run(d,time_limit=5,node_limit=1)
        self.assertAlmostEqual(r['global_upper_bound'],6.5)
        self.assertTrue(all(n['upper_bound']==6.5 for n in r['open_nodes']))
    def test_forged_tree_bound_duals_and_missing_pricing(self):
        d=instance();r=run(d,time_limit=5)
        for change in ('bound','missing','branch','x','prune'):
            b=deepcopy(r)
            if change=='bound':b['global_upper_bound']-=1
            elif change=='missing':next(h for h in b['node_history'][0]['result']['history'] if h['complete_exact_pricing'])['pricing'].pop()
            elif change=='branch':b['node_history'][2]['branch_from_parent']['value']=0
            elif change=='x':b['node_history'][0]['result']['x_values'][0]['value']+=.1
            else:next(n for n in b['node_history'] if n['status']=='bound_pruned')['prune_lower_bound']+=10
            with self.assertRaises(AssertionError):audit(d,b)
    def test_native_exception_keeps_node_open(self):
        with patch('line_bp_node.solve_line',side_effect=RuntimeError('injected PP error')):
            r=run(instance(),time_limit=5)
        audit(instance(),r);self.assertEqual(r['status'],'solver_error')
        self.assertFalse(r['global_integer_optimal_proven']);self.assertTrue(r['open_nodes'])
    def test_restriction_conflicts(self):
        d=instance();p=NodeRestrictions().add(d,('B','t',1,'H'),1)
        for key,value in [(('B','t',1,'H'),0),(('B','t',1,'R'),1),(('B','bad',1,'H'),0)]:
            with self.assertRaises(ValueError):p.add(d,key,value)
    def test_elastic_recovery_from_globally_infeasible_inherited_pool(self):
        from validate import enumerate_all
        d=instance();full=enumerate_all(d)
        # A执行J、B执行H：各线合法，组合超人力。完整节点LP仍可行。
        pool={l:[dict(line=l,**next(c for c in cs if (c['profit']==9 if l=='A' else c['human']==1)))] for l,cs in full.items()}
        before=deepcopy(pool);r=solve_node(d,parent_pool=pool,time_limit=5);node_audit(d,r)
        self.assertTrue(r['lp_optimal_proven']);self.assertEqual(before,pool)
        self.assertGreater(sum(r['history'][0]['rmp']['artificials'].values()),0)
    def test_zero_negative_objective_and_optional_empty(self):
        for value in (0,-1):
            d=instance()
            for l in d['lines']:
                l['required_tasks']=[]
                for t in l['tasks']:t['value']=value
            r=run(d,time_limit=5);audit(d,r)
            self.assertTrue(r['global_integer_optimal_proven']);self.assertAlmostEqual(r['global_lower_bound'],0)
    def test_cbc_rounded_duals_repaired_without_relaxing_tolerance(self):
        from find_cases import instance as make
        d=make(8);r=run(d,time_limit=10,solver='cbc');audit(d,r)
        self.assertTrue(r['global_integer_optimal_proven']);self.assertAlmostEqual(r['global_lower_bound'],31)
    def test_invalid_inherited_column_never_reaches_master(self):
        r=solve_node(instance(),time_limit=5);pool=deepcopy(r['pool'])
        pool['A'][0]['profit']+=100
        bad=solve_node(instance(),parent_pool=pool,time_limit=5)
        self.assertFalse(bad['lp_optimal_proven']);self.assertEqual(bad['history'],[])
    def test_child_pricing_interruption_keeps_parent_bound(self):
        import branch_price
        actual=branch_price.solve_node;calls=0
        def interrupt(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls>1:raise RuntimeError('injected child solver failure')
            return actual(*args,**kwargs)
        with patch.object(branch_price,'solve_node',side_effect=interrupt):r=run(instance(),time_limit=5)
        audit(instance(),r)
        self.assertFalse(r['global_integer_optimal_proven']);self.assertAlmostEqual(r['global_upper_bound'],6.5)

if __name__=='__main__':unittest.main(verbosity=2)
