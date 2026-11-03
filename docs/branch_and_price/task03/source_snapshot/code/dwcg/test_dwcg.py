"""Independent local enumeration, dual checks and root/full/compact comparisons."""
import copy
import json
from pathlib import Path
import random
import unittest

from common import blocks, empty_pool, enumerate_pool, reduced_cost, compact
from master import build_master, solve_master
from pricing import price
from solve import run_cg
from verify import cross_validate


def tiny():
    return {"human_limit": 1, "robot_limit": 1, "lines": [{
        "id": "L", "cycle_time": 3, "fatigue_limit": 0.5,
        "stations": [{"fixed_cost": 1, "human_cost": 1, "robot_cost": 1}],
        "tasks": [{"id": "a", "value": 10, "weight": 1, "modes": {
            "H": {"time": 2, "cost": 1, "beta": 0.1},
            "R": {"time": 2, "cost": 2, "beta": 0}}}]}]}


class ColumnGenerationTests(unittest.TestCase):
    def check_instance(self, data):
        result, pool = run_cg(data)
        report = cross_validate(data, result)
        self.assertTrue(report["passed"])
        if report["full_lp_feasible"]:
            self.assertTrue(result["lp_converged"], result)
            self.assertAlmostEqual(result["lp_objective"], report["full_lp_objective"], places=5)
            self.assertGreaterEqual(result["lp_upper_bound"] + 1e-5, report["full_lp_objective"])
        else:
            self.assertEqual(result["status"], "infeasible_full_column_LP")
        return result, pool, report

    def test_examples_root_full_lp_full_ip_compact_ip(self):
        for name in ("single_line", "two_lines"):
            data = json.loads((Path(__file__).resolve().parents[1] / "milp/examples" / f"{name}.json").read_text())
            with self.subTest(example=name):
                result, _, _ = self.check_instance(data)
                self.assertTrue(result["integer_recovery"]["has_feasible_solution"])
                self.assertFalse(result["integer_recovery"]["optimal"])
                for row in result["history"]:
                    if row["phase"] == 2:
                        self.assertLessEqual(row["objective"], result["lp_objective"] + 1e-5)
                        self.assertGreaterEqual(row["lp_upper_bound"] + 1e-5, result["lp_objective"])

    def test_pricing_vs_enumeration_in_both_phases(self):
        data = tiny()
        line = data["lines"][0]
        line["stations"].append(copy.deepcopy(line["stations"][0]))
        b = copy.deepcopy(line["tasks"][0])
        b["id"] = "b"
        b["modes"]["J"] = {"time": 1, "cost": 3, "beta": 0.15}
        line["tasks"].append(b)
        line["precedence"] = [["a", "b"]]
        line["required_tasks"] = ["b"]
        all_columns = enumerate_pool(data)
        rng = random.Random(42)
        for phase in (1, 2):
            keys = build_master(data, empty_pool(data), phase).rows
            for trial in range(8):
                duals = {key: rng.uniform(0, 4) for key in keys}
                # Equality row prices are deliberately signed and station-dependent.
                duals["task", "L", "b"] = rng.uniform(-3, 3)
                for s in (1, 2):
                    duals["station", "L", s] = rng.uniform(-2, 3)
                    col, rc = price(line, s, duals, phase)
                    expected = max(reduced_cost(line, s, c, duals, phase) for c in all_columns["L", s])
                    with self.subTest(phase=phase, trial=trial, station=s):
                        self.assertAlmostEqual(rc, expected, places=6)
                        self.assertAlmostEqual(rc, reduced_cost(line, s, col, duals, phase), places=6)

    def test_row_duals_match_solver_reduced_costs(self):
        data = tiny()
        data["lines"][0].update(required_tasks=["a"], min_recovery=1)
        pool = enumerate_pool(data)
        for phase in (1, 2):
            master = solve_master(build_master(data, pool, phase))
            line = data["lines"][0]
            for p, col in enumerate(pool["L", 1]):
                rc = reduced_cost(line, 1, col, master.duals(), phase)
                self.assertAlmostEqual(rc, master.variables["L", 1, p].dj, places=6)

    def test_required_recovery_phase_I_and_infeasibility(self):
        data = tiny()
        data["lines"][0].update(required_tasks=["a"], min_recovery=1)
        result, _, _ = self.check_instance(data)
        self.assertGreater(result["history"][0]["artificial_sum"], 0)
        data["human_limit"] = data["robot_limit"] = 0
        result, _, _ = self.check_instance(data)
        self.assertIsNone(result["lp_objective"])

    def test_recovery_only_initialization_and_impossible_recovery(self):
        data = tiny()
        data["lines"][0]["min_recovery"] = 1
        self.check_instance(data)
        data["lines"][0]["min_recovery"] = 2
        self.check_instance(data)

    def test_empty_zero_profit_objective_and_no_resources(self):
        data = tiny()
        data.update(human_limit=0, robot_limit=0)
        result, _, _ = self.check_instance(data)
        self.assertEqual(result["lp_objective"], 0)
        self.assertEqual(result["integer_recovery"]["objective"], 0)
        data["lines"][0]["tasks"][0].update(value=0)
        for mode in data["lines"][0]["tasks"][0]["modes"].values():
            mode["cost"] = 0
        data["lines"][0]["stations"][0] = dict(fixed_cost=0, human_cost=0, robot_cost=0)
        self.check_instance(data)

    def test_zero_fatigue_robot_and_joint_time(self):
        data = tiny()
        line = data["lines"][0]
        line.update(required_tasks=["a"], fatigue_limit=0)
        self.check_instance(data)
        del line["tasks"][0]["modes"]["R"]
        self.check_instance(data)
        line["fatigue_limit"] = 0.5
        line["cycle_time"] = 2
        line["tasks"][0]["modes"] = {"J": {"time": 2, "cost": 0, "beta": 0.1}}
        self.check_instance(data)

    def test_predecessor_need_not_be_inside_column_and_heterogeneous_stations(self):
        data = tiny()
        line = data["lines"][0]
        line["cycle_time"] = 2
        line["stations"].append(copy.deepcopy(line["stations"][0]))
        data["human_limit"] = 2
        b = copy.deepcopy(line["tasks"][0])
        b.update(id="b", value=20)
        line["tasks"].append(b)
        line["precedence"] = [["a", "b"]]
        line["required_tasks"] = ["b"]
        cols = enumerate_pool(data)["L", 2]
        self.assertTrue(any(c.assignments == (("b", "H"),) for c in cols))
        self.check_instance(data)
        data = tiny()
        line = data["lines"][0]
        line["stations"][0]["fixed_cost"] = 100
        line["stations"].append(dict(fixed_cost=0, human_cost=0, robot_cost=0))
        result, _, _ = self.check_instance(data)
        self.assertEqual([s["active"] for s in result["integer_recovery"]["lines"][0]["stations"]], [0, 1])

    def test_iteration_limit_is_not_an_optimality_certificate(self):
        data = tiny()
        result, _ = run_cg(data, max_iterations=1)
        self.assertFalse(result["lp_converged"])
        self.assertEqual(result["status"], "iteration_limit")
        data["lines"][0]["required_tasks"] = ["a"]
        result, _ = run_cg(data, max_iterations=1)
        self.assertFalse(result["lp_converged"])
        self.assertNotEqual(result["status"], "infeasible_full_column_LP")

    def test_lp_feasible_can_be_integer_infeasible(self):
        data = tiny()
        line = data["lines"][0]
        line["required_tasks"] = ["a"]
        second = copy.deepcopy(line)
        second.update(id="L2", required_tasks=[], min_recovery=1)
        second["tasks"][0].update(weight=2, modes={"J": {"time": 2, "cost": 0, "beta": 0.1}})
        data["lines"].append(second)
        # Line 1: half H, half R. Line 2: half J, half empty. Total H=R=1.
        # Integer recovery must execute J, leaving no resource for mandatory line 1.
        result, _, report = self.check_instance(data)
        self.assertTrue(report["full_lp_feasible"])
        self.assertFalse(report["full_ip_feasible"])
        self.assertFalse(result["integer_recovery"]["has_feasible_solution"])

    def test_enumeration_guard_and_invalid_data(self):
        with self.assertRaises(ValueError):
            enumerate_pool(tiny(), max_combinations=1)
        data = tiny()
        data["lines"][0]["precedence"] = [["a", "a"]]
        with self.assertRaises(ValueError):
            run_cg(data)

    def test_seeded_small_instances(self):
        rng = random.Random(101)
        for trial in range(8):
            data = tiny()
            line = data["lines"][0]
            line["stations"].append(copy.deepcopy(line["stations"][0]))
            data["human_limit"] = rng.randrange(3)
            data["robot_limit"] = rng.randrange(3)
            line["cycle_time"] = rng.randrange(2, 6)
            line["min_recovery"] = rng.randrange(3)
            for i in ("b", "c"):
                task = copy.deepcopy(line["tasks"][0])
                task.update(id=i, value=rng.randrange(-2, 15))
                line["tasks"].append(task)
            line["precedence"] = [["a", "b"], ["b", "c"]]
            with self.subTest(trial=trial):
                self.check_instance(data)


if __name__ == "__main__":
    unittest.main()
