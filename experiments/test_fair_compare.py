"""CBC/CPLEX-independent formulas plus actual small CPLEX paired-arm tests."""
from pathlib import Path
import sys
import tempfile
import unittest

from fair_compare import arm,relative_gap
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code/dwcg'))
from common import enumerate_pool,reduced_cost
from test_dwcg import tiny
from verify import cross_validate


class FairComparisonTests(unittest.TestCase):
    def test_equal_budget_small_model_and_saved_bound_certificates(self):
        data=tiny();config=dict(equal_budget_seconds=3,root_fraction=.73,max_iterations=100,solver_seed=11)
        with tempfile.TemporaryDirectory() as tmp:
            ip=arm(data,config,'compact_ip',Path(tmp)/'ip')
            cg=arm(data,config,'cg_pipeline',Path(tmp)/'cg')
        self.assertEqual(ip['incumbent'],cg['incumbent'])
        self.assertTrue(ip['optimal']);self.assertFalse(cg['optimal'])
        self.assertTrue(cg['root_converged'])
        self.assertTrue(cross_validate(data,cg['cg'])['passed'])
        columns=enumerate_pool(data)
        for record in cg['completed_pricing_rounds']:
            duals={tuple(d['row']):d['value'] for d in record['duals']}
            maxima=[]
            for line in data['lines']:
                for s in range(1,len(line['stations'])+1):
                    rho=max(reduced_cost(line,s,c,duals,record['phase']) for c in columns[line['id'],s])
                    maxima.append(rho)
            self.assertAlmostEqual(record['upper_bound'],record['objective']+sum(max(0,rho) for rho in maxima))

    def test_interrupted_root_retains_pool_but_never_claims_optimality(self):
        config=dict(equal_budget_seconds=3,root_fraction=1e-7,max_iterations=100)
        with tempfile.TemporaryDirectory() as tmp:
            result=arm(tiny(),config,'cg_pipeline',Path(tmp))
        self.assertEqual(result['root_status'],'time_limit')
        self.assertFalse(result['root_converged']);self.assertFalse(result['optimal'])
        self.assertTrue(result['generated_pool'])
        self.assertEqual(result['incumbent'],0)
        self.assertIsNone(result['best_bound'])

    def test_gap_with_missing_incumbent_or_bound(self):
        self.assertIsNone(relative_gap(10,None));self.assertIsNone(relative_gap(None,5))
        self.assertAlmostEqual(relative_gap(11,10),.1)


if __name__=='__main__':unittest.main()
