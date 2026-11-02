"""Input compatibility, station columns, and independent master-row coefficients."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import importlib.util
import itertools
import math
from pathlib import Path
import sys

import pulp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from solver_backend import make_solver

# Load the existing implementation under a unique name, never shadow test/model modules.
_name = "_p1test_compact_milp"
if _name not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_name, Path(__file__).resolve().parents[1] / "milp/model.py")
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_name] = _module
    _spec.loader.exec_module(_module)
compact = sys.modules[_name]


def cbc(mip=True, verbose=False, role="verification"):
    """Backward-compatible name; backend is selected by solver_backend context."""
    solver = make_solver(mip=mip, msg=verbose, role=role)
    if not solver.available():
        raise RuntimeError("CBC is unavailable")
    return solver


def require_optimal(problem):
    if (problem.status != pulp.LpStatusOptimal or problem.sol_status != pulp.LpSolutionOptimal
            or not problem.valid(1e-6)):
        error = RuntimeError(f"Exact solve failed: {pulp.LpStatus[problem.status]} / "
                             f"{pulp.LpSolution.get(problem.sol_status)}")
        error.solver_result = getattr(problem, "backend_result", {})
        raise error


class PricingResult(tuple):
    """Backward-compatible (column, rc) pair with solver certificate metadata."""
    def __new__(cls, column, rc, certificate):
        answer = super().__new__(cls, (column, rc))
        answer.certificate = certificate
        return answer


@dataclass(frozen=True)
class Column:
    assignments: tuple[tuple[str, str], ...]
    active: int
    human: int
    robot: int
    duration: float
    fatigue: float
    recovery: float
    profit: float


def make_column(line, station, assignments, tolerance=1e-8):
    """Validate local feasibility only: no predecessor closure and no global limits."""
    assignments = tuple(sorted((i,m) for i,m in assignments))
    if len({i for i, _ in assignments}) != len(assignments):
        raise ValueError("A column cannot execute a task twice")
    tasks = {t["id"]: t for t in line["tasks"]}
    duration = fatigue = recovery = profit = 0.0
    human = robot = 0
    for i, m in assignments:
        p = tasks[i]["modes"][m]
        duration += p["time"]
        fatigue += p["time"] * p["beta"]
        recovery += tasks[i].get("weight", 0)
        profit += tasks[i]["value"] - p["cost"]
        human |= m in ("H", "J")
        robot |= m in ("R", "J")
    active = int(bool(assignments))
    if duration > line["cycle_time"] * active + tolerance:
        raise ValueError("Column exceeds cycle time")
    if fatigue > -math.log1p(-line["fatigue_limit"]) * human + tolerance:
        raise ValueError("Column exceeds fatigue budget")
    costs = line["stations"][station - 1]
    profit -= costs["fixed_cost"] * active + costs["human_cost"] * human + costs["robot_cost"] * robot
    return Column(assignments, active, int(human), int(robot), duration, fatigue, recovery, profit)


def blocks(data):
    return [(line, s) for line in data["lines"] for s in range(1, len(line["stations"]) + 1)]


def empty_pool(data):
    return {(line["id"], s): [make_column(line, s, [])] for line, s in blocks(data)}


def enumerate_pool(data, max_combinations=100000):
    """Tiny-instance oracle only. Never used by the production CG loop."""
    pool = {}
    for line, s in blocks(data):
        tasks = line["tasks"]
        combinations = math.prod(1 + len(t["modes"]) for t in tasks)
        if combinations > max_combinations:
            raise ValueError(f"Enumeration guard: {combinations} combinations per station; "
                             f"limit is {max_combinations}")
        choices = [[None] + [(t["id"], m) for m in t["modes"]] for t in tasks]
        pool[line["id"], s] = []
        for selection in itertools.product(*choices):
            try:
                col = make_column(line, s, [a for a in selection if a is not None])
            except ValueError:
                continue
            pool[line["id"], s].append(col)
    return pool


def coefficients(line, station, col):
    """CG-17--24: explicit column vector, independent of PP adjusted rewards."""
    return dict(_coefficient_items(line['id'],station,len(line['stations']),
                tuple(map(tuple,line.get('precedence',[]))),col.assignments,col.human,col.robot,col.recovery))


@lru_cache(maxsize=100000)
def _coefficient_items(l, station, station_count, edges, assignments, human, robot, recovery):
    """Immutable cached sparse column; keys include the full graph and all values."""
    present = {i for i, _ in assignments}
    result = {("station", l, station): 1, ("human",): human,
              ("robot",): robot, ("recovery", l): -recovery}
    for i in present:
        result["task", l, i] = 1
    for e, (i, j) in enumerate(edges):
        difference=int(j in present)-int(i in present)
        if not difference:
            continue
        for k in range(station, station_count + 1):
            result["precedence", l, e, k] = difference
    return tuple((row,value) for row,value in result.items() if value)


def reduced_cost(line, station, col, duals, phase):
    objective = col.profit if phase == 2 else 0.0
    return objective - sum(duals[row] * value for row, value in coefficients(line, station, col).items())
