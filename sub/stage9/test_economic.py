import json,sys,unittest,zlib
from pathlib import Path
from copy import deepcopy
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from economic_bound import refine,derive
from verify_economic import audit
from demand_traced import run

class Economic(unittest.TestCase):
    def test_tiny_enumeration_and_forgery(self):
        for name in ('gap','lp_yes_ip_no'):
            with self.subTest(name=name):
                d=json.loads((HERE.parent/f'stage7/evidence/validation/{name}_cplex_py/instance.json').read_bytes())
                b=run(d,time_limit=12,cg_fraction=.9,cg_cap_seconds=1000000)
                r=refine(d,b);audit(d,r,enumerate_profiles=True)
                self.assertEqual(r['global_lower_bound'],b['global_lower_bound'])
                bad=deepcopy(r);bad['economic_evidence']['records'][0]['economic_upper_bound']-=1
                with self.assertRaises(AssertionError):audit(d,bad,enumerate_profiles=True)
                missing=deepcopy(b)
                for c in missing['cg']['initialization']:c['solver']['native_status']=0
                missing['cg']['history']=[]
                self.assertIsNone(derive(d,missing)['upper_bound'])

    def test_truncated_pricing_native_bound(self):
        folder=HERE/'evidence/pilot120/tasks060_lines02_r90_seed21__root_first'
        d=json.loads((folder/'instance.json').read_bytes());b=json.loads(zlib.decompress((folder/'result.json.zlib').read_bytes()))
        r=refine(d,b);audit(d,r)
        self.assertLess(r['global_upper_bound'],b['global_upper_bound'])
        self.assertFalse(r['global_integer_optimal_proven'])
        bad=deepcopy(b)
        c=bad['cg']['history'][1]['pricing'][1]
        c['solver']['best_bound']=c['reduced_cost']-1
        with self.assertRaises(ValueError):refine(d,bad)
        nonzero=deepcopy(b)
        nonzero['cg']['history'][1]['pricing'][1]['human_price']=1e-12
        paths=[x['path'] for x in derive(d,nonzero)['records']]
        self.assertNotIn('history/1/pricing/1',paths)

if __name__=='__main__':unittest.main(verbosity=2)
