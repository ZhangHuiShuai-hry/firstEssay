import json,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
from generate_instances import generate
from hybrid import run,columns_from_solution
from solver_backend import BackendConfig,use_backend
from verify import cross_validate

class HybridTest(unittest.TestCase):
    def test_no_mip_incumbent(self):
        data,_=generate(n=3,lines=1,seed=11)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'input.json';p.write_text(json.dumps(data))
            with patch('hybrid.arm',return_value={'status':'time_limit','incumbent':None,'best_bound':None}):
                result=run(p,Path(temp)/'out',30,1)
            self.assertIsNone(result['integer_lower_bound']);self.assertEqual(result['initial_columns'],0)
            self.assertTrue(result['cg']['converged']);self.assertIsNotNone(result['upper_bound'])
    def test_small_enumeration(self):
        for n in (3,6,10):
            with self.subTest(tasks=n),tempfile.TemporaryDirectory() as temp:
                data,_=generate(n=n,lines=1,seed=11,mode_profile='sparse');p=Path(temp)/'input.json';p.write_text(json.dumps(data))
                result=run(p,Path(temp)/'out',60,5)
                self.assertTrue(result['cg']['converged']);self.assertIsNotNone(result['integer_lower_bound'])
                with use_backend(BackendConfig(name='cplex_py',threads=1,seed=11)):
                    checked=cross_validate(data,result['cg']['cg'],enumeration_limit=2000000)
                self.assertTrue(checked['passed'],checked)
                self.assertLessEqual(result['integer_lower_bound'],result['upper_bound']+1e-5)
    def test_reject_duplicate(self):
        data,_=generate(n=3,lines=1,seed=11)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'input.json';p.write_text(json.dumps(data));r=run(p,Path(temp)/'out',30,5)
            s=r['mip']['solution'];st=next(st for st in s['lines'][0]['stations'] if st['assignments_in_order']);st['assignments_in_order'].append(st['assignments_in_order'][0])
            with self.assertRaises((ValueError,AssertionError)):columns_from_solution(data,s)

if __name__=='__main__':unittest.main(verbosity=2)
