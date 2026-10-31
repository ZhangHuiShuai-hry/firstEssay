"""Experimental integrity tests: paired generation, statuses and unchanged models."""
import copy
import math
from pathlib import Path
import random
import sys
import unittest

from generate_instances import generate, digest, metadata
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
import pulp
from solver_backend import BackendConfig,make_solver,use_backend


class FrameworkTests(unittest.TestCase):
    def test_existing_run_directory_is_never_overwritten(self):
        import tempfile
        from run_experiments import run
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileExistsError):
                run(ROOT/'experiments/configs/stage_a.json',Path(temp))

    def test_all_planned_sizes_have_valid_constructive_witnesses(self):
        for seed in (11,21,31,41,51):
            for n in (10,20,30,40,50):
                data,meta=generate(n=n,lines=2,seed=seed)
                self.assertEqual({l['cycle_time'] for l in data['lines']},{15})
                self.assertEqual(metadata(data)['total_tasks'],2*n)

    def test_deterministic_generator_and_fixed_total_task_multiset(self):
        a,ma=generate(seed=11,n=10,lines=2)
        b,mb=generate(seed=11,n=10,lines=2)
        self.assertEqual(digest(a),digest(b))
        banks=[]
        for l in (1,2,3,5):
            data,meta=generate(lines=l,total_tasks=60,total_stations=20,seed=11)
            self.assertEqual(metadata(data)['total_tasks'],60)
            self.assertEqual(metadata(data)['total_stations'],20)
            banks.append(meta['base_task_parameter_hash'])
        self.assertEqual(len(set(banks)),1)

    def test_fatigue_and_resource_pairs_change_only_intended_fields(self):
        from generate_instances import write_suite
        import json,tempfile
        with tempfile.TemporaryDirectory() as temp:
            destination=Path(temp)/'cases'
            config=dict(design='pilot',seeds=[11],sizes=[],line_counts=[],base_n=6,
                        fatigue_levels=[.4,.6,.8])
            manifest=write_suite(config,destination)
            pairs={}
            for entry in manifest:
                data=json.loads((destination/entry['instance']).read_text())
                if entry['group']=='B3':
                    for line in data['lines']:line.pop('fatigue_limit')
                else:data.pop('human_limit');data.pop('robot_limit')
                pairs.setdefault(entry['group'],set()).add(digest(data))
            self.assertEqual(len(pairs['B3']),1);self.assertEqual(len(pairs['B4']),1)

    def test_native_timeout_is_never_optimal_or_infeasible(self):
        rng=random.Random(5)
        for backend in ('cplex_py','cbc'):
            p=pulp.LpProblem('timeout_test',pulp.LpMaximize)
            x=[pulp.LpVariable(f'x{i}',cat='Binary') for i in range(150)]
            p+=pulp.lpSum(rng.randint(1,30)*v for v in x)
            for k in range(60):p+=pulp.lpSum(rng.randint(1,20)*v for v in x)<=400
            with use_backend(BackendConfig(name=backend)):
                p.solve(make_solver(role='compact_ip',time_limit=1e-6))
            with self.subTest(backend=backend):
                self.assertFalse(p.backend_result['optimal'])
                self.assertNotEqual(p.backend_result['status'],'infeasible')
                self.assertNotEqual(p.sol_status,pulp.LpSolutionOptimal)


if __name__=='__main__':unittest.main()
