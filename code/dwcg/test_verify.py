"""CBC regressions for verifier verdicts, numeric values and LP bounds."""
import copy
import unittest
from unittest.mock import patch

import pulp

from solve import run_cg
from test_dwcg import tiny
from verify import cross_validate, _objective


class VerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = tiny()
        cls.converged, _ = run_cg(cls.data)

    def test_verified_optimum(self):
        report = cross_validate(self.data, self.converged)
        for field in ("model_consistency_passed", "cg_verified", "passed"):
            self.assertTrue(report[field])
        self.assertEqual(report["verification_status"], "passed")
        self.assertGreater(report["cg_lp_upper_bounds_checked"], 0)

    def test_iteration_limits_and_phase_I_uncertainty_are_inconclusive(self):
        for required in ([], ["a"]):
            data = tiny()
            data["lines"][0]["required_tasks"] = required
            result, _ = run_cg(data, max_iterations=1)
            for status in ("iteration_limit", "phase_I_numerically_inconclusive"):
                # Inject the uncertainty status; do not depend on CBC roundoff.
                if status.startswith("phase_I") and not required:
                    continue
                result["status"] = status
                with self.subTest(required=required, status=status):
                    report = cross_validate(data, result)
                    self.assertTrue(report["model_consistency_passed"])
                    self.assertFalse(report["cg_verified"])
                    self.assertFalse(report["passed"])
                    self.assertEqual(report["verification_status"], "inconclusive")

    def test_true_and_false_infeasibility_claims(self):
        data = tiny()
        data.update(human_limit=0, robot_limit=0)
        data["lines"][0]["required_tasks"] = ["a"]
        result, _ = run_cg(data)
        report = cross_validate(data, result)
        self.assertTrue(report["passed"])
        self.assertTrue(report["cg_infeasibility_checked"])
        self.assertFalse(report["cg_vs_full_lp_checked"])
        wrong = dict(status="infeasible_full_column_LP", lp_converged=False)
        with self.assertRaisesRegex(RuntimeError, "incorrectly declared"):
            cross_validate(self.data, wrong)
        with self.assertRaises(RuntimeError):
            cross_validate(data, self.converged)

    def test_full_lp_infeasible_compact_lp_feasible_is_allowed(self):
        data = tiny()
        line = data["lines"][0]
        line["required_tasks"] = ["a"]
        line["tasks"][0]["modes"] = {"H": dict(time=4, cost=1, beta=0)}
        # The compact relaxation can mix half of a with half of the short task
        # at each station. No local integer column can contain the overlong a.
        line["tasks"].append(dict(id="b", value=1, weight=0,
                                  modes={"H": dict(time=1, cost=0, beta=0)}))
        line["stations"].append(copy.deepcopy(line["stations"][0]))
        result, _ = run_cg(data)
        report = cross_validate(data, result)
        self.assertTrue(report["passed"])
        self.assertFalse(report["full_lp_feasible"])
        self.assertTrue(report["compact_lp_feasible"])

    def test_zero_objective_and_missing_real_variable_value(self):
        data = tiny()
        line = data["lines"][0]
        line["tasks"][0]["value"] = 0
        for params in line["tasks"][0]["modes"].values():
            params["cost"] = 0
        line["stations"][0] = dict(fixed_cost=0, human_cost=0, robot_cost=0)
        result, _ = run_cg(data)
        report = cross_validate(data, result)
        self.assertTrue(report["passed"])
        self.assertEqual(report["compact_lp_objective"], 0)
        problem = pulp.LpProblem("missing_value")
        problem += pulp.LpVariable("unassigned")
        with self.assertRaisesRegex(RuntimeError, "finite number"):
            _objective(problem)

    def test_nonfinite_or_invalid_final_values_are_rejected(self):
        for field in ("lp_objective", "lp_upper_bound"):
            for invalid in (float("nan"), float("inf"), -float("inf"), "7", True):
                result = copy.deepcopy(self.converged)
                result[field] = invalid
                with self.subTest(field=field, invalid=invalid), self.assertRaises(RuntimeError):
                    cross_validate(self.data, result)

    def test_history_finite_values_and_bounds(self):
        for field, value in (("objective", float("nan")), ("lp_upper_bound", float("inf")),
                             ("maximum_reduced_cost", float("nan")),
                             ("objective", 10000), ("lp_upper_bound", -10000)):
            result = copy.deepcopy(self.converged)
            record = next(r for r in result["history"] if r["phase"] == 2)
            record[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(RuntimeError):
                cross_validate(self.data, result)

    def test_truncated_run_bounds_are_checked(self):
        result, _ = run_cg(self.data, max_iterations=1)
        for location in ("final", "history"):
            wrong = copy.deepcopy(result)
            record = wrong if location == "final" else next(r for r in wrong["history"] if r["phase"] == 2)
            record["lp_upper_bound"] = -100
            with self.subTest(location=location), self.assertRaises(RuntimeError):
                cross_validate(self.data, wrong)

    def test_convergence_requires_matching_status_objective_and_bound(self):
        for field, value in (("status", "iteration_limit"), ("lp_converged", False),
                             ("lp_converged", "true"), ("lp_objective", None),
                             ("lp_objective", -100), ("lp_upper_bound", None)):
            result = copy.deepcopy(self.converged)
            result[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(RuntimeError):
                cross_validate(self.data, result)

    def test_lp_bounds_checked_with_infeasible_integer_models(self):
        data = tiny()
        data["lines"][0]["required_tasks"] = ["a"]
        second = copy.deepcopy(data["lines"][0])
        second.update(id="L2", required_tasks=[], min_recovery=1)
        second["tasks"][0].update(weight=2, modes={"J": dict(time=2, cost=0, beta=0.1)})
        data["lines"].append(second)
        result, _ = run_cg(data)
        report = cross_validate(data, result)
        self.assertFalse(report["full_ip_feasible"])
        self.assertTrue(report["lp_relaxation_bound_checked"])
        self.assertTrue(report["passed"])
        with patch("verify._objective", side_effect=[10.0, 9.0]):
            with self.assertRaisesRegex(RuntimeError, "exceeds compact LP"):
                cross_validate(data, result)


if __name__ == "__main__":
    unittest.main()
