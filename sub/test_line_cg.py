"""整线列生成的数学回归、独立枚举与伪造证书拒绝。"""
from copy import deepcopy
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch
import line_cg

from line_cg import run
from compact_solver import run as compact_run
from validate import audit, close, enumerate_all, solve_full
from instances import variant

ROOT=Path(__file__).resolve().parents[1]


class LineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tiny=json.loads((ROOT/'code/data/tasks005_lines02_each03-02.json').read_text(encoding='utf-8-sig'))
        cls.answer=run(cls.tiny,time_limit=20)

    def test_two_lines_four_models_pricing_and_witness(self):
        verified=audit(self.tiny,self.answer)
        self.assertEqual(verified['status'],'PASS')
        direct=compact_run(self.tiny,time_limit=20)
        self.assertTrue(direct['global_integer_optimal_proven'])
        close(direct['global_lower_bound'],self.answer['lower_bound'])
        close(self.answer['lower_bound'],24.)
        self.assertTrue(self.answer['global_integer_optimal_proven'])

    def test_single_line_gap_disappears(self):
        data=json.loads((ROOT/'code/data/tasks006_lines01_each06_seed13.json').read_text(encoding='utf-8-sig'))
        answer=run(data,time_limit=20)
        verified=audit(data,answer)
        self.assertEqual(verified['status'],'PASS')
        close(answer['lower_bound'],56.63)
        self.assertEqual(answer['termination_reason'],'independent_line_optima_are_resource_compatible')

    def test_phase_one_resource_infeasibility(self):
        path=ROOT/'docs/research_audit/evidence/independent_final/lp_yes_ip_no_cplex_py/instance.json'
        data=json.loads(path.read_text(encoding='utf-8-sig'))
        answer=run(data,time_limit=20)
        audit(data,answer)
        self.assertTrue(answer['global_infeasibility_proven'])
        self.assertIn('Phase_I',answer['termination_reason'])
        self.assertFalse(answer['global_integer_optimal_proven'])

    def test_local_empty_domain(self):
        data=deepcopy(self.tiny); data['lines']=data['lines'][:1]
        data['lines'][0]['cycle_time']=.01
        answer=run(data,time_limit=20)
        audit(data,answer)
        self.assertTrue(answer['global_infeasibility_proven'])
        self.assertEqual(answer['termination_reason'],'one_line_integer_domain_empty')

    def test_zero_negative_profit_and_empty_plan(self):
        data=deepcopy(self.tiny); data['lines']=data['lines'][:1]
        line=data['lines'][0]; line['required_tasks']=[]; line['min_recovery']=0
        for t in line['tasks']:
            t['value']=0
        answer=run(data,time_limit=20)
        audit(data,answer)
        close(answer['lower_bound'],0)
        self.assertTrue(answer['global_integer_optimal_proven'])

    def test_timeout_keeps_unproven(self):
        answer=run(self.tiny,time_limit=1e-9)
        audit(self.tiny,answer)
        self.assertEqual(answer['status'],'time_limit')
        self.assertFalse(answer['global_integer_optimal_proven'])
        self.assertFalse(answer['global_infeasibility_proven'])

    def test_forged_column_profit_rejected(self):
        bad=deepcopy(self.answer); bad['pool']['L1'][0]['profit']+=1
        with self.assertRaises(AssertionError): audit(self.tiny,bad,enumerate_pricing=False)

    def test_forged_reduced_cost_rejected(self):
        bad=deepcopy(self.answer)
        record=next(r for r in bad['history'] if r['complete_exact_pricing'])
        record['pricing'][0]['reduced_cost']+=1
        with self.assertRaises(AssertionError): audit(self.tiny,bad)

    def test_missing_pricing_block_rejected(self):
        bad=deepcopy(self.answer)
        record=next(r for r in bad['history'] if r['complete_exact_pricing'])
        record['pricing'].pop()
        with self.assertRaises(AssertionError): audit(self.tiny,bad,enumerate_pricing=False)

    def test_forged_global_bound_rejected(self):
        bad=deepcopy(self.answer); bad['upper_bound']-=1
        with self.assertRaises(AssertionError): audit(self.tiny,bad,enumerate_pricing=False)

    def test_variants_isolated_and_relaxation_relationship(self):
        unchanged=deepcopy(self.tiny)
        for name in ('no_precedence','no_fatigue','resource_ample'):
            transformed=variant(self.tiny,name)
            answer=compact_run(transformed,time_limit=20)
            self.assertTrue(answer['global_integer_optimal_proven'])
            self.assertGreaterEqual(answer['global_lower_bound'],24-1e-5)
        self.assertEqual(unchanged,self.tiny)

    def test_invalid_numeric_limit(self):
        for limit in (0,-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError): run(self.tiny,time_limit=limit)

    def test_initial_native_bounds_are_distinct_from_incumbents(self):
        actual=line_cg.solve_line
        def incomplete(line,**kwargs):
            column,cert=actual(line,**kwargs)
            if kwargs.get('purpose')=='initialization':
                cert['optimal']=False; cert['status']='time_limit'
                cert['solver'].update(optimal=False,status='time_limit',best_bound=column['profit']+2)
            return column,cert
        with patch.object(line_cg,'solve_line',side_effect=incomplete):
            answer=run(self.tiny,time_limit=20)
        self.assertEqual(answer['initial_upper_bound_source'],'sum_native_economic_line_MIP_best_bounds')
        self.assertGreater(answer['initial_independent_upper_bound'],sum(e['column']['profit'] for e in answer['initialization']))
        audit(self.tiny,answer)

    def test_impossible_initial_best_bound_rejected(self):
        actual=line_cg.solve_line
        def invalid(line,**kwargs):
            column,cert=actual(line,**kwargs)
            if kwargs.get('purpose')=='initialization':
                cert['optimal']=False; cert['status']='time_limit'
                cert['solver'].update(optimal=False,status='time_limit',best_bound=column['profit']-1)
            return column,cert
        with patch.object(line_cg,'solve_line',side_effect=invalid):
            answer=run(self.tiny,time_limit=20)
        self.assertEqual(answer['status'],'numerical_uncertain')
        self.assertFalse(answer['global_integer_optimal_proven'])


if __name__=='__main__':
    unittest.main(verbosity=2)
