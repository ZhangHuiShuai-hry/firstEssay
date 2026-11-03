"""Tree bounds, exact integer conclusions, and interrupted/forged proofs."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from branch_price import run_branch_price
from node_master import solve_node
from node_state import NodePricingResult,PricingCertificate,NodeRestrictions,NumericPolicy
from bp_solution import verify_integer_assignments
from test_node_cg import small

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'docs/branch_and_price'))
from independent_bp_verify import verify_tree,CertificateRejected,oracle


def case(name):
    return dict(oracle.cases())[name]


class BranchPriceTests(unittest.TestCase):
    def test_integer_root_and_positive_gap_global_optimum(self):
        for name,expected in (('single_line',21),('two_lines',24),('generator_n6_L1_s13',56.63)):
            result=run_branch_price(case(name),solver='cplex_py',time_limit=30)
            self.assertEqual(result['status'],'optimal_within_tolerance',result['termination_reason'])
            self.assertAlmostEqual(result['integer_incumbent_objective'],expected,places=5)
            self.assertTrue(result['global_integer_optimal_proven'])
            self.assertTrue(verify_tree(case(name),result,solve_oracles=False)['passed'])
            if name!='single_line':self.assertGreater(result['total_nodes_processed'],1)

    def test_integer_infeasibility_after_fractional_root_and_root_LP_infeasible(self):
        for name in ('lp_yes_ip_no','and_diamond'):
            result=run_branch_price(case(name),solver='cplex_py',time_limit=20)
            self.assertEqual(result['status'],'infeasible_proven',result['termination_reason'])
            self.assertTrue(result['global_infeasibility_proven']);self.assertFalse(result['has_integer_incumbent'])
            self.assertTrue(verify_tree(case(name),result,solve_oracles=False)['passed'])
            if name=='lp_yes_ip_no':self.assertEqual(result['root_lp_status'],'node_lp_optimal_proven')

    def test_node_limit_retains_children_and_inherited_bound(self):
        d=case('two_lines');r=run_branch_price(d,solver='cplex_py',node_limit=1)
        self.assertEqual(r['status'],'node_limit');self.assertEqual(len(r['open_nodes']),2)
        self.assertEqual(r['total_nodes_processed'],1);self.assertAlmostEqual(r['global_upper_bound'],27)
        self.assertFalse(r['global_integer_optimal_proven']);self.assertIsNone(r['global_lower_bound'])
        self.assertTrue(verify_tree(d,r,solve_oracles=False)['passed'])

    def test_actual_root_time_limit_unknown_and_child_deadline_with_inherited_bound(self):
        d=case('two_lines');r=run_branch_price(d,time_limit=1e-12)
        self.assertEqual(r['status'],'time_limit');self.assertIsNone(r['global_upper_bound'])
        self.assertFalse(r['global_integer_optimal_proven']);self.assertTrue(verify_tree(d,r,solve_oracles=False)['passed'])
        calls=[]
        def deadline_after_root(*args,**kwargs):
            if calls:kwargs['deadline']=time.perf_counter()-1
            calls.append(True);return solve_node(*args,**kwargs)
        r=run_branch_price(d,solver='cplex_py',_node_solver=deadline_after_root)
        self.assertEqual(r['status'],'time_limit');self.assertEqual(len(r['open_nodes']),2)
        self.assertAlmostEqual(r['global_upper_bound'],27);self.assertFalse(r['global_integer_optimal_proven'])
        self.assertTrue(verify_tree(d,r,solve_oracles=False)['passed'])

    def test_solver_error_and_cg_iteration_limit_never_prune(self):
        d=small()
        def error(*args,**kwargs):raise RuntimeError('injected native API failure')
        r=run_branch_price(d,_node_solver=error)
        self.assertEqual(r['status'],'solver_error');self.assertEqual(len(r['open_nodes']),1)
        self.assertFalse(r['global_integer_optimal_proven']);self.assertTrue(verify_tree(d,r,solve_oracles=False)['passed'])
        r=run_branch_price(d,max_cg_iterations=1)
        self.assertEqual(r['status'],'numerical_uncertain');self.assertTrue(r['open_nodes'])
        self.assertFalse(r['global_integer_optimal_proven']);self.assertTrue(verify_tree(d,r,solve_oracles=False)['passed'])

    def test_zero_and_required_negative_profit(self):
        for name in ('zero_profit','dual_degenerate','heterogeneous_gap'):
            r=run_branch_price(case(name),solver='cplex_py')
            self.assertTrue(r['global_integer_optimal_proven']);self.assertTrue(verify_tree(case(name),r,solve_oracles=False)['passed'])
        d=small();l=d['lines'][0];l['required_tasks']=['a','b']
        for t in l['tasks']:t['value']=-2
        r=run_branch_price(d,solver='cbc');self.assertLess(r['global_lower_bound'],0)
        self.assertTrue(r['global_integer_optimal_proven']);self.assertTrue(verify_tree(d,r,solve_oracles=False)['passed'])

    def test_tampered_pruning_bounds_branching_and_pricing_rejected(self):
        d=case('two_lines');result=run_branch_price(d,solver='cplex_py')
        for kind in ('upper','prune','branch','pricing','witness','lost_node'):
            r=copy.deepcopy(result)
            if kind=='upper':r['global_upper_bound']-=1
            if kind=='prune':r['node_history'][0]['node_status']='pruned_bound';r['node_history'][0]['pruning']={'integer_lower_bound':100,'upper_bound':0}
            if kind=='branch':r['node_history'][1]['restrictions'][0]['value']=1-r['node_history'][1]['restrictions'][0]['value']
            if kind=='pricing':
                round_=next(x for x in r['node_history'][0]['certificate']['rounds'] if x['complete_pricing'])
                round_['pricing'][0]['optimal']=False
            if kind=='witness':r['integer_incumbent_solution']['stations'][0]['assignments'].append(['not_a_task','H'])
            if kind=='lost_node':r['node_history'][0]['children'].pop()
            with self.subTest(kind=kind),self.assertRaises((CertificateRejected,KeyError)):
                verify_tree(d,r,solve_oracles=False)

    def test_CLI_refuses_overwrite_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'existing.json';target.write_text('preserve me')
            cmd=[sys.executable,str(ROOT/'code/dwcg/branch_price.py'),str(ROOT/'code/milp/examples/single_line.json'),'--output',str(target)]
            r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertEqual(r.returncode,1);self.assertEqual(target.read_text(),'preserve me')
            cmd[-1]=str(Path(tmp)/'limited.json');cmd+=['--node-limit','0']
            r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertEqual(r.returncode,2);self.assertEqual(json.loads(Path(cmd[4]).read_text())['status'],'node_limit')

    def test_tiny_rc_integral_candidate_does_not_hide_global_gap(self):
        d=small();l=d['lines'][0]
        for t in l['tasks']:
            t['value']=3e-8
            for m in t['modes'].values():m['cost']=0
        for s in l['stations']:s.update(fixed_cost=0,human_cost=0,robot_cost=0)
        policy=NumericPolicy(lp_dual_tolerance=1e-9,global_absolute_tolerance=1e-12,global_relative_tolerance=0)
        r=run_branch_price(d,solver='cplex_py',policy=policy)
        self.assertEqual(r['status'],'numerical_uncertain')
        self.assertFalse(r['global_integer_optimal_proven']);self.assertTrue(r['has_integer_incumbent'])
        self.assertGreater(r['absolute_gap'],policy.global_absolute_tolerance)
        self.assertTrue(r['open_nodes']);self.assertTrue(verify_tree(d,r,solve_oracles=False)['passed'])


if __name__=='__main__':unittest.main()
