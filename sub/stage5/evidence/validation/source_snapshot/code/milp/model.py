"""ML-HRC-DLBP-CF: equations (5)--(19), PuLP/CBC implementation.

Run: python code/milp/model.py code/milp/examples/two_lines.json
All examples are synthetic. Fatigue refers to one representative cycle.
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pulp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from solver_backend import make_solver

HUMAN = {"H": 1, "R": 0, "J": 1}
ROBOT = {"H": 0, "R": 1, "J": 1}


def number(value: Any, name: str, lower: float | None = None,
           strict: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: expected a number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name}: must be finite")
    if lower is not None and (value < lower or (strict and value == lower)):
        raise ValueError(f"{name}: must be {'>' if strict else '>='} {lower}")
    return value


def integer(value: Any, name: str, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower:
        raise ValueError(f"{name}: expected integer >= {lower}")
    return value


def identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}: expected a nonempty string")
    return value


def check_keys(obj: Any, required: set[str], optional: set[str], name: str) -> None:
    if not isinstance(obj, dict):
        raise ValueError(f"{name}: expected an object")
    missing = required - obj.keys()
    extra = obj.keys() - required - optional
    if missing or extra:
        raise ValueError(f"{name}: missing keys {sorted(missing)}, unknown keys {sorted(extra)}")


def topological_order(tasks: list[str], edges: list[tuple[str, str]]) -> list[str]:
    """Deterministic order; also validates the full input DAG."""
    successors = {i: [] for i in tasks}
    indegree = dict.fromkeys(tasks, 0)
    for i, j in edges:
        if i not in successors or j not in successors:
            raise ValueError(f"Unknown task in precedence edge {(i, j)}")
        successors[i].append(j)
        indegree[j] += 1
    ready = [i for i in tasks if indegree[i] == 0]
    heapq.heapify(ready)
    ordered = []
    while ready:
        i = heapq.heappop(ready)
        ordered.append(i)
        for j in successors[i]:
            indegree[j] -= 1
            if indegree[j] == 0:
                heapq.heappush(ready, j)
    if len(ordered) != len(tasks):
        raise ValueError("Precedence graph must be a DAG")
    return ordered


def validate_data(data: dict) -> None:
    """Reject malformed data; valid but infeasible instances are left to CBC."""
    check_keys(data, {"human_limit", "robot_limit", "lines"}, {"name"}, "instance")
    integer(data["human_limit"], "human_limit")
    integer(data["robot_limit"], "robot_limit")
    if not isinstance(data["lines"], list) or not data["lines"]:
        raise ValueError("lines must be a nonempty list")
    line_ids = set()
    for line in data["lines"]:
        check_keys(line, {"id", "cycle_time", "fatigue_limit", "stations", "tasks"},
                   {"precedence", "required_tasks", "min_recovery"}, "line")
        lid = identifier(line["id"], "line.id")
        if lid in line_ids:
            raise ValueError(f"Duplicate line id: {lid}")
        line_ids.add(lid)
        number(line["cycle_time"], "cycle_time", 0, strict=True)
        fatigue = number(line["fatigue_limit"], "fatigue_limit", 0)
        if fatigue >= 1:
            raise ValueError("fatigue_limit must be < 1")
        number(line.get("min_recovery", 0), "min_recovery", 0)
        if not isinstance(line["stations"], list) or not line["stations"]:
            raise ValueError("stations must be a nonempty list in process order")
        for station in line["stations"]:
            check_keys(station, {"fixed_cost", "human_cost", "robot_cost"}, set(), "station")
            for key, value in station.items():
                number(value, key, 0)
        if not isinstance(line["tasks"], list) or not line["tasks"]:
            raise ValueError("tasks must be a nonempty list")
        ids = []
        for task in line["tasks"]:
            check_keys(task, {"id", "value", "modes"}, {"weight"}, "task")
            tid = identifier(task["id"], "task.id")
            if tid in ids:
                raise ValueError(f"Duplicate task id in {lid}: {tid}")
            ids.append(tid)
            number(task["value"], "value")
            number(task.get("weight", 0), "weight", 0)
            if not isinstance(task["modes"], dict) or not task["modes"]:
                raise ValueError("modes must be a nonempty object")
            for mode, params in task["modes"].items():
                if mode not in HUMAN:
                    raise ValueError(f"Unknown mode {mode}; use H, R or J")
                check_keys(params, {"time", "cost", "beta"}, set(), "mode")
                time = number(params["time"], "time", 0, strict=True)
                number(params["cost"], "cost", 0)
                beta = number(params["beta"], "beta", 0)
                if mode == "R" and beta != 0:
                    raise ValueError("R mode must have beta=0")
                if not math.isfinite(time * beta):
                    raise ValueError("time * beta must be finite")
        edges = line.get("precedence", [])
        if not isinstance(edges, list) or any(
            not isinstance(edge, (list, tuple)) or len(edge) != 2
            or not all(isinstance(i, str) for i in edge) for edge in edges
        ):
            raise ValueError("precedence must contain [predecessor_id, successor_id] pairs")
        if len(set(map(tuple, edges))) != len(edges):
            raise ValueError("Duplicate precedence edges")
        topological_order(ids, edges)
        required = line.get("required_tasks", [])
        if (not isinstance(required, list) or not all(isinstance(i, str) for i in required)
                or len(set(required)) != len(required) or not set(required) <= set(ids)):
            raise ValueError("required_tasks must contain unique known task ids")


@dataclass
class Model:
    problem: pulp.LpProblem
    data: dict
    y: dict
    x: dict
    u: dict
    h: dict
    r: dict
    profit_terms: dict


def build_model(data: dict) -> Model:
    """Create P0 without solving. Keys use external line/task IDs and 1-based stations."""
    validate_data(data)
    problem = pulp.LpProblem("ML_HRC_DLBP_CF", pulp.LpMaximize)
    y, x, u, h, r = {}, {}, {}, {}, {}
    revenue, direct, fixed, human_cost, robot_cost = [], [], [], [], []
    for li, line in enumerate(data["lines"], 1):
        l = line["id"]
        tasks = {task["id"]: task for task in line["tasks"]}
        stations = range(1, len(line["stations"]) + 1)
        n = len(tasks)
        budget = -math.log1p(-line["fatigue_limit"])
        # Internal ordinal names avoid collisions caused by punctuation in user IDs.
        for ti, (i, task) in enumerate(tasks.items(), 1):
            y[l, i] = pulp.LpVariable(f"y_{li}_{ti}", cat="Binary")
            revenue.append(task["value"] * y[l, i])
            for s in stations:
                for m, params in task["modes"].items():
                    x[l, i, s, m] = pulp.LpVariable(f"x_{li}_{ti}_{s}_{m}", cat="Binary")
                    direct.append(params["cost"] * x[l, i, s, m])
            problem += (pulp.lpSum(x[l, i, s, m] for s in stations for m in task["modes"])
                        == y[l, i], f"eq06_assignment_{li}_{ti}")
            if i in line.get("required_tasks", []):
                problem += y[l, i] == 1, f"eq17_required_{li}_{ti}"
        for s, costs in enumerate(line["stations"], 1):
            u[l, s] = pulp.LpVariable(f"u_{li}_{s}", cat="Binary")
            h[l, s] = pulp.LpVariable(f"h_{li}_{s}", cat="Binary")
            r[l, s] = pulp.LpVariable(f"r_{li}_{s}", cat="Binary")
            fixed.append(costs["fixed_cost"] * u[l, s])
            human_cost.append(costs["human_cost"] * h[l, s])
            robot_cost.append(costs["robot_cost"] * r[l, s])
            terms = [(x[l, i, s, m], m, p) for i, task in tasks.items()
                     for m, p in task["modes"].items()]
            count = pulp.lpSum(v for v, _, _ in terms)
            humans = pulp.lpSum(HUMAN[m] * v for v, m, _ in terms)
            robots = pulp.lpSum(ROBOT[m] * v for v, m, _ in terms)
            problem += (pulp.lpSum(p["time"] * v for v, _, p in terms)
                        <= line["cycle_time"] * u[l, s], f"eq08_cycle_{li}_{s}")
            for eq, label, variable, total in [(9, "station", u[l, s], count),
                                              (10, "human", h[l, s], humans),
                                              (11, "robot", r[l, s], robots)]:
                problem += variable <= total, f"eq{eq:02d}_{label}_lower_{li}_{s}"
                problem += total <= n * variable, f"eq{eq:02d}_{label}_upper_{li}_{s}"
            problem += (pulp.lpSum(p["beta"] * p["time"] * v for v, _, p in terms)
                        <= budget * h[l, s], f"eq14_fatigue_{li}_{s}")
        for e, (i, j) in enumerate(line.get("precedence", []), 1):
            for k in stations:
                problem += (
                    pulp.lpSum(x[l, j, s, m] for s in range(1, k + 1) for m in tasks[j]["modes"])
                    <= pulp.lpSum(x[l, i, s, m] for s in range(1, k + 1) for m in tasks[i]["modes"]),
                    f"eq07_precedence_{li}_{e}_{k}")
        problem += (pulp.lpSum(task.get("weight", 0) * y[l, i] for i, task in tasks.items())
                    >= line.get("min_recovery", 0), f"eq18_recovery_{li}")
    problem += pulp.lpSum(h.values()) <= data["human_limit"], "eq15_shared_humans"
    problem += pulp.lpSum(r.values()) <= data["robot_limit"], "eq16_shared_robots"
    profit_terms = {name: pulp.lpSum(terms) for name, terms in
                    [("revenue", revenue), ("execution_cost", direct), ("station_cost", fixed),
                     ("human_cost", human_cost), ("robot_cost", robot_cost)]}
    problem += (profit_terms["revenue"] - profit_terms["execution_cost"]
                - profit_terms["station_cost"] - profit_terms["human_cost"]
                - profit_terms["robot_cost"]), "eq05_net_profit"
    return Model(problem, data, y, x, u, h, r, profit_terms)


def solution_report(model: Model, tolerance: float = 1e-6) -> dict:
    """Never interpret infeasible/relaxed/partial solver values as an incumbent."""
    problem = model.problem
    status = pulp.LpStatus[problem.status]
    solution_status = pulp.LpSolution.get(problem.sol_status, "Unknown")
    incumbent_status = problem.sol_status in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible)
    has_solution = incumbent_status and problem.valid(tolerance)
    result = {"status": status, "solution_status": solution_status,
              "optimal": has_solution and problem.sol_status == pulp.LpSolutionOptimal,
              "has_feasible_solution": bool(has_solution), "objective": None}
    if not has_solution:
        return result
    terms = {name: float(pulp.value(expr)) for name, expr in model.profit_terms.items()}
    result["profit_breakdown"] = terms
    # Reconstruct the objective from the expressions even when it is identically zero.
    result["objective"] = terms["revenue"] - sum(v for k, v in terms.items() if k != "revenue")
    result["resources_used"] = {"humans": sum(round(v.value()) for v in model.h.values()),
                                "robots": sum(round(v.value()) for v in model.r.values())}
    result["lines"] = []
    for line in model.data["lines"]:
        l = line["id"]
        tasks = {t["id"]: t for t in line["tasks"]}
        order = topological_order(list(tasks), line.get("precedence", []))
        selected = [i for i in order if model.y[l, i].value() > 0.5]
        report = {"id": l, "selected_tasks": selected,
                  "recovery": sum(tasks[i].get("weight", 0) for i in selected), "stations": []}
        for s in range(1, len(line["stations"]) + 1):
            assignments = [{"task": i, "mode": m} for i in order for m in tasks[i]["modes"]
                           if model.x[l, i, s, m].value() > 0.5]
            duration = sum(tasks[a["task"]]["modes"][a["mode"]]["time"] for a in assignments)
            load = sum(tasks[a["task"]]["modes"][a["mode"]]["time"]
                       * tasks[a["task"]]["modes"][a["mode"]]["beta"] for a in assignments)
            report["stations"].append({"station": s, "active": round(model.u[l, s].value()),
                "human": round(model.h[l, s].value()), "robot": round(model.r[l, s].value()),
                "assignments_in_order": assignments, "time_used": duration,
                "fatigue_load": load, "fatigue_level": -math.expm1(-load),
                "fatigue_budget": -math.log1p(-line["fatigue_limit"])})
        result["lines"].append(report)
    return result


def solve(model: Model, time_limit: float | None = None, gap: float = 0,
          verbose: bool = False) -> dict:
    if time_limit is not None:
        number(time_limit, "time_limit", 0, strict=True)
    number(gap, "gap", 0)
    solver = make_solver(msg=verbose, time_limit=time_limit, gap=gap, role="compact_ip")
    if not solver.available():
        raise RuntimeError("CBC is unavailable; install a PuLP distribution containing CBC")
    model.problem.solve(solver)
    result = solution_report(model)
    # CBC may report 'optimal' after satisfying a positive requested gap.
    result["requested_relative_gap"] = gap
    result["optimal"] = result["optimal"] and gap == 0
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path)
    parser.add_argument("--output", type=Path, help="Save JSON solution")
    parser.add_argument("--lp", type=Path, help="Export the MILP as an LP file")
    parser.add_argument("--time-limit", type=float, default=None, help="CBC time limit in seconds")
    parser.add_argument("--gap", type=float, default=0, help="Relative MIP gap (default 0)")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--solver", choices=("cbc", "cplex_py"), default="cbc")
    args = parser.parse_args()
    try:
        data = json.loads(args.instance.read_text(encoding="utf-8-sig"))
        model = build_model(data)
        if args.lp:
            args.lp.parent.mkdir(parents=True, exist_ok=True)
            model.problem.writeLP(str(args.lp))
        from solver_backend import BackendConfig, use_backend
        with use_backend(BackendConfig(name=args.solver)):
            result = solve(model, args.time_limit, args.gap, args.verbose)
        rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0 if result["has_feasible_solution"] else 2
    except (ValueError, OSError, RuntimeError, pulp.PulpSolverError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
