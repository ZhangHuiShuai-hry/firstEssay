import copy,json,sys,tempfile,unittest
from pathlib import Path
from incremental_evidence import materialize
from task03 import run
from evidence_store import EvidenceStore
from search_checkpoint import resume_search
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'docs/branch_and_price/task03'))
from task03_verify import oracle,verify_tree

class CheckpointContract(unittest.TestCase):
    def test_full_resume_explicitly_not_implemented(self):
        with self.assertRaises(NotImplementedError):resume_search({'checkpoint_kind':'safe_initial_frontier'})
    def test_missing_station_and_stale_dual_rejected(self):
        d=dict(oracle.cases())['two_lines'];r=materialize(run(d,'V2',solver='cplex_py',time_limit=30,incremental_evidence=True))
        for kind in ('station','dual'):
            bad=copy.deepcopy(r);rnd=next(x for x in bad['node_history'][0]['certificate']['rounds'] if x['complete_pricing'])
            if kind=='station':rnd['pricing'].pop()
            else:rnd['duals'][0]['value']+=123
            with self.assertRaises(Exception):verify_tree(d,bad,solve_oracles=False)
    def test_prefix_mutation_rejected(self):
        from common import empty_pool
        from incremental_evidence import ColumnLedger
        d=dict(oracle.cases())['two_lines'];p=empty_pool(d);ledger=ColumnLedger();ledger.capture(p)
        p[next(iter(p))]=[]
        with self.assertRaises(ValueError):ledger.capture(p)
