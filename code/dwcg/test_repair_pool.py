import copy,sys,time,unittest
from unittest.mock import patch
from pathlib import Path
from common import empty_pool,make_column
from repair_pool import repair,generate_columns,profit_aware_seed,joint_repair,violations
from bp_solution import verify_integer_assignments
from test_node_cg import small
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'docs/branch_and_price'))
from independent_bp_verify import integer_witness
from node_state import NumericPolicy
from dataclasses import asdict


class RepairTests(unittest.TestCase):
    def test_duplicate_repair_and_source_immutable(self):
        d=small();l=d['lines'][0];l['required_tasks']=['a']
        pool={('L',s):[make_column(l,s,[('a','H')])] for s in (1,2)};before=copy.deepcopy(pool)
        r,new=repair(d,pool,time_limit=10,joint=False)
        self.assertEqual(pool,before);self.assertIsNotNone(r['witness'])
        self.assertGreater(r['final_columns'],r['initial_columns'])
        integer_witness(d,[],r['witness'],asdict(NumericPolicy()))
        self.assertFalse(r['global_integer_optimal_proven'])

    def test_missing_predecessor_and_profit_seed(self):
        d=small();l=d['lines'][0];l['required_tasks']=['b'];l['precedence']=[['a','b']]
        pool=empty_pool(d);pool['L',2]=[make_column(l,2,[('b','R')])]
        seed=profit_aware_seed(d,pool,time.perf_counter()+5)
        self.assertTrue(seed['minimum_violation_proven']);self.assertEqual(seed['violation_total'],1)
        r,new=repair(d,pool,time_limit=10,joint=False)
        self.assertIsNotNone(r['witness']);self.assertFalse(violations(d,r['witness']['stations']))
        self.assertTrue(any(('a','H') in c.assignments or ('a','R') in c.assignments for cs in new.values() for c in cs))

    def test_joint_repair_and_nonempty_fixed_station(self):
        d=small();l=d['lines'][0];l['required_tasks']=['a','b']
        seed=dict(assignments=[dict(line='L',station=1,assignments=[('a','H')]),dict(line='L',station=2,assignments=[])],
                  violations=[dict(row=['task','L','b'])])
        w=joint_repair(d,seed,time.perf_counter()+5,max_stations=1)['witness']
        self.assertIsNotNone(w);self.assertEqual(w['stations'][1]['assignments'],[])
        verify_integer_assignments(d,w['stations'],expected=w['objective'])

    def test_cap_dedup_and_all_local_constraints(self):
        d=small();pool=empty_pool(d);l=d['lines'][0]
        seed=dict(assignments=[dict(line='L',station=s,assignments=[('a','H'),('b','R')]) for s in (1,2)])
        added=generate_columns(d,pool,seed,limit=2)
        self.assertLessEqual(len(added),2)
        for (li,s),cs in pool.items():
            self.assertEqual(len(cs),len({c.assignments for c in cs}))
            for c in cs:self.assertEqual(c,make_column(l,s,c.assignments))

    def test_infeasible_original_and_expired_budget_no_false_claim(self):
        d=small();d['lines'][0]['required_tasks']=['a'];d['lines'][0]['tasks'][0]['modes']={'H':dict(time=9,cost=1,beta=.1)}
        r,_=repair(d,empty_pool(d),time_limit=2,joint=False,rounds=1)
        self.assertIsNone(r['witness']);self.assertFalse(r['global_integer_optimal_proven'])

    def test_verified_incumbent_survives_unproven_improvement(self):
        d=small();l=d['lines'][0];l['required_tasks']=['a']
        pool=empty_pool(d);pool['L',1].append(make_column(l,1,[('a','R')]))
        with patch('repair_pool.joint_repair',return_value=dict(solver_result={'status':'time_limit'},witness=None)):
            r,_=repair(d,pool,time_limit=5,rounds=1)
        self.assertIsNotNone(r['witness'])
        verify_integer_assignments(d,r['witness']['stations'],expected=r['integer_lower_bound'])
        r,_=repair(small(),empty_pool(small()),time_limit=1e-12)
        self.assertIsNone(r['witness']);self.assertFalse(r['global_integer_optimal_proven'])

if __name__=='__main__':unittest.main()
