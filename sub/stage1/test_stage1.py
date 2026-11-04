import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gap_case import instance
from independent_solver import run as independent
from line_cg import run
from validate import audit,enumerate_all,solve_full
from quota_repair import repair
from copy import deepcopy
import json

class StageTests(unittest.TestCase):
    def test_independence_does_not_declare_global_infeasibility(self):
        r=independent(instance(),time_limit=10)
        self.assertEqual(r['status'],'resource_incompatible_unresolved')
        self.assertIsNone(r['witness']);self.assertIsNone(r['global_lower_bound'])
        self.assertAlmostEqual(r['global_upper_bound'],11)
        self.assertFalse(r['global_infeasibility_proven'])

    def test_true_full_line_integrality_gap_is_not_closed(self):
        d=instance();pool=enumerate_all(d)
        self.assertAlmostEqual(solve_full(d,pool)['objective'],6.5)
        self.assertAlmostEqual(solve_full(d,pool,True)['objective'],2)
        r=run(d,time_limit=10);audit(d,r)
        self.assertAlmostEqual(r['lower_bound'],2);self.assertAlmostEqual(r['upper_bound'],6.5)
        self.assertFalse(r['global_integer_optimal_proven'])

    def test_independent_timeout_has_no_invented_bound(self):
        r=independent(instance(),time_limit=1e-9)
        self.assertIsNone(r['global_upper_bound']);self.assertIsNone(r['witness'])
        self.assertFalse(r['global_integer_optimal_proven'])

    def test_quota_columns_repair_pool_without_mutation_or_false_proof(self):
        root=Path(__file__).resolve().parent/'evidence/pool_counterexample'
        d=json.loads((root/'instance.json').read_text());pool=json.loads((root/'restricted_pool.json').read_text());before=deepcopy(pool)
        r=repair(d,pool);self.assertEqual(before,pool)
        self.assertAlmostEqual(r['lower_bound'],40);self.assertFalse(r['global_integer_optimal_proven'])

    def test_no_quota_calls_does_not_infer_global_infeasibility(self):
        root=Path(__file__).resolve().parent/'evidence/pool_counterexample'
        d=json.loads((root/'instance.json').read_text());pool=json.loads((root/'restricted_pool.json').read_text())
        r=repair(d,pool,max_calls=0);self.assertIsNone(r['witness']);self.assertFalse(r['global_integer_optimal_proven'])

if __name__=='__main__':unittest.main(verbosity=2)
