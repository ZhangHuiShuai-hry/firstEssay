import json, sys, unittest, time
from unittest.mock import patch
from copy import deepcopy
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'stage2'),str(HERE.parent/'stage1')]
from persistent_line import LinePricing
from line_cg import solve_line, BackendConfig, use_backend
from stage2_verify import audit
from validate import enumerate_all
from gap_case import instance
from solver import run

class Tests(unittest.TestCase):
    def test_same_duals_full_enumeration_and_phase_reset(self):
        data=json.loads((HERE.parent.parent/'code/data/tasks006_lines01_each06_seed13.json').read_text())
        full=enumerate_all(data);events=[]
        with use_backend(BackendConfig(name='cplex_py'),events):
            session=LinePricing(BackendConfig(name='cplex_py'),events)
            try:
                for n,(phase,h,r,sigma) in enumerate([(2,0,0,0),(1,1,.3,-2),(2,3,2,17),(1,0,0,0),(2,0,0,-7)]):
                    for line in data['lines']:
                        kw=dict(phase=phase,human_price=h,robot_price=r,sigma=sigma,time_limit=10)
                        _,old=solve_line(line,**kw);_,new=session.solve(line,**kw)
                        expected=max((c['profit'] if phase==2 else 0)-h*c['human']-r*c['robot']-sigma for c in full[line['id']])
                        self.assertTrue(old['optimal'] and new['optimal'])
                        self.assertAlmostEqual(old['reduced_cost'],expected)
                        self.assertAlmostEqual(new['reduced_cost'],expected)
                        self.assertEqual(new['reused'],n>0)
                        self.assertAlmostEqual(sum(new['profile'].values()),new['total_seconds'],places=5)
            finally: session.close()

    def test_end_to_end_variants_and_forgery(self):
        paths=[HERE.parent.parent/'code/data/tasks005_lines02_each03-02.json',
               HERE.parent.parent/'code/data/tasks006_lines01_each06_seed13.json']
        datasets=[json.loads(p.read_text()) for p in paths]+[instance()]
        for data in datasets:
            for strategy in ('rebuild','reuse','warm'):
                with self.subTest(strategy=strategy,tasks=len(data['lines'][0]['tasks'])):
                    result=run(data,time_limit=10,init_seconds=.5,pricing=strategy)
                    audit(data,result)
                    self.assertNotIn(result['status'],('solver_error','numerical_uncertain'))
                    if data==instance():
                        self.assertFalse(result['global_integer_optimal_proven'])
                        self.assertAlmostEqual(result['upper_bound'],6.5)
                        bad=deepcopy(result)
                        rec=next(x for x in bad['history'] if x['complete_exact_pricing'])
                        rec['pricing'].pop()
                        with self.assertRaises(AssertionError):audit(data,bad)
                    else:self.assertTrue(result['global_integer_optimal_proven'])

    def test_isolation_timeout_and_invalid_domain(self):
        d=instance();a=LinePricing(BackendConfig(name='cplex_py'),[])
        b=LinePricing(BackendConfig(name='cplex_py'),[])
        try:
            a.solve(d['lines'][0],time_limit=1)
            self.assertFalse(b.sessions)
            changed=deepcopy(d['lines'][0]);changed['tasks'][0]['value']+=1
            with self.assertRaises(ValueError):a.solve(changed)
            with self.assertRaises(ValueError):a.solve(d['lines'][0],caps=(1,1))
            a.config.deadline=time.perf_counter()-1
            with self.assertRaises(TimeoutError):a.solve(d['lines'][0])
        finally:a.close();b.close()
        result=run(d,time_limit=1e-9,pricing='warm')
        self.assertFalse(result['global_integer_optimal_proven'])

    def test_failed_native_pricing_and_stale_dual_never_prove(self):
        actual=LinePricing.solve
        def fail(session,line,**kwargs):
            if kwargs.get('purpose','pricing')=='pricing':
                raise RuntimeError('injected native failure')
            return actual(session,line,**kwargs)
        with patch.object(LinePricing,'solve',new=fail):
            r=run(instance(),time_limit=5,pricing='warm',init_seconds=.5)
        self.assertEqual(r['status'],'solver_error')
        self.assertFalse(r['global_integer_optimal_proven'])
        self.assertFalse(r['global_infeasibility_proven'])
        r=run(instance(),time_limit=5,pricing='warm',init_seconds=.5)
        bad=deepcopy(r)
        rec=next(x for x in bad['history'] if x['complete_exact_pricing'])
        rec['pricing'][0]['human_price']+=1
        with self.assertRaises(AssertionError):audit(instance(),bad)

if __name__=='__main__':unittest.main(verbosity=2)
