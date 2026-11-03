"""Restricted/full column master (LP or integer); explicit Phase I artificials."""
from dataclasses import dataclass
import math

import pulp

from common import blocks, coefficients, cbc, require_optimal, compact


@dataclass
class Master:
    problem: pulp.LpProblem
    variables: dict
    rows: dict
    artificials: list
    objective: pulp.LpAffineExpression
    phase: int

    def duals(self):
        return {key: row.pi for key, row in self.rows.items()}

    def value(self):
        # PuLP may attach an unassigned zero-coefficient dummy to a constant objective.
        return float(self.objective.constant + sum(coef * variable.value()
                     for variable, coef in self.objective.items() if coef != 0))


def build_master(data, pool, phase=2, integer=False):
    if phase not in (1, 2) or (integer and phase == 1):
        raise ValueError("Use phase 1/2; integer recovery is phase 2 only")
    problem = pulp.LpProblem("DW_master", pulp.LpMaximize)
    variables, expressions, row_specs, rows, artificials = {}, {}, {}, {}, []
    for line, s in blocks(data):
        row_specs["station", line["id"], s] = ("=", 1)
    for line in data["lines"]:
        l = line["id"]
        required = set(line.get("required_tasks", []))
        for task in line["tasks"]:
            row_specs["task", l, task["id"]] = ("=" if task["id"] in required else "<=", 1)
        for e, _ in enumerate(line.get("precedence", [])):
            for k in range(1, len(line["stations"]) + 1):
                row_specs["precedence", l, e, k] = ("<=", 0)
        row_specs["recovery", l] = ("<=", -line.get("min_recovery", 0))
    row_specs["human",] = ("<=", data["human_limit"])
    row_specs["robot",] = ("<=", data["robot_limit"])
    expressions = {row: pulp.LpAffineExpression() for row in row_specs}
    profit = pulp.LpAffineExpression()
    for bi, (line, s) in enumerate(blocks(data)):
        l = line["id"]
        for p, col in enumerate(pool[l, s]):
            # No LP upper bound: convexity implies <=1; extra bounds obscure pricing duals.
            variable = pulp.LpVariable(f"lambda_{bi}_{p}", lowBound=0,
                                       cat="Binary" if integer else "Continuous")
            variables[l, s, p] = variable
            if col.profit:
                profit.addterm(variable,col.profit)
            for row, value in coefficients(line, s, col).items():
                if value:
                    expressions[row].addterm(variable,value)
    for ri, (key, (sense, rhs)) in enumerate(row_specs.items()):
        expression = expressions[key]
        if phase == 1 and ((key[0] == "task" and sense == "=") or key[0] == "recovery"):
            artificial = pulp.LpVariable(f"artificial_{ri}", lowBound=0)
            artificials.append(artificial)
            expression += artificial if key[0] == "task" else -artificial
        row = expression == rhs if sense == "=" else expression <= rhs
        problem += row, f"{key[0]}_{ri}"
        rows[key] = row
    objective = -pulp.lpSum(artificials) if phase == 1 else profit
    problem += objective
    return Master(problem, variables, rows, artificials, objective, phase)


def solve_master(master, integer=False, verbose=False):
    master.problem.solve(cbc(mip=integer, verbose=verbose, role="rmp" if not integer else "recovery"))
    require_optimal(master.problem)
    if not integer:
        duals = master.duals()
        if any(v is None or not math.isfinite(v) for v in duals.values()):
            raise RuntimeError("LP solver did not return finite dual prices")
        for key, row in master.rows.items():
            if row.sense == pulp.LpConstraintLE and duals[key] < -1e-6:
                raise RuntimeError("Unexpected maximization LP dual sign")
    return master


def decode_integer(data, pool, master):
    """Recover all original variables and verify against the unchanged compact MILP."""
    original = compact.build_model(data)
    for variable in original.problem.variables():
        variable.varValue = 0
    for line, s in blocks(data):
        l = line["id"]
        chosen = [col for p, col in enumerate(pool[l, s]) if master.variables[l, s, p].value() > 0.5]
        if len(chosen) != 1:
            raise RuntimeError("Integer master must select exactly one column per station")
        col = chosen[0]
        original.u[l, s].varValue = col.active
        original.h[l, s].varValue = col.human
        original.r[l, s].varValue = col.robot
        for i, m in col.assignments:
            original.x[l, i, s, m].varValue = 1
            original.y[l, i].varValue = 1
    if not original.problem.valid(1e-6):
        raise RuntimeError("Decoded integer solution violates original MILP")
    original.problem.status = pulp.LpStatusOptimal
    original.problem.sol_status = pulp.LpSolutionIntegerFeasible
    report = compact.solution_report(original)
    if abs(report["objective"] - master.value()) > 1e-5:
        raise RuntimeError("Decoded profit differs from column objective")
    report["status"] = "Feasible"
    report["optimal"] = False
    report["scope"] = "restricted_column_integer_recovery"
    return report
