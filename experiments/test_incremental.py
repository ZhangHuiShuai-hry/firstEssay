import json
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code/dwcg'))
from common import enumerate_pool,empty_pool,reduced_cost
from master import build_master,solve_master
from incremental_master import IncrementalMaster
from solver_backend import BackendConfig,use_backend
from compare_incremental import execute
from verify import cross_validate
from test_dwcg import tiny
import solve as cg


class IncrementalTests(unittest.TestCase):
    def native_cg(self,data,**kwargs):
        native=IncrementalMaster(data)
        try:
            with use_backend(BackendConfig(name='cplex_py')):
                with patch.object(cg,'build_master',side_effect=lambda d,pool,phase:native.sync(pool,phase)),patch.object(cg,'solve_master',side_effect=lambda m,**kw:m.solve()):
                    result,_=cg.run_cg(data,recover=False,**kwargs)
                report=cross_validate(data,result)
            return result,report
        finally:native.close()

    def test_fixed_pool_matrix_phase_switch_and_duals(self):
        data=json.loads((ROOT/'code/milp/examples/two_lines.json').read_text());pool=enumerate_pool(data)
        native=IncrementalMaster(data)
        with use_backend(BackendConfig(name='cplex_py')):
            for phase in (1,2):
                native.sync(pool,phase).solve()
                rebuilt=solve_master(build_master(data,pool,phase))
                self.assertAlmostEqual(native.value(),rebuilt.value(),places=5)
                for row,index in native.row_indices.items():
                    self.assertEqual(native.native.linear_constraints.get_rhs(index),-rebuilt.rows[row].constant)
                    self.assertEqual(native.native.linear_constraints.get_senses(index),'E' if rebuilt.rows[row].sense==0 else 'L')
                for key,variable in native.variables.items():
                    for row,index in native.row_indices.items():
                        self.assertEqual(native.native.linear_constraints.get_coefficients(index,variable.index),rebuilt.rows[row].get(rebuilt.variables[key],0))
                    self.assertAlmostEqual(native.native.objective.get_linear(variable.index),rebuilt.objective.get(rebuilt.variables[key],0))
                    line=next(l for l in data['lines'] if l['id']==key[0]);col=pool[key[0],key[1]][key[2]]
                    self.assertAlmostEqual(variable.dj,reduced_cost(line,key[1],col,native.duals(),phase),places=5)
                if phase==2:
                    self.assertTrue(all(native.native.variables.get_upper_bounds(a.index)==0 for a in native.artificials))
        native.close()

    def test_actual_append_and_small_CG_certificates(self):
        data=json.loads((ROOT/'code/milp/examples/single_line.json').read_text());all_pool=enumerate_pool(data);pool=empty_pool(data)
        native=IncrementalMaster(data);identity=id(native.native)
        native.sync(pool,1).solve()
        count=native.native.variables.get_num()
        for key in pool:pool[key].extend(c for c in all_pool[key] if c.assignments)
        native.sync(pool,1).solve()
        self.assertEqual(identity,id(native.native));self.assertGreater(native.native.variables.get_num(),count)
        native.close()
        for name in ('single_line','two_lines'):
            with tempfile.TemporaryDirectory() as tmp:
                task=dict(input=str(ROOT/'code/milp/examples'/f'{name}.json'),version='V1',budget=15,
                          logs=tmp,output=str(Path(tmp)/'result.json'),entry=dict(instance_id=name,factor=3,seed=0))
                result=execute(task)
                with use_backend(BackendConfig(name='cplex_py')):self.assertTrue(cross_validate(json.loads(Path(task['input']).read_text()),result['cg'])['passed'])

    def test_phase_I_infeasible_and_uncertain(self):
        data=tiny();data['lines'][0]['required_tasks']=['a']
        result,report=self.native_cg(data,epsilon=2)
        self.assertEqual(result['status'],'phase_I_numerically_inconclusive')
        self.assertTrue(report['model_consistency_passed']);self.assertFalse(report['cg_verified']);self.assertFalse(report['passed'])
        data.update(human_limit=0,robot_limit=0)
        result,report=self.native_cg(data)
        self.assertEqual(result['status'],'infeasible_full_column_LP')
        self.assertTrue(report['phase_I_infeasibility_certificate_verified']);self.assertTrue(report['passed'])

    def test_iteration_limit_and_zero_objective(self):
        result,report=self.native_cg(tiny(),max_iterations=1)
        self.assertEqual(result['status'],'iteration_limit');self.assertFalse(report['passed'])
        data=tiny();line=data['lines'][0];line['tasks'][0]['value']=0
        for params in line['tasks'][0]['modes'].values():params['cost']=0
        line['stations'][0]=dict(fixed_cost=0,human_cost=0,robot_cost=0)
        result,report=self.native_cg(data)
        self.assertEqual(result['lp_objective'],0);self.assertTrue(report['passed'])

    def test_LP_feasible_integer_infeasible(self):
        data=tiny();data['lines'][0]['required_tasks']=['a']
        second=copy.deepcopy(data['lines'][0]);second.update(id='L2',required_tasks=[],min_recovery=1)
        second['tasks'][0].update(weight=2,modes={'J':dict(time=2,cost=0,beta=.1)})
        data['lines'].append(second)
        result,report=self.native_cg(data)
        self.assertTrue(result['lp_converged']);self.assertFalse(report['full_ip_feasible'])
        self.assertTrue(report['termination_certificate_verified']);self.assertTrue(report['passed'])


if __name__=='__main__':unittest.main()
