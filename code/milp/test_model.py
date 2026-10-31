"""Small-instance independent enumeration and model boundary regressions."""
import copy
import itertools
import json
import math
from pathlib import Path
import unittest

from model import build_model, solve, validate_data


def enumerate_optimum(data):
    """Enumerate assignments; evaluate original exponential fatigue, not MILP rows."""
    line_plans = []
    for line in data["lines"]:
        tasks = line["tasks"]
        options = [[None] + [(s, m) for s in range(len(line["stations"]))
                             for m in t["modes"]] for t in tasks]
        plans = []
        for choice in itertools.product(*options):
            assigned = {t["id"]: c for t, c in zip(tasks, choice) if c is not None}
            if not set(line.get("required_tasks", [])) <= assigned.keys():
                continue
            if any(j in assigned and (i not in assigned or assigned[i][0] > assigned[j][0])
                   for i, j in line.get("precedence", [])):
                continue
            if sum(t.get("weight", 0) for t in tasks if t["id"] in assigned) < line.get("min_recovery", 0):
                continue
            profit = sum(t["value"] - t["modes"][c[1]]["cost"]
                         for t, c in zip(tasks, choice) if c is not None)
            humans = robots = 0
            feasible = True
            for s, station in enumerate(line["stations"]):
                selected = [(t["modes"][c[1]], c[1]) for t, c in zip(tasks, choice)
                            if c is not None and c[0] == s]
                if not selected:
                    continue
                h = any(m in ("H", "J") for _, m in selected)
                r = any(m in ("R", "J") for _, m in selected)
                duration = sum(p["time"] for p, _ in selected)
                fatigue = 1 - math.exp(-sum(p["time"] * p["beta"] for p, _ in selected))
                if duration > line["cycle_time"] + 1e-9 or fatigue > line["fatigue_limit"] + 1e-9:
                    feasible = False
                    break
                humans += h
                robots += r
                profit -= station["fixed_cost"] + h * station["human_cost"] + r * station["robot_cost"]
            if feasible:
                plans.append((profit, humans, robots))
        line_plans.append(plans)
    feasible_profits = [sum(p[0] for p in combination)
                        for combination in itertools.product(*line_plans)
                        if sum(p[1] for p in combination) <= data["human_limit"]
                        and sum(p[2] for p in combination) <= data["robot_limit"]]
    return max(feasible_profits, default=None)


def tiny():
    return {"human_limit": 1, "robot_limit": 1, "lines": [{
        "id": "L", "cycle_time": 5, "fatigue_limit": 0.5,
        "stations": [{"fixed_cost": 0, "human_cost": 0, "robot_cost": 0}],
        "tasks": [{"id": "a", "value": 10, "weight": 1, "modes": {
            "H": {"time": 2, "cost": 1, "beta": 0.1}}}]}]}


