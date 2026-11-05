import unittest,json,sys
from pathlib import Path
from copy import deepcopy
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'stage1'),str(HERE.parent/'stage4')]
from resource_dp import run,NodeRestrictions
from verify6 import audit
from gap_case import instance
from cases import lp_yes_ip_no
class Tests(unittest.TestCase):
    def test_exact_cases(self):
        for data,expected in [(instance(),2),(lp_yes_ip_no(),None)]:
            for solver in ('cplex_py','cbc'):
                r=run(data,time_limit=10,solver=solver);audit(data,r)
                if expected is None:self.assertTrue(r['global_infeasibility_proven'])
                else:self.assertTrue(r['global_integer_optimal_proven']);self.assertAlmostEqual(r['global_lower_bound'],expected)
    def test_node_domains_are_separate(self):
        d=instance()
        for v in (0,1):
            fix=NodeRestrictions().add(d,('A','t',1,'J'),v)
            r=run(d,time_limit=5,restrictions=fix);audit(d,r)
            self.assertEqual(r['global_infeasibility_proven'],bool(v))
    def test_timeout_unknown_bounds_not_incumbents(self):
        r=run(instance(),time_limit=1e-9);audit(instance(),r)
        self.assertIsNone(r['global_upper_bound']);self.assertFalse(r['global_integer_optimal_proven'])
    def test_forged_missing_profile_or_bound(self):
        d=instance();r=run(d,time_limit=5)
        for mode in ('missing','bound','witness'):
            b=deepcopy(r)
            if mode=='missing':b['table']['A'].pop()
            elif mode=='bound':b['global_upper_bound']-=1
            else:b['witness']['objective']+=1
            with self.assertRaises(AssertionError):audit(d,b)
if __name__=='__main__':unittest.main(verbosity=2)
