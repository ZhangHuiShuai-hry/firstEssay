"""End-to-end CBC certificates and deliberate corruption of genuine run logs."""
import copy
import unittest

from solve import run_cg
from test_dwcg import tiny
from verify import cross_validate


class CertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = tiny()
        cls.result, _ = run_cg(cls.data)
        cls.infeasible = tiny()
        cls.infeasible.update(human_limit=0, robot_limit=0)
        cls.infeasible["lines"][0]["required_tasks"] = ["a"]
        cls.infeasible_result, _ = run_cg(cls.infeasible)

    def assert_missing(self, data, result, objective_checked=True):
        report = cross_validate(data, result)
        self.assertTrue(report["model_consistency_passed"])
        self.assertEqual(report["optimal_objective_cross_validated"], objective_checked)
        self.assertFalse(report["termination_certificate_verified"])
        self.assertFalse(report["cg_verified"])
        self.assertFalse(report["passed"])
        self.assertEqual(report["certificate_status"], "missing")
        self.assertEqual(report["verification_status"], "inconclusive")

    def test_normal_convergence_and_enumerated_reduced_costs(self):
        report = cross_validate(self.data, self.result)
        self.assertTrue(report["optimal_objective_cross_validated"])
        self.assertTrue(report["pricing_termination_certificate_verified"])
        self.assertTrue(report["termination_certificate_verified"])
        self.assertTrue(report["passed"])
        for station in report["termination_certificate"]["station_reduced_costs"]:
            self.assertAlmostEqual(station["reported"], station["enumerated"])

    def test_missing_last_phase_II_record_is_objective_only(self):
        result = copy.deepcopy(self.result)
        result["history"] = [r for r in result["history"] if r["phase"] == 1]
        self.assert_missing(self.data, result)

    def test_missing_certificate_fields_are_not_silent_successes(self):
        for key in ("maximum_reduced_cost", "pricing", "duals", "objective", "lp_upper_bound"):
            result = copy.deepcopy(self.result)
            del result["history"][-1][key]
            with self.subTest(key=key):
                self.assert_missing(self.data, result)
        for key in ("epsilon", "final_duals"):
            result = copy.deepcopy(self.result)
            del result[key]
            with self.subTest(key=key):
                self.assert_missing(self.data, result)

    def test_positive_final_reduced_cost_rejected(self):
        result = copy.deepcopy(self.result)
        result["history"][-1]["maximum_reduced_cost"] = 1
        with self.assertRaisesRegex(RuntimeError, "positive reduced cost"):
            cross_validate(self.data, result)

    def test_last_RMP_must_match_final_return_values(self):
        for key, delta in (("objective", -0.1), ("lp_upper_bound", 0.1)):
            result = copy.deepcopy(self.result)
            result["history"][-1][key] += delta
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, "Final RMP"):
                cross_validate(self.data, result)

    def test_station_coverage_missing_duplicate_unknown_and_nonnumeric(self):
        result = copy.deepcopy(self.result)
        result["history"][-1]["pricing"] = []
        self.assert_missing(self.data, result)
        for change in ("duplicate", "unknown", "nonfinite", "missing_number"):
            result = copy.deepcopy(self.result)
            pricing = result["history"][-1]["pricing"]
            if change == "duplicate":
                pricing.append(copy.deepcopy(pricing[0]))
            elif change == "unknown":
                pricing[0]["station"] = 999
            elif change == "nonfinite":
                pricing[0]["reduced_cost"] = float("nan")
            else:
                del pricing[0]["reduced_cost"]
            with self.subTest(change=change):
                if change == "missing_number":
                    self.assert_missing(self.data, result)
                else:
                    with self.assertRaises(RuntimeError):
                        cross_validate(self.data, result)

    def test_pricing_report_must_match_independent_enumeration(self):
        result = copy.deepcopy(self.result)
        result["history"][-1]["pricing"][0]["reduced_cost"] -= 0.5
        result["history"][-1]["maximum_reduced_cost"] -= 0.5
        with self.assertRaisesRegex(RuntimeError, "Pricing vs enumeration"):
            cross_validate(self.data, result)

    def test_dual_rows_and_snapshots_are_checked(self):
        for change in ("missing", "duplicate", "changed", "nonfinite"):
            result = copy.deepcopy(self.result)
            entries = result["history"][-1]["duals"]
            if change == "missing":
                entries.pop()
            elif change == "duplicate":
                entries.append(copy.deepcopy(entries[0]))
            elif change == "changed":
                entries[0]["value"] += 1
            else:
                entries[0]["value"] = float("inf")
            with self.subTest(change=change):
                if change == "missing":
                    self.assert_missing(self.data, result)
                else:
                    with self.assertRaises(RuntimeError):
                        cross_validate(self.data, result)

    def test_dual_repaired_upper_bound_not_just_objective_agreement(self):
        result = copy.deepcopy(self.result)
        result["history"][-1]["lp_upper_bound"] += 1
        result["lp_upper_bound"] += 1
        with self.assertRaisesRegex(RuntimeError, "Dual-repaired"):
            cross_validate(self.data, result)

    def test_Phase_I_artificial_and_negative_upper_certificate(self):
        report = cross_validate(self.infeasible, self.infeasible_result)
        self.assertTrue(report["cg_infeasibility_checked"])
        self.assertTrue(report["phase_I_infeasibility_certificate_verified"])
        self.assertTrue(report["passed"])
        certificate = report["termination_certificate"]
        self.assertGreater(certificate["artificial_sum"], 0)
        self.assertLess(certificate["recomputed_upper_bound"], 0)

    def test_Phase_I_missing_certificate_is_not_verified(self):
        for key in ("artificials", "artificial_sum", "duals"):
            result = copy.deepcopy(self.infeasible_result)
            del result["history"][-1][key]
            with self.subTest(key=key):
                self.assert_missing(self.infeasible, result, objective_checked=False)
        result = copy.deepcopy(self.infeasible_result)
        del result["phase_I_lp_upper_bound"]
        self.assert_missing(self.infeasible, result, objective_checked=False)

    def test_Phase_I_corrupt_artificials_and_upper_bounds(self):
        for change in ("negative", "sum", "duplicate", "upper", "final_sum"):
            result = copy.deepcopy(self.infeasible_result)
            record = result["history"][-1]
            if change == "negative":
                record["artificials"][0]["value"] = -1
            elif change == "sum":
                record["artificials"][0]["value"] += 0.5
            elif change == "duplicate":
                record["artificials"].append(copy.deepcopy(record["artificials"][0]))
            elif change == "upper":
                result["phase_I_lp_upper_bound"] = 0
            else:
                result["phase_I_artificial_sum"] = 0
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                cross_validate(self.infeasible, result)

    def test_real_CBC_iteration_limit_and_Phase_I_uncertainty(self):
        result, _ = run_cg(self.data, max_iterations=1)
        report = cross_validate(self.data, result)
        self.assertFalse(report["passed"])
        self.assertFalse(report["termination_certificate_verified"])
        data = tiny()
        data["lines"][0]["required_tasks"] = ["a"]
        # Deliberately coarse epsilon makes the first exact PP stop Phase I
        # without proving infeasibility. This is an actual CBC run, not a mock.
        result, _ = run_cg(data, epsilon=2)
        self.assertEqual(result["status"], "phase_I_numerically_inconclusive")
        report = cross_validate(data, result)
        self.assertTrue(report["model_consistency_passed"])
        self.assertFalse(report["cg_verified"])
        self.assertFalse(report["passed"])

    def test_LP_feasible_integer_infeasible_certificate(self):
        data = tiny()
        data["lines"][0]["required_tasks"] = ["a"]
        second = copy.deepcopy(data["lines"][0])
        second.update(id="L2", required_tasks=[], min_recovery=1)
        second["tasks"][0].update(weight=2, modes={"J": dict(time=2, cost=0, beta=0.1)})
        data["lines"].append(second)
        result, _ = run_cg(data)
        report = cross_validate(data, result)
        self.assertFalse(report["full_ip_feasible"])
        self.assertTrue(report["termination_certificate_verified"])
        self.assertTrue(report["passed"])

    def test_zero_objective_certificate(self):
        data = tiny()
        line = data["lines"][0]
        line["tasks"][0]["value"] = 0
        for params in line["tasks"][0]["modes"].values():
            params["cost"] = 0
        line["stations"][0] = dict(fixed_cost=0, human_cost=0, robot_cost=0)
        result, _ = run_cg(data)
        report = cross_validate(data, result)
        self.assertEqual(report["full_lp_objective"], 0)
        self.assertTrue(report["termination_certificate_verified"])
        self.assertTrue(report["passed"])


if __name__ == "__main__":
    unittest.main()