class ModelTests(unittest.TestCase):
    def assert_matches_enumeration(self, data):
        expected = enumerate_optimum(data)
        result = solve(build_model(data))
        if expected is None:
            self.assertFalse(result["has_feasible_solution"])
            self.assertIsNone(result["objective"])
        else:
            self.assertTrue(result["optimal"], result)
            self.assertAlmostEqual(result["objective"], expected)
        return result

    def test_examples_and_shared_resource_competition(self):
        for name in ("single_line", "two_lines"):
            data = json.loads((Path(__file__).parent / "examples" / f"{name}.json").read_text())
            with self.subTest(example=name):
                self.assert_matches_enumeration(data)
        for h, r in ((0, 0), (1, 1), (2, 0), (3, 2)):
            with self.subTest(humans=h, robots=r):
                variant = copy.deepcopy(data)
                variant.update(human_limit=h, robot_limit=r)
                self.assert_matches_enumeration(variant)

    def test_all_optional_unprofitable_tasks_may_be_skipped(self):
        data = tiny()
        data["lines"][0]["tasks"][0]["value"] = -1
        result = self.assert_matches_enumeration(data)
        self.assertEqual(result["lines"][0]["selected_tasks"], [])
        self.assertEqual(result["resources_used"], {"humans": 0, "robots": 0})
        self.assertEqual(result["lines"][0]["stations"][0]["active"], 0)

    def test_zero_fatigue_allows_robot_but_forbids_positive_human_load(self):
        data = tiny()
        line = data["lines"][0]
        line["fatigue_limit"] = 0
        line["required_tasks"] = ["a"]
        self.assert_matches_enumeration(data)
        line["tasks"][0]["modes"]["R"] = {"time": 2, "cost": 3, "beta": 0}
        result = self.assert_matches_enumeration(data)
        station = result["lines"][0]["stations"][0]
        self.assertEqual((station["human"], station["robot"]), (0, 1))

    def test_joint_duration_counted_once_and_requires_both_resources(self):
        data = tiny()
        line = data["lines"][0]
        line["cycle_time"] = 2
        line["required_tasks"] = ["a"]
        line["tasks"][0]["modes"] = {"J": {"time": 2, "cost": 1, "beta": 0.1}}
        result = self.assert_matches_enumeration(data)
        self.assertEqual(result["resources_used"], {"humans": 1, "robots": 1})
        data["robot_limit"] = 0
        self.assert_matches_enumeration(data)

    def test_predecessor_closure_same_station_and_reverse_station(self):
        data = tiny()
        line = data["lines"][0]
        b = copy.deepcopy(line["tasks"][0])
        b.update(id="b", value=20)
        line["tasks"][0]["value"] = -2
        line["tasks"].append(b)
        line["precedence"] = [["a", "b"]]
        result = self.assert_matches_enumeration(data)
        self.assertEqual(result["lines"][0]["selected_tasks"], ["a", "b"])
        line["stations"].append(copy.deepcopy(line["stations"][0]))
        model = build_model(data)
        model.problem += model.x["L", "a", 2, "H"] == 1
        model.problem += model.x["L", "b", 1, "H"] == 1
        self.assertFalse(solve(model)["has_feasible_solution"])

    def test_required_overlong_task_and_impossible_recovery(self):
        data = tiny()
        line = data["lines"][0]
        line["required_tasks"] = ["a"]
        line["cycle_time"] = 1
        self.assert_matches_enumeration(data)
        line["cycle_time"] = 5
        line["min_recovery"] = 2
        self.assert_matches_enumeration(data)

    def test_heterogeneous_stations_may_have_a_gap(self):
        data = tiny()
        line = data["lines"][0]
        line["stations"][0]["fixed_cost"] = 100
        line["stations"].append({"fixed_cost": 0, "human_cost": 0, "robot_cost": 0})
        result = self.assert_matches_enumeration(data)
        self.assertEqual([s["active"] for s in result["lines"][0]["stations"]], [0, 1])

    def test_input_validation(self):
        mutations = [lambda d: d.update(human_limit=-1),
                     lambda d: d["lines"][0].update(fatigue_limit=1),
                     lambda d: d["lines"][0].update(precedence=[["a", "a"]]),
                     lambda d: d["lines"][0].update(precedence=[["a", "missing"]]),
                     lambda d: d["lines"][0]["tasks"][0].update(value=float("nan")),
                     lambda d: d["lines"][0]["tasks"][0].update(modes={"R": {"time": 1, "cost": 0, "beta": 1}}),
                     lambda d: d["lines"][0]["tasks"][0]["modes"]["H"].update(time=0),
                     lambda d: d["lines"][0].update(required_tasks=["unknown"]),
                     lambda d: d["lines"][0].update(cycle_tim=4)]
        for mutation in mutations:
            data = tiny()
            mutation(data)
            with self.subTest(data=data), self.assertRaises(ValueError):
                validate_data(data)


if __name__ == "__main__":
    unittest.main()
