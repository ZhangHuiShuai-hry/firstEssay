import json,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from balanced_bound import run
from cg_balanced import run as cg
from line_cg import solve_line
from verify_economic import audit
from stage2_verify import audit as cg_audit

class Balanced(unittest.TestCase):
    def test_tiny_oracle(self):
        for name in ('gap','lp_yes_ip_no'):
            with self.subTest(name=name):
                d=json.loads((HERE.parent/f'stage7/evidence/validation/{name}_cplex_py/instance.json').read_bytes())
                r=run(d,time_limit=15,cg_fraction=.9,cg_cap_seconds=1000000)
                audit(d,r,enumerate_profiles=True)
                if name=='gap':self.assertTrue(r['global_integer_optimal_proven']);self.assertAlmostEqual(r['global_lower_bound'],2)
                else:self.assertTrue(r['global_infeasibility_proven'])

    def test_unproven_first_block_does_not_skip_second(self):
        d=json.loads((HERE.parent/'stage7/evidence/validation/gap_cplex_py/instance.json').read_bytes());calls=[]
        def price(line,**kwargs):
            col,c=solve_line(line,**kwargs)
            if kwargs.get('purpose','pricing')=='pricing':
                calls.append(line['id'])
                if len(calls)==1:
                    # 故障注入：只降级真实最优证书，保留真实可行列与有效界。
                    c.update(optimal=False,status='time_limit',fault_injection='force_unproven')
                    c['solver'].update(optimal=False,status='time_limit',native_status=107)
            return col,c
        r=cg(d,time_limit=15,init_seconds=.5,pricing='rebuild',price_override=price)
        self.assertEqual(calls,[l['id'] for l in d['lines']])
        self.assertEqual(len(r['history'][-1]['pricing']),len(d['lines']))
        self.assertFalse(r['history'][-1]['complete_exact_pricing'])
        self.assertFalse(r['lp_optimal_proven']);self.assertFalse(r['global_integer_optimal_proven'])
        cg_audit(d,r)

if __name__=='__main__':unittest.main(verbosity=2)
