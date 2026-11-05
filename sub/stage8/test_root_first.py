import json,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent),str(HERE.parent/'stage3'),str(HERE.parent/'stage6'),str(HERE.parent/'stage7')]
from demand_traced import run
from verify7 import audit

class RootFirst(unittest.TestCase):
    def test_gap_and_infeasible(self):
        for name in ('gap','lp_yes_ip_no'):
            with self.subTest(name=name):
                d=json.loads((HERE.parent/f'stage7/evidence/validation/{name}_cplex_py/instance.json').read_bytes())
                r=run(d,time_limit=15,cg_fraction=.9,cg_cap_seconds=1000000)
                audit(d,r)
                if name=='gap':self.assertTrue(r['global_integer_optimal_proven']);self.assertAlmostEqual(r['global_lower_bound'],2)
                else:self.assertTrue(r['global_infeasibility_proven'])

if __name__=='__main__':unittest.main(verbosity=2)
