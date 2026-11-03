import copy
from dataclasses import asdict
import json
from pathlib import Path
import sys,tempfile,time,unittest
from root_diagnostics import run_root,inject_witness,restricted_recovery
from common import empty_pool
from node_state import NumericPolicy
from solver_backend import BackendConfig,use_backend
from evidence_store import EvidenceStore
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'docs/branch_and_price'))
from independent_bp_verify import oracle,verify_node,integer_witness,CertificateRejected


class RootDiagnosticsTests(unittest.TestCase):
    def test_node_oracle_replay_all_modes_and_infeasible_integer(self):
        for name in ('single_line','two_lines','generator_n6_L1_s13','lp_yes_ip_no'):
            data=dict(oracle.cases())[name];complete=oracle.enumerate_patterns(data)
            for mode in ('baseline','seed','recover'):
                with self.subTest(name=name,mode=mode),tempfile.TemporaryDirectory() as tmp:
                    store=EvidenceStore(Path(tmp)/'evidence.sqlite')
                    try:
                        r=run_root(data,mode=mode,time_limit=20,initial_seconds=.5,
                                   recovery_every=2,store=store)
                        saved=store.get()
                    finally:store.close()
                    with use_backend(BackendConfig(name='cplex_py')):
                        verified=verify_node(data,saved['node'],complete,asdict(NumericPolicy()))
                    self.assertAlmostEqual(verified['full_lp']['objective'],r['node']['node_result']['lp_objective'],places=5)
                    if r['integer_incumbent_solution']:
                        integer_witness(data,[],r['integer_incumbent_solution'],asdict(NumericPolicy()))
                    if name=='lp_yes_ip_no':
                        self.assertIsNone(r['global_lower_bound']);self.assertFalse(r['global_integer_optimal_proven'])
                    else:self.assertLessEqual(r['global_lower_bound'],r['global_upper_bound']+1e-5)

    def test_seed_real_RMP_immediately_feasible_and_isolated(self):
        data=json.loads((ROOT/'code/data/tasks005_lines02_each03-02.json').read_text())
        r=run_root(data,time_limit=10,initial_seconds=.5)
        witness=r['integer_incumbent_solution'];before=copy.deepcopy(witness)
        pool,_=inject_witness(data,witness);pool2,_=inject_witness(data,witness)
        pool[next(iter(pool))].clear()
        self.assertTrue(pool2[next(iter(pool2))]);self.assertEqual(witness,before)
        seeded=run_root(data,mode='seed',seed_witness=witness,time_limit=10)
        first=seeded['node']['certificate']['rounds'][0]
        self.assertLessEqual(first['artificial_sum'],1e-7)
        self.assertEqual(sum(x['phase']==1 for x in seeded['round_diagnostics']),1)

    def test_restricted_infeasibility_is_not_global_and_no_acquisition_recovery(self):
        data=dict(oracle.cases())['two_lines']
        attempt=restricted_recovery(data,empty_pool(data),'cplex_py',time.perf_counter()+5)
        self.assertIsNone(attempt['witness']);self.assertEqual(attempt['scope'],'restricted_pool_only')
        r=run_root(data,mode='recover',initial_seconds=0,time_limit=10,recovery_every=1)
        self.assertEqual(r['acquisition']['status'],'time_limit')
        self.assertTrue(any(a['witness'] for a in r['recoveries']))
        self.assertAlmostEqual(r['global_lower_bound'],24)
        self.assertFalse(r['global_integer_optimal_proven'])  # root LP 27 != integer 24

    def test_bad_witness_and_forged_pricing_rejected(self):
        data=dict(oracle.cases())['two_lines'];r=run_root(data,time_limit=10,initial_seconds=.5)
        w=copy.deepcopy(r['integer_incumbent_solution']);w['objective']+=1
        with self.assertRaises(Exception):inject_witness(data,w)
        from incremental_evidence import materialize
        n=materialize(r['node']);last=next(x for x in n['certificate']['rounds'] if x.get('complete_pricing'))
        last['pricing'].pop()
        with self.assertRaises(CertificateRejected):
            verify_node(data,n,oracle.enumerate_patterns(data),asdict(NumericPolicy()),solve_oracles=False)

    def test_tiny_budget_does_not_claim_optimal(self):
        r=run_root(dict(oracle.cases())['two_lines'],time_limit=1e-12,initial_seconds=0)
        self.assertIsNone(r['global_lower_bound']);self.assertFalse(r['global_integer_optimal_proven'])

    def test_new_offline_checker_rejects_false_LB_and_missing_PP(self):
        sys.path.insert(0,str(ROOT/'docs/root_diagnostics'))
        from verify_root import verify
        from incremental_evidence import materialize
        data=dict(oracle.cases())['two_lines']
        r=materialize(run_root(data,mode='recover',time_limit=10,initial_seconds=0,recovery_every=1))
        self.assertTrue(verify(data,r,True)['passed'])
        bad=copy.deepcopy(r);bad['global_lower_bound']+=1
        with self.assertRaises(CertificateRejected):verify(data,bad)
        bad=copy.deepcopy(r)
        next(row for row in bad['node']['certificate']['rounds'] if row.get('complete_pricing'))['pricing'].pop()
        with self.assertRaises(CertificateRejected):verify(data,bad)

if __name__=='__main__':unittest.main()
