import json,sys,unittest
from copy import deepcopy
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'stage1')]
from independent_solver import run
from audit_independent import audit

class Baseline(unittest.TestCase):
    def test_oracle_compatible_and_conflicting(self):
        data=json.loads((HERE.parent/'stage7/evidence/validation/gap_cplex_py/instance.json').read_bytes())
        for ample in (False,True):
            d=deepcopy(data)
            if ample:d.update(human_limit=2,robot_limit=2)
            r=run(d,time_limit=10);audit(d,r,enumerate_profiles=True)
            self.assertEqual(r['global_integer_optimal_proven'],ample)
            if not ample:
                self.assertEqual(r['status'],'resource_incompatible_unresolved')
                self.assertIsNone(r['global_lower_bound']);self.assertFalse(r['global_infeasibility_proven'])
            bad=deepcopy(r);bad['global_upper_bound']-=1
            with self.assertRaises(AssertionError):audit(d,bad,enumerate_profiles=True)
    def test_integer_infeasibility_is_not_independent_failure_proof(self):
        d=json.loads((HERE.parent/'stage7/evidence/validation/lp_yes_ip_no_cplex_py/instance.json').read_bytes())
        r=run(d,time_limit=10);audit(d,r,enumerate_profiles=True)
        self.assertFalse(r['global_integer_optimal_proven']);self.assertFalse(r['global_infeasibility_proven'])
if __name__=='__main__':unittest.main(verbosity=2)
