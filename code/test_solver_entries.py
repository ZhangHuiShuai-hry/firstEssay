"""Small real CPLEX integration checks for the two user-facing entry scripts."""
import hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];CODE=ROOT/'code'
sys.path[:0]=[str(CODE/'dwcg'),str(CODE/'milp'),str(CODE)]
from evidence_store import load_result
from common import compact

class SolverEntries(unittest.TestCase):
    def invoke(self,entry,out,*args):
        r=subprocess.run([sys.executable,str(CODE/entry),*map(str,args),'--output-dir',str(out)],cwd=CODE,
                         text=True,encoding='utf-8',errors='strict',stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                         env=dict(os.environ,PYTHONUTF8='1'),timeout=60)
        return r
    def test_data_manifest(self):
        for item in json.loads((CODE/'data/MANIFEST.json').read_text(encoding='utf-8')):
            raw=(CODE/'data'/item['file']).read_bytes();data=json.loads(raw);compact.validate_data(data)
            self.assertEqual(hashlib.sha256(raw).hexdigest(),item['sha256'])
            self.assertEqual(sum(len(l['tasks']) for l in data['lines']),item['total_tasks'])
    def test_ide_defaults_and_root_cg(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            for script,folder in [('milp/cplex_solver.py','compact'),('dwcg/dwcg_solver.py','bp')]:
                r=self.invoke(script,td/folder);self.assertEqual(r.returncode,0,r.stderr)
                report=json.loads(next((td/folder).glob('*/result.json')).read_text(encoding='utf-8'))
                self.assertEqual(report['global_lower_bound'],24);self.assertTrue(report['global_integer_optimal_proven'])
            r=self.invoke('dwcg/dwcg_solver.py',td/'cg','--strategy','cg');self.assertEqual(r.returncode,0,r.stderr)
            file=next((td/'cg').glob('*/result.json'));report=json.loads(file.read_text(encoding='utf-8'))
            self.assertEqual(report['lp_objective'],27);self.assertFalse(report['global_integer_optimal_proven'])
            from verify import cross_validate
            from solver_backend import BackendConfig,use_backend
            data=json.loads((CODE/'data/tasks005_lines02_each03-02.json').read_text())
            with use_backend(BackendConfig(name='cplex_py')):
                self.assertTrue(cross_validate(data,load_result(file.parent/'certificate.sqlite'))['passed'])
    def test_n6_and_safe_limit(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td);source=CODE/'data/tasks006_lines01_each06_seed13.json'
            for script,folder in [('milp/cplex_solver.py','compact'),('dwcg/dwcg_solver.py','bp')]:
                r=self.invoke(script,td/folder,source);self.assertEqual(r.returncode,0,r.stderr)
                report=json.loads(next((td/folder).glob('*/result.json')).read_text(encoding='utf-8'))
                self.assertAlmostEqual(report['global_lower_bound'],56.63,places=5)
            r=self.invoke('dwcg/dwcg_solver.py',td/'limit','--time-limit','1e-12');self.assertEqual(r.returncode,2,r.stderr)
            report=json.loads(next((td/'limit').glob('*/result.json')).read_text(encoding='utf-8'))
            self.assertFalse(report['global_integer_optimal_proven']);self.assertIsNone(report['global_lower_bound'])

if __name__=='__main__':unittest.main()
