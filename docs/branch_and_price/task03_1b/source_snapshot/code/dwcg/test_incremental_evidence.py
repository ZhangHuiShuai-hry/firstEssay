import json,tempfile,unittest,sys
from pathlib import Path
from common import empty_pool,make_column
from incremental_evidence import ColumnLedger,materialize
from evidence_store import EvidenceStore,canonical
from task03 import run
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'docs/branch_and_price/task03'))
from task03_verify import oracle,verify_tree
from solver_backend import BackendConfig,use_backend

class IncrementalTests(unittest.TestCase):
    def test_prefix_and_rollback(self):
        d=dict(oracle.cases())['two_lines'];pool=empty_pool(d);ledger=ColumnLedger();a=ledger.capture(pool)
        line=d['lines'][0];key=(line['id'],1)
        task=line['tasks'][0];pool[key].append(make_column(line,1,[(task['id'],next(iter(task['modes'])))]));b=ledger.capture(pool)
        self.assertNotEqual(materialize(a),materialize(b))
        with tempfile.TemporaryDirectory() as td:
            s=EvidenceStore(Path(td)/'x.sqlite')
            with self.assertRaises(ValueError):s.put({'view':b,'zz':float('nan')})
            s.put({'a':a,'b':b});self.assertEqual(canonical(s.get()),canonical(materialize({'a':a,'b':b})));s.close()
    def test_live_oracle(self):
        for name in ('two_lines','generator_n6_L1_s13','lp_yes_ip_no'):
            data=dict(oracle.cases())[name]
            for version in ('V0','V1','V2','V3'):
                with tempfile.TemporaryDirectory() as td:
                    s=EvidenceStore(Path(td)/'x.sqlite');r=run(data,version,solver='cplex_py',time_limit=30,incremental_evidence=True,evidence_sink=s)
                    s.put(r);out=s.get();s.close();self.assertEqual(canonical(out),canonical(materialize(r)))
                    with use_backend(BackendConfig(name='cplex_py')):self.assertTrue(verify_tree(data,out,solve_oracles=True)['passed'])
