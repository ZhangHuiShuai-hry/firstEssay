import json,sys,unittest
from copy import deepcopy
from pathlib import Path
from pricing_actions import ROOT,prices,exact_upper_bound
from validate import enumerate_all,solve_full
class Bounds(unittest.TestCase):
    def test_enumeration_all_actions_and_signed_prices(self):
        d=json.loads((ROOT/'sub/stage7/evidence/validation/gap_cplex_py/instance.json').read_bytes());pool=enumerate_all(d);lp=solve_full(d,pool)['objective']
        for a in (1.,.75,.5,.25):
            p=prices([4.,7.],[1.,2.],a);cs=[]
            for l,cols in pool.items():
                c=max(cols,key=lambda c:c['profit']-p[0]*c['human']-p[1]*c['robot']);q=c['profit']-p[0]*c['human']-p[1]*c['robot'];cs.append(dict(line=l,phase=2,caps=None,sigma=0,human_price=p[0],robot_price=p[1],column=c,optimal=True,reduced_cost=q,solver=dict(native_status=101,objective=q,best_bound=q)))
            self.assertGreaterEqual(exact_upper_bound(d,p,cs)+1e-7,lp)
            timed=deepcopy(cs);timed[0]['optimal']=False;self.assertIsNone(exact_upper_bound(d,p,timed))
            bad=deepcopy(cs);bad[0]['solver']['objective']+=1
            with self.assertRaises(ValueError):exact_upper_bound(d,p,bad)
            with self.assertRaises(ValueError):exact_upper_bound(d,p,cs[:-1])
            bad=deepcopy(cs);bad[0]['human_price']+=1
            with self.assertRaises(ValueError):exact_upper_bound(d,p,bad)
        with self.assertRaises(ValueError):prices([-1,0],[0,0],1.)
        with self.assertRaises(ValueError):prices([float('nan'),0],[0,0],1.)
if __name__=='__main__':unittest.main(verbosity=2)
