"""Actual CPLEX tests: native pricing versus independent enumeration and V1."""
import copy
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
import pulp
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code/dwcg'))
from persistent_pricing import PersistentPricing
from pricing import price
from common import enumerate_pool,empty_pool,reduced_cost
from master import build_master
from solver_backend import BackendConfig,use_backend
from test_dwcg import tiny
from verify import cross_validate
from incremental_master import IncrementalMaster
import solve as cg
from compare_pricing import execute


class PersistentPricingTests(unittest.TestCase):
    def test_matrix_bounds_and_objective_match_immutable_pricing(self):
        data=json.loads((ROOT/'code/milp/examples/two_lines.json').read_text());line=data['lines'][0]
        keys=build_master(data,empty_pool(data),1).rows;duals={k:.3 for k in keys};saved=[]
        actual_solve=pulp.LpProblem.solve
        def capture(problem,*args,**kw):
            saved.append(problem);return actual_solve(problem,*args,**kw)
        native=PersistentPricing(line,1)
        try:
            for phase in (1,2):
                with use_backend(BackendConfig(name='cplex_py')),patch.object(pulp.LpProblem,'solve',new=capture):price(line,1,duals,phase)
                native.solve(duals,phase);problem=saved[-1];names=native.native.variables.get_names()
                for j,name in enumerate(names):
                    v=next(v for v in problem.variables() if v.name==name)
                    self.assertEqual(v.lowBound,native.native.variables.get_lower_bounds(j));self.assertEqual(v.upBound,native.native.variables.get_upper_bounds(j))
                    self.assertAlmostEqual(problem.objective.get(v,0),native.native.objective.get_linear(j))
                self.assertAlmostEqual(problem.objective.constant,native.objective_constant)
                self.assertEqual(native.native.objective.get_offset(),0.)
                self.assertTrue(all(t=='I' for t in native.native.variables.get_types()))
                for i,row in enumerate(problem.constraints.values()):
                    self.assertEqual(-row.constant,native.native.linear_constraints.get_rhs(i))
                    self.assertEqual(native.native.linear_constraints.get_senses(i),'L')
                    for j,name in enumerate(names):
                        v=next(v for v in problem.variables() if v.name==name)
                        self.assertEqual(row.get(v,0),native.native.linear_constraints.get_coefficients(i,j))
        finally:native.close()

    def test_random_duals_both_phases_against_V1_and_enumeration(self):
        data=json.loads((ROOT/'code/milp/examples/two_lines.json').read_text());pool=enumerate_pool(data)
        keys=build_master(data,empty_pool(data),1).rows;rng=random.Random(271)
        with use_backend(BackendConfig(name='cplex_py')):
            for line in data['lines']:
                for station in range(1,len(line['stations'])+1):
                    native=PersistentPricing(line,station);identity=id(native.native)
                    for phase in (1,2,1,2):
                        for trial in range(4):
                            dual={k:rng.uniform(0,4) for k in keys}
                            for k in keys:
                                if k[0] in ('station','task'):dual[k]=rng.uniform(-4,4)
                            a,rc=native.solve(dual,phase);b,old=price(line,station,dual,phase)
                            expected=max(reduced_cost(line,station,c,dual,phase) for c in pool[line['id'],station])
                            self.assertAlmostEqual(rc,old,places=5);self.assertAlmostEqual(rc,expected,places=5)
                            self.assertEqual(identity,id(native.native));self.assertEqual(native.records[-1]['native_status'],101)
                    native.close()

    def native_cg(self,data,**kwargs):
        master=IncrementalMaster(data);models={}
        def pp(line,s,duals,phase,verbose):
            key=line['id'],s
            if key not in models:models[key]=PersistentPricing(line,s)
            return models[key].solve(duals,phase)
        try:
            with use_backend(BackendConfig(name='cplex_py')):
                with patch.object(cg,'build_master',side_effect=lambda d,p,phase:master.sync(p,phase)),patch.object(cg,'solve_master',side_effect=lambda m,**kw:m.solve()),patch.object(cg,'price',side_effect=pp):
                    result,_=cg.run_cg(data,recover=False,**kwargs)
                report=cross_validate(data,result)
            return result,report
        finally:
            master.close()
            for model in models.values():model.close()

    def test_reference_full_column_certificates(self):
        for name in ('single_line','two_lines'):
            data=json.loads((ROOT/'code/milp/examples'/f'{name}.json').read_text())
            result,report=self.native_cg(data);self.assertTrue(report['passed']);self.assertTrue(report['termination_certificate_verified'])

    def test_boundaries_and_zero_objective(self):
        data=tiny();result,report=self.native_cg(data,max_iterations=1)
        self.assertEqual(result['status'],'iteration_limit');self.assertFalse(report['passed'])
        data['lines'][0]['required_tasks']=['a']
        result,report=self.native_cg(data,epsilon=2)
        self.assertEqual(result['status'],'phase_I_numerically_inconclusive');self.assertFalse(report['passed'])
        data.update(human_limit=0,robot_limit=0);result,report=self.native_cg(data)
        self.assertEqual(result['status'],'infeasible_full_column_LP');self.assertTrue(report['passed'])
        data=tiny();line=data['lines'][0];line['tasks'][0]['value']=0
        for p in line['tasks'][0]['modes'].values():p['cost']=0
        line['stations'][0]=dict(fixed_cost=0,human_cost=0,robot_cost=0)
        result,report=self.native_cg(data);self.assertEqual(result['lp_objective'],0);self.assertTrue(report['passed'])

    def test_LP_feasible_integer_infeasible(self):
        data=tiny();data['lines'][0]['required_tasks']=['a'];second=copy.deepcopy(data['lines'][0])
        second.update(id='L2',required_tasks=[],min_recovery=1);second['tasks'][0].update(weight=2,modes={'J':dict(time=2,cost=0,beta=.1)})
        data['lines'].append(second);result,report=self.native_cg(data)
        self.assertTrue(result['lp_converged']);self.assertFalse(report['full_ip_feasible']);self.assertTrue(report['passed'])

    def test_deadline_never_returns_unproven_price(self):
        import time
        data=tiny();line=data['lines'][0];duals={k:0. for k in build_master(data,empty_pool(data),1).rows}
        native=PersistentPricing(line,1)
        try:
            with self.assertRaises(TimeoutError):native.solve(duals,2,deadline=time.perf_counter()-1)
            self.assertFalse(native.records[-1]['optimal']);self.assertEqual(native.records[-1]['status'],'time_limit')
        finally:native.close()

    def test_zero_fatigue_and_overlong_tasks(self):
        for overlong in (False,True):
            data=tiny();line=data['lines'][0];line['fatigue_limit']=0
            if overlong:
                for p in line['tasks'][0]['modes'].values():p['time']=4
            pool=enumerate_pool(data);duals={k:0. for k in build_master(data,empty_pool(data),1).rows}
            native=PersistentPricing(line,1)
            try:
                col,rc=native.solve(duals,2)
                self.assertAlmostEqual(rc,max(reduced_cost(line,1,c,duals,2) for c in pool['L',1]))
                if overlong:self.assertFalse(col.assignments)
                else:self.assertEqual(col.assignments,(('a','R'),))
            finally:native.close()

    def test_runner_versions_and_nonoverlapping_timers(self):
        for version in ('V1','V2'):
            with tempfile.TemporaryDirectory() as tmp:
                task=dict(version=version,input=str(ROOT/'code/milp/examples/two_lines.json'),budget=20,logs=tmp,
                          output=str(Path(tmp)/'result.json'),entry=dict(instance_id='two_lines',factor=3,seed=0))
                result=execute(task);self.assertTrue(result['converged'])
                self.assertGreaterEqual(result['other_time'],-1e-6)
                self.assertTrue(all(p['other_time']>=-1e-6 for p in result['pricing_log']))
                with use_backend(BackendConfig(name='cplex_py')):self.assertTrue(cross_validate(json.loads(Path(task['input']).read_text()),result['cg'])['passed'])


if __name__=='__main__':unittest.main()
