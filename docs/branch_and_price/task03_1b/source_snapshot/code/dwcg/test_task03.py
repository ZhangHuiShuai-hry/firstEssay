import sys
from pathlib import Path
import unittest
from dataclasses import asdict
from common import empty_pool,blocks
from node_state import NodeRestrictions,NumericPolicy
from node_master import build_node_master,solve_node_master
from node_pricing import price_node,validate_pricing_evidence
from node_persistent_pricing import NodePersistentPricing
from node_incremental_master import NodeIncrementalMaster
from solver_backend import BackendConfig,use_backend
from test_node_cg import small
from task03 import run
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'docs/branch_and_price'))
from independent_bp_verify import verify_tree,oracle


class NativeTests(unittest.TestCase):
    def test_PP_same_dual_and_sibling_fixes(self):
        d=small();p=NumericPolicy();cfg=BackendConfig(name='cplex_py')
        for b in (0,1):
            r=NodeRestrictions().add(d,('L','a',1,'H'),b);line=d['lines'][0]
            dual={k:.3 for k in build_node_master(d,empty_pool(d),NodeRestrictions(),1).rows}
            native=NodePersistentPricing(line,1,r,p,cfg)
            try:
                with use_backend(cfg):
                    for phase in (1,2,1,2):
                        a=price_node(line,1,dual,phase,r,p);n=native.run(dual,phase,None)
                        validate_pricing_evidence(n,line,1,phase,r,'pricing')
                        self.assertTrue(n.certificate.optimal,n.certificate.error)
                        self.assertAlmostEqual(a.certificate.reduced_cost,n.certificate.reduced_cost,places=6)
            finally:native.close()

    def test_RMP_matrix_and_switch(self):
        d=small();p=NumericPolicy();cfg=BackendConfig(name='cplex_py')
        from common import enumerate_pool
        pool=enumerate_pool(d);native=NodeIncrementalMaster(cfg)
        try:
            with use_backend(cfg):
                for phase in (1,2):
                    a=build_node_master(d,pool,NodeRestrictions(),phase);expected=solve_node_master(a,p)[0]
                    b=build_node_master(d,pool,NodeRestrictions(),phase);native.sync(b)
                    actual=__import__('node_master_optimized').solve_node_master(b,p)[0]
                    self.assertAlmostEqual(expected,actual,places=6)
                    for i,row in enumerate(b.rows.values()):
                        self.assertEqual(-row.constant,native.native.linear_constraints.get_rhs(i))
                        for v,c in row.items():self.assertEqual(c,native.native.linear_constraints.get_coefficients(i,native.indices[v.name]))
        finally:native.close()

    def test_native_global_proofs(self):
        for name in ('two_lines','generator_n6_L1_s13','lp_yes_ip_no'):
            d=dict(oracle.cases())[name]
            for version in ('V1','V2'):
                r=run(d,version,solver='cplex_py',time_limit=30)
                self.assertIn(r['status'],('optimal_within_tolerance','infeasible_proven'),r['termination_reason'])
                self.assertTrue(verify_tree(d,r,solve_oracles=False)['passed'])

if __name__=='__main__':unittest.main()
