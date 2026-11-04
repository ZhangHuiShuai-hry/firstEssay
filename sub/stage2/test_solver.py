import sys,json,unittest
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1]/'stage1')]
import solver
from stage2_verify import audit
from gap_case import instance
SUB=Path(__file__).resolve().parents[1]

class Tests(unittest.TestCase):
    def test_variants_tiny_and_real_integrality_gap(self):
        datasets=[json.loads((SUB/'../code/data/tasks005_lines02_each03-02.json').read_text()),instance()]
        for d in datasets:
            for short,quota in ((None,False),(.5,False),(None,True),(.5,True)):
                with self.subTest(short=short,quota=quota):
                    r=solver.run(d,time_limit=10,init_seconds=short,quota=quota)
                    audit(d,r)
                    self.assertNotIn(r['status'],('solver_error','numerical_uncertain'))
                    if len(d['lines'][0]['tasks'])==1:
                        self.assertFalse(r['global_integer_optimal_proven']);self.assertAlmostEqual(r['upper_bound'],6.5)
                    else:self.assertTrue(r['global_integer_optimal_proven'])

    def test_quota_record_and_forgery_rejection(self):
        r=solver.run(instance(),time_limit=10,init_seconds=.5,quota=True)
        self.assertTrue(r['quota_repair']);audit(instance(),r)
        bad=deepcopy(r);bad['quota_repair'][0]['pricing'][0]['reduced_cost']+=1
        with self.assertRaises(AssertionError):audit(instance(),bad)

    def test_short_no_incumbent_fallback_is_not_economic_upper_bound(self):
        actual=solver.solve_line
        def interrupt(line,**kwargs):
            c,e=actual(line,**kwargs)
            if kwargs.get('purpose')=='initialization':
                e.update(column=None,optimal=False,status='time_limit',reduced_cost=None)
                e['solver'].update(optimal=False,has_incumbent=False,status='time_limit',best_bound=None)
                return None,e
            return c,e
        with patch.object(solver,'solve_line',side_effect=interrupt):r=solver.run(instance(),time_limit=10,init_seconds=.5,quota=True)
        self.assertEqual(len(r['initialization_fallback']),2);audit(instance(),r)
        self.assertNotIn('initial_independent_upper_bound',r)

    def test_timeout_and_configuration(self):
        r=solver.run(instance(),time_limit=1e-9,init_seconds=.5,quota=True)
        self.assertFalse(r['global_integer_optimal_proven']);self.assertIsNone(r['witness'])
        for v in (0,-1,float('nan')):
            with self.assertRaises(ValueError):solver.run(instance(),init_seconds=v)

if __name__=='__main__':unittest.main(verbosity=2)
