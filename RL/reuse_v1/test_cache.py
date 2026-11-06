import json,sys,unittest
from copy import deepcopy
from proof_cache import ROOT,ProofCache
from validate import enumerate_all

def certificate(lid,col,p):
    q=col['profit']-p[0]*col['human']-p[1]*col['robot']
    return dict(line=lid,phase=2,caps=None,optimal=True,column=col,human_price=p[0],robot_price=p[1],sigma=3.,reduced_cost=q-3.,
                solver=dict(backend='cplex_py',native_status=101,objective=q-3.,best_bound=q-3.))

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'sub/stage7/evidence/validation/gap_cplex_py/instance.json').read_bytes())
        self.pool=enumerate_all(self.data)

    def test_complete_enumeration_across_prices(self):
        for line in self.data['lines']:
            cols=self.pool[line['id']];cache=ProofCache(line)
            self.assertIsNone(cache.query(line,[0,0],cols)['upper'])
            for p in ([0,0],[1,7],[8,2],[3,3]):
                col=max(cols,key=lambda c:c['profit']-p[0]*c['human']-p[1]*c['robot'])
                cache.add(line,certificate(line['id'],col,p),str(p))
                for target in ([0,0],[2,9],[9,1],[.5,.25],p):
                    q=cache.query(line,target,cols);truth=max(c['profit']-target[0]*c['human']-target[1]*c['robot'] for c in cols)
                    self.assertGreaterEqual(q['upper']+1e-7,truth)
                    self.assertAlmostEqual(q['lower'],truth)
                q=cache.query(line,p,cols);self.assertLessEqual(q['upper']-q['lower'],1e-7)

    def test_reject_forged_or_restricted_sources(self):
        line=self.data['lines'][0];col=self.pool[line['id']][0];c=certificate(line['id'],col,[0,0]);cache=ProofCache(line)
        for key,value in [('caps',[1,1]),('restrictions',[['x',1]]),('phase',1),('line','wrong')]:
            bad=deepcopy(c);bad[key]=value
            with self.assertRaises(ValueError):cache.add(line,bad,'bad')
        for key,value in [('native_status',107),('best_bound',999),('objective',None)]:
            bad=deepcopy(c);bad['solver'][key]=value
            with self.assertRaises(ValueError):cache.add(line,bad,'bad')
        bad=deepcopy(c);bad['optimal']=False;self.assertFalse(cache.add(line,bad,'unproven'));self.assertEqual(cache.sources,[])

    def test_domain_and_query_isolation(self):
        line=self.data['lines'][0];cache=ProofCache(line);changed=deepcopy(line);changed['cycle_time']+=1
        with self.assertRaises(ValueError):cache.query(changed,[0,0])
        for p in ([-1,0],[float('nan'),0],[1]):
            with self.assertRaises(ValueError):cache.query(line,p)
        other=ProofCache(line);col=self.pool[line['id']][0];cache.add(line,certificate(line['id'],col,[0,0]),'one')
        self.assertEqual(other.sources,[])
if __name__=='__main__':unittest.main(verbosity=2)
