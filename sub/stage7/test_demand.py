import sys,unittest
from pathlib import Path
from copy import deepcopy
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'stage1'),str(HERE.parent/'stage4')]
from demand_profiles import run
from verify7 import audit
from gap_case import instance
from cases import lp_yes_ip_no
class Tests(unittest.TestCase):
    def test_gap_and_infeasibility(self):
        for d in (instance(),lp_yes_ip_no()):
            for solver in ('cplex_py','cbc'):
                r=run(d,time_limit=10,solver=solver);audit(d,r)
                if d==instance():self.assertTrue(r['global_integer_optimal_proven']);self.assertAlmostEqual(r['global_lower_bound'],2)
                else:self.assertTrue(r['global_infeasibility_proven'])
    def test_timeout_and_unknown_bound(self):
        r=run(instance(),time_limit=1e-9);audit(instance(),r)
        self.assertFalse(r['global_integer_optimal_proven']);self.assertIsNone(r['global_upper_bound'])
    def test_forged_source_query_and_missing_profile(self):
        d=instance();r=run(d,time_limit=10);self.assertTrue(r['queries'])
        for kind in ('source','query','missing'):
            bad=deepcopy(r)
            if kind=='source':bad['bound_sources']['A'][0]['constant']-=1
            elif kind=='query':bad['queries'][0]['upper_value']+=1
            else:bad['table']['A'].pop()
            with self.assertRaises(AssertionError):audit(d,bad)
if __name__=='__main__':unittest.main(verbosity=2)
