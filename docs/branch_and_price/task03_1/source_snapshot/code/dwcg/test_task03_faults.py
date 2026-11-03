"""Fail-closed native adapter regressions and full-node state interruptions."""
import time,unittest
from unittest.mock import patch
from dataclasses import asdict
from pathlib import Path
import sys
from test_node_cg import small
from node_state import NumericPolicy,NodeRestrictions
from node_persistent_pricing import NodePersistentPricing
from node_incremental_master import NodeIncrementalMaster
from node_master_optimized import solve_node,build_node_master,solve_node_master
from node_pricing import price_node
from common import empty_pool,enumerate_pool
from solver_backend import BackendConfig,use_backend
from task03 import run
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'docs/branch_and_price/task03'))
from task03_verify import verify_tree
from independent_bp_verify import oracle

class AdapterFaults(unittest.TestCase):
    def setUp(self):
        self.data=small();self.line=self.data['lines'][0];self.policy=NumericPolicy();self.cfg=BackendConfig(name='cplex_py')
        self.duals={k:0. for k in build_node_master(self.data,empty_pool(self.data),NodeRestrictions(),1).rows}

    def test_branch_one_lost_native_fix_rejected(self):
        r=NodeRestrictions().add(self.data,('L','a',1,'H'),1)
        pp=NodePersistentPricing(self.line,1,r,self.policy,self.cfg)
        try:
            j=pp.z['a','H'];pp.native.variables.set_lower_bounds(j,0);pp.native.variables.set_upper_bounds(j,0)
            n=pp.run(self.duals,1,None)
            self.assertFalse(n.certificate.optimal);self.assertIsNone(n.column)
        finally:pp.close()

    def test_stale_objective_updates(self):
        pp=NodePersistentPricing(self.line,1,NodeRestrictions(),self.policy,self.cfg)
        try:
            for k in range(8):
                dual={key:(k-3)*.71 if key[0]=='task' else k*.13 for key in self.duals}
                phase=1+k%2
                with use_backend(self.cfg):a=price_node(self.line,1,dual,phase,NodeRestrictions(),self.policy)
                n=pp.run(dual,phase,None)
                self.assertTrue(n.certificate.optimal,n.certificate.error)
                self.assertAlmostEqual(a.certificate.reduced_cost,n.certificate.reduced_cost,places=6)
        finally:pp.close()

    def test_optimal_native_bad_bound_rejected(self):
        pp=NodePersistentPricing(self.line,1,NodeRestrictions(),self.policy,self.cfg)
        try:
            with patch.object(pp.native.solution.MIP,'get_best_objective',return_value=-999.):
                n=pp.run(self.duals,1,None)
            self.assertFalse(n.certificate.optimal);self.assertIsNone(n.column)
        finally:pp.close()

    def test_policy_integrality_check_stricter_than_legacy_reader(self):
        pp=NodePersistentPricing(self.line,1,NodeRestrictions(),self.policy,self.cfg)
        read=pp.native.solution.get_values
        def perturbed(*args):
            a=read(*args);a[0]+=.0000003;return a
        try:
            with patch.object(pp.native.solution,'get_values',side_effect=perturbed):
                n=pp.run(self.duals,1,None)
            self.assertFalse(n.certificate.optimal);self.assertIn('Node policy',n.certificate.error)
        finally:pp.close()

    def test_native_pp_timeout_and_exception(self):
        pp=NodePersistentPricing(self.line,1,NodeRestrictions(),self.policy,self.cfg)
        try:
            n=pp.run(self.duals,1,time.perf_counter()-1)
            self.assertEqual(n.certificate.status,'time_limit');self.assertFalse(n.certificate.optimal)
            with patch.object(pp.native,'solve',side_effect=RuntimeError('injected native failure')):
                n=pp.run(self.duals,1,None)
            self.assertEqual(n.certificate.status,'solver_error');self.assertFalse(n.certificate.optimal)
        finally:pp.close()

    def test_time_limited_pp_incumbent_is_recorded_but_not_exact(self):
        pp=NodePersistentPricing(self.line,1,NodeRestrictions(),self.policy,self.cfg)
        try:
            # Real feasible native solve; only the termination code is injected.
            with patch.object(pp.native.solution,'get_status',return_value=107):
                n=pp.run(self.duals,1,None)
            self.assertEqual(n.certificate.status,'time_limit');self.assertFalse(n.certificate.optimal)
            self.assertTrue(n.certificate.has_incumbent);self.assertIsNotNone(n.certificate.incumbent)
            self.assertIsNone(n.column)
        finally:pp.close()

    def test_incremental_matrix_and_all_artificials_disabled(self):
        native=NodeIncrementalMaster(self.cfg);pool=enumerate_pool(self.data)
        try:
            with use_backend(self.cfg):
                for phase in (1,2):
                    a=build_node_master(self.data,pool,NodeRestrictions(),phase);native.sync(a)
                    solve_node_master(a,self.policy)
                    for i,row in enumerate(a.rows.values()):
                        self.assertEqual('E' if row.sense==0 else 'L',native.native.linear_constraints.get_senses(i))
                        for v in a.problem.variables():
                            if v.name=='__dummy':continue
                            j=native.indices[v.name]
                            self.assertEqual(float(row.get(v,0)),native.native.linear_constraints.get_coefficients(i,j))
                            self.assertEqual(float(a.objective.get(v,0)),native.native.objective.get_linear(j))
                    if phase==2:
                        for name,j in native.indices.items():
                            if name.startswith('elastic_'):
                                self.assertEqual(0,native.native.variables.get_upper_bounds(j))
                                self.assertEqual(0,native.native.objective.get_linear(j))
        finally:native.close()

    def test_node_timeouts_keep_open_domains(self):
        d=dict(oracle.cases())['two_lines']
        for v in ('V1','V2','V3'):
            for options in ({'time_limit':1e-12},{'node_limit':1},{'max_cg_iterations':1}):
                r=run(d,v,solver='cplex_py',**options)
                self.assertFalse(r['global_integer_optimal_proven']);self.assertFalse(r['global_infeasibility_proven'])
                self.assertTrue(r['open_nodes']);self.assertTrue(verify_tree(d,r,solve_oracles=False)['passed'])

    def test_native_lp_timeout_and_exception(self):
        from node_master_optimized import solve_node_master
        pool=enumerate_pool(self.data);m=build_node_master(self.data,pool,NodeRestrictions(),1)
        native=NodeIncrementalMaster(BackendConfig(name='cplex_py',deadline=time.perf_counter()-1))
        try:
            native.sync(m)
            with self.assertRaises(TimeoutError):solve_node_master(m,self.policy)
            native.deadline=None
            with patch.object(native.native,'solve',side_effect=RuntimeError('injected LP exception')):
                with self.assertRaises(RuntimeError):solve_node_master(m,self.policy)
        finally:native.close()

    def test_phase1_artificial_deletion_rejected(self):
        d=dict(oracle.cases())['two_lines']
        m=build_node_master(d,empty_pool(d),NodeRestrictions(),1)
        self.assertTrue(m.artificials)
        for v in m.artificials:v.upBound=0
        # Hard initial pool is infeasible; it must not be interpreted as a full-node proof.
        with use_backend(self.cfg):
            with self.assertRaises(Exception):solve_node_master(m,self.policy)

if __name__=='__main__':unittest.main()
