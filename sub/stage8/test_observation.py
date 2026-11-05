import json,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent),str(HERE.parent/'stage3'),str(HERE.parent/'stage6'),str(HERE.parent/'stage7'),str(HERE.parent/'stage2')]
from cg_traced import run as cg
from demand_traced import run as demand
from compact_traced import run as compact
from verify7 import audit as demand_audit
from stage2_verify import audit as cg_audit
from validate import check_witness

class Observation(unittest.TestCase):
    def test_exact_gap_and_integer_infeasible(self):
        for case,expected in [('gap',2.),('lp_yes_ip_no',None)]:
            data=json.loads((HERE.parent/f'stage7/evidence/validation/{case}_cplex_py/instance.json').read_bytes())
            for method in ('compact','cg','demand'):
                with self.subTest(case=case,method=method):
                    rows=[]
                    kwargs=dict(pricing='warm',init_seconds=.5) if method=='cg' else {}
                    r={'compact':compact,'cg':cg,'demand':demand}[method](data,time_limit=15,progress=lambda *args:rows.append(args),**kwargs)
                    self.assertNotEqual(r['status'],'solver_error',r.get('error'))
                    if method=='cg':cg_audit(data,r)
                    elif method=='demand':demand_audit(data,r)
                    elif r['witness']:check_witness(data,r['witness'],r['global_lower_bound'])
                    self.assertTrue(rows)
                    if method!='cg':
                        self.assertEqual(r['global_infeasibility_proven'],expected is None)
                        if expected is not None:self.assertAlmostEqual(r['global_lower_bound'],expected)

if __name__=='__main__':unittest.main(verbosity=2)
