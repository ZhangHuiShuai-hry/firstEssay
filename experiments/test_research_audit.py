"""Regressions for confirmed Task01 bound and certificate defects."""
import json
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code/dwcg'),str(ROOT/'code')]
import pulp
from solver_backend import BackendConfig,make_solver,use_backend
import solve as cg
from test_dwcg import tiny


class ResearchAuditTests(unittest.TestCase):
    def test_best_bound_includes_objective_constant(self):
        for backend in ('cbc','cplex_py'):
            for constant in (-7.,7.):
                with self.subTest(backend=backend,constant=constant):
                    p=pulp.LpProblem('offset',pulp.LpMaximize);x=pulp.LpVariable('x',cat='Binary')
                    p+=3*x+constant;p+=x<=1
                    with use_backend(BackendConfig(name=backend)):p.solve(make_solver())
                    self.assertTrue(p.backend_result['optimal'])
                    self.assertAlmostEqual(p.backend_result['objective'],3+constant)
                    self.assertAlmostEqual(p.backend_result['best_bound'],3+constant)

    def test_cbc_printed_bound_rounds_outwards(self):
        from solver_backend import cbc_max_bound
        self.assertAlmostEqual(cbc_max_bound('Upper bound: 1.234\n',7),8.2345)
        self.assertAlmostEqual(cbc_max_bound('Upper bound: -1.234\n',-7),-8.2335)
        self.assertIsNone(cbc_max_bound('no bound',0))

    def test_complete_round_certificate_and_integer_scope(self):
        result,pool=cg.run_cg(tiny())
        self.assertEqual(result['certificate_status'],'lp_optimal_proven')
        for record in result['history']:
            if record['phase']!=2:continue
            self.assertTrue(record['complete_pricing']);self.assertEqual(record['rmp_status'],'optimal')
            self.assertIn('rmp_solution',record)
            for pp in record['pricing']:
                self.assertTrue(pp['optimal']);self.assertIn('best_bound',pp);self.assertGreaterEqual(pp['solve_seconds'],0)
        self.assertTrue(result['integer_recovery']['restricted_master_optimal'])
        self.assertFalse(result['integer_recovery']['original_integer_optimal_proven'])

    def test_failure_retains_partial_certificate(self):
        with patch.object(cg,'price',side_effect=TimeoutError('test interrupted pricing')):
            with self.assertRaises(TimeoutError) as caught:cg.run_cg(tiny())
        result=caught.exception.cg_result
        self.assertEqual(result['certificate_status'],'pricing_time_limit')
        self.assertFalse(result['lp_converged']);self.assertIsNone(result['lp_upper_bound'])
        self.assertFalse(result['history'][-1]['complete_pricing'])
        self.assertEqual(result['history'][-1]['pricing'][0]['status'],'time_limit')
        json.dumps(result,allow_nan=False)

    def test_unproven_solver_status_and_error_distinct(self):
        error=RuntimeError('unproven');error.solver_result={'status':'feasible_unproven','optimal':False,'objective':0,'best_bound':5}
        with patch.object(cg,'price',side_effect=error):
            with self.assertRaises(RuntimeError) as caught:cg.run_cg(tiny())
        self.assertEqual(caught.exception.cg_result['certificate_status'],'lp_feasible_unproven')
        with patch.object(cg,'price',side_effect=pulp.PulpSolverError('test solver exception')):
            with self.assertRaises(pulp.PulpSolverError) as caught:cg.run_cg(tiny())
        self.assertEqual(caught.exception.cg_result['certificate_status'],'solver_error')

    def test_legacy_verifier_and_tampered_proof_metadata(self):
        import copy
        from verify_checked import cross_validate
        result,_=cg.run_cg(tiny())
        missing=copy.deepcopy(result);missing.pop('final_duals')
        self.assertFalse(cross_validate(tiny(),missing)['passed'])
        for field,value in (('complete_pricing',False),('rmp_status','time_limit')):
            bad=copy.deepcopy(result);bad['history'][-1][field]=value
            with self.assertRaises(RuntimeError):cross_validate(tiny(),bad)
        bad=copy.deepcopy(result);bad['history'][-1]['pricing'][0]['optimal']=False
        with self.assertRaises(RuntimeError):cross_validate(tiny(),bad)

    def test_metadata_rejects_unproven_pair_and_native_exception(self):
        from common import PricingResult,empty_pool
        col=empty_pool(tiny())['L',1][0]
        answer=PricingResult(col,0.,{'optimal':False,'status':'time_limit'})
        with patch.object(cg,'price',return_value=answer):
            with self.assertRaises(RuntimeError) as caught:cg.run_cg(tiny())
        self.assertEqual(caught.exception.cg_result['certificate_status'],'pricing_time_limit')
        with patch.object(cg,'price',side_effect=Exception('native API failure')):
            with self.assertRaises(Exception) as caught:cg.run_cg(tiny())
        self.assertEqual(caught.exception.cg_result['certificate_status'],'solver_error')

    def test_recovery_exception_preserves_lp_proof(self):
        with patch.object(cg,'recover_integer',side_effect=RuntimeError('recovery failed')):
            with self.assertRaises(RuntimeError) as caught:cg.run_cg(tiny())
        result=caught.exception.cg_result
        self.assertTrue(result['lp_converged'])
        self.assertEqual(result['certificate_status'],'lp_optimal_proven')
        self.assertFalse(result['integer_recovery']['original_integer_optimal_proven'])


if __name__=='__main__':unittest.main()
