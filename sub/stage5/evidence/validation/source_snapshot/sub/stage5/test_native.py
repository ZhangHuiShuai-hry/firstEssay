import unittest,json,sys,time
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'stage4'),str(HERE.parent/'stage1')]
from branch_price5 import run
from node_cg5 import solve_node
from native_node_pp import LinePricing,NodeRestrictions
from line_bp_pricing import solve_line,allows
from line_cg import BackendConfig,use_backend
from verify5 import audit
from validate import enumerate_all
from gap_case import instance
from cases import lp_yes_ip_no

class Tests(unittest.TestCase):
    def test_same_node_same_duals_and_immutable_domains(self):
        d=instance();full=enumerate_all(d)
        domains=[NodeRestrictions(),NodeRestrictions().add(d,('A','t',1,'J'),0),NodeRestrictions().add(d,('A','t',1,'J'),1),
            NodeRestrictions().add(d,('B','t',1,'H'),0).add(d,('B','t',1,'R'),0)]
        for fixes in domains:
            session=LinePricing(BackendConfig(name='cplex_py'),[],restrictions=fixes)
            try:
                with use_backend(BackendConfig(name='cplex_py')):
                    for phase,h,r,sigma in [(2,0,0,0),(1,.4,1,-3),(2,3,2,17),(1,0,0,0)]:
                        for line in d['lines']:
                            kw=dict(phase=phase,human_price=h,robot_price=r,sigma=sigma,restrictions=fixes,time_limit=5)
                            _,a=solve_line(line,**kw);_,b=session.solve(line,**kw)
                            self.assertEqual(a['optimal'],b['optimal']);self.assertEqual(a['status'],b['status'])
                            if a['optimal']:self.assertAlmostEqual(a['reduced_cost'],b['reduced_cost'])
                with self.assertRaises(ValueError):session.solve(d['lines'][0],restrictions=domains[1] if fixes!=domains[1] else domains[0])
            finally:session.close()
    def test_complete_trees_all_strategies(self):
        for d in (instance(),lp_yes_ip_no()):
            for strategy in ('rebuild','reuse','warm'):
                with self.subTest(strategy=strategy):
                    r=run(d,time_limit=10,pricing=strategy);audit(d,r)
                    if d==instance():self.assertTrue(r['global_integer_optimal_proven']);self.assertAlmostEqual(r['global_lower_bound'],2)
                    else:self.assertTrue(r['global_infeasibility_proven'])
    def test_inherited_start_and_pool_isolation(self):
        d=instance();parent=solve_node(d,time_limit=5);before=deepcopy(parent['pool'])
        fix=NodeRestrictions().add(d,('A','t',1,'J'),0)
        pool={l:[dict(c) for c in cs if allows(c,fix)] for l,cs in parent['pool'].items()}
        s=LinePricing(BackendConfig(name='cplex_py'),[],restrictions=fix,seed_pool=pool)
        brother=LinePricing(BackendConfig(name='cplex_py'),[],restrictions=NodeRestrictions().add(d,('A','t',1,'J'),1))
        try:
            _,cert=s.solve(d['lines'][0],time_limit=5)
            self.assertTrue(cert['mip_start_submitted']);self.assertEqual(cert['mip_start_source'],'inherited_pool')
            self.assertFalse(brother.sessions);self.assertEqual(parent['pool'],before)
        finally:s.close();brother.close()
    def test_corrupt_start_and_missing_record_rejected(self):
        d=instance();r=run(d,time_limit=5,pricing='warm');audit(d,r)
        c=next(c for n in r['node_history'] if n['result'] for h in n['result']['history'] for c in h['pricing'] if c.get('mip_start_submitted'))
        c['mip_start_column']['profit']+=1
        with self.assertRaises(AssertionError):audit(d,r)
    def test_limits_and_native_error_remain_unresolved(self):
        for limit in (0,1):
            r=run(instance(),node_limit=limit,pricing='warm',time_limit=5);audit(instance(),r)
            self.assertTrue(r['open_nodes']);self.assertFalse(r['global_integer_optimal_proven'])
        with patch.object(LinePricing,'solve',side_effect=RuntimeError('injected native error')):
            r=run(instance(),time_limit=5,pricing='warm')
        audit(instance(),r);self.assertEqual(r['status'],'solver_error');self.assertTrue(r['open_nodes'])

if __name__=='__main__':unittest.main(verbosity=2)
