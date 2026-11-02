"""Exact station MILP pricing with distinct Phase I and Phase II objectives."""
import math

import pulp

from common import make_column, reduced_cost, cbc, require_optimal, PricingResult


def price(line, station, duals, phase=2, verbose=False):
    problem = pulp.LpProblem("DW_pricing", pulp.LpMaximize)
    l = line["id"]
    z = {(t["id"], m): pulp.LpVariable(f"z_{i}_{m}", cat="Binary")
         for i, t in enumerate(line["tasks"]) for m in t["modes"]}
    u, h, r = [pulp.LpVariable(name, cat="Binary") for name in ("u", "h", "r")]
    n = len(line["tasks"])
    sigma = {t["id"]: 0.0 for t in line["tasks"]}
    for e, (i, j) in enumerate(line.get("precedence", [])):
        suffix = sum(duals["precedence", l, e, k] for k in range(station, len(line["stations"]) + 1))
        sigma[i] += suffix
        sigma[j] -= suffix
    objective, duration, fatigue, nh, nr = [pulp.LpAffineExpression() for _ in range(5)]
    for task in line["tasks"]:
        i = task["id"]
        problem += pulp.lpSum(z[i, m] for m in task["modes"]) <= 1
        for m, params in task["modes"].items():
            variable = z[i, m]
            reward = (task["value"] - params["cost"]) if phase == 2 else 0.0
            reward += -duals["task", l, i] + duals["recovery", l] * task.get("weight", 0) + sigma[i]
            objective += reward * variable
            duration += params["time"] * variable
            fatigue += params["time"] * params["beta"] * variable
            nh += int(m in ("H", "J")) * variable
            nr += int(m in ("R", "J")) * variable
    costs = line["stations"][station - 1]
    objective -= (costs["fixed_cost"] if phase == 2 else 0) * u
    objective -= ((costs["human_cost"] if phase == 2 else 0) + duals["human",]) * h
    objective -= ((costs["robot_cost"] if phase == 2 else 0) + duals["robot",]) * r
    objective -= duals["station", l, station]
    problem += objective
    count = pulp.lpSum(z.values())
    problem += duration <= line["cycle_time"] * u
    for variable, total in ((u, count), (h, nh), (r, nr)):
        problem += variable <= total
        problem += total <= n * variable
    problem += fatigue <= -math.log1p(-line["fatigue_limit"]) * h
    # No global resource limit, required task, recovery or predecessor-closure constraints here.
    problem.solve(cbc(verbose=verbose, role="pricing"))
    require_optimal(problem)
    col = make_column(line, station, [key for key, variable in z.items() if variable.value() > 0.5])
    rc = reduced_cost(line, station, col, duals, phase)
    value = pulp.value(objective)
    if value is None:
        value = objective.constant  # possible identically-zero objective with solver dummy
    if abs(rc - value) > 1e-5:
        raise RuntimeError("Pricing objective disagrees with explicit column reduced cost")
    return PricingResult(col, rc, dict(getattr(problem, "backend_result", {})))
