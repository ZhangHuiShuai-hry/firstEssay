"""Two-phase root-node column generation. Run with an existing MILP JSON instance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pulp

from common import blocks, empty_pool, compact, reduced_cost
from master import build_master, solve_master, decode_integer
from pricing import price


def recover_integer(data, pool, verbose=False):
    master = build_master(data, pool, integer=True)
    from common import cbc
    master.problem.solve(cbc(verbose=verbose, role="recovery"))
    if master.problem.status == pulp.LpStatusInfeasible:
        return {"status": "infeasible_on_generated_columns", "has_feasible_solution": False,
                "optimal": False, "objective": None}
    from common import require_optimal
    require_optimal(master.problem)
    return decode_integer(data, pool, master)


def run_cg(data, epsilon=1e-7, feasibility_tolerance=1e-7, max_iterations=1000,
           recover=True, verbose=False):
    compact.validate_data(data)
    compact.number(epsilon, "epsilon", 0, strict=True)
    compact.number(feasibility_tolerance, "feasibility_tolerance", 0, strict=True)
    compact.integer(max_iterations, "max_iterations", 1)
    pool = empty_pool(data)
    history = []
    result = {"algorithm": "two_phase_exact_pricing_CG", "status": "iteration_limit",
              "lp_converged": False, "lp_objective": None, "lp_upper_bound": None,
              "epsilon": epsilon, "feasibility_tolerance": feasibility_tolerance,
              "history": history}
    last_master = None
    for phase in (1, 2):
        for iteration in range(1, max_iterations + 1):
            master = solve_master(build_master(data, pool, phase), verbose=verbose)
            value = master.value()
            if phase == 1 and -value <= feasibility_tolerance:
                history.append({"phase": 1, "iteration": iteration, "artificial_sum": -value,
                                "objective": value, "event": "feasible_RMP_found"})
                break
            duals = master.duals()
            for line, s in blocks(data):
                for p, col in enumerate(pool[line["id"], s]):
                    rc = reduced_cost(line, s, col, duals, phase)
                    if abs(rc - master.variables[line["id"], s, p].dj) > 1e-5 or rc > 1e-5:
                        raise RuntimeError("RMP reduced costs do not match row dual prices")
            candidates = [(line, s, *price(line, s, duals, phase, verbose)) for line, s in blocks(data)]
            upper = value + sum(max(0.0, rc) for _, _, _, rc in candidates)
            best = max(rc for _, _, _, rc in candidates)
            record = {"phase": phase, "iteration": iteration, "objective": value,
                      "lp_upper_bound": upper, "maximum_reduced_cost": best,
                      "duals": [{"row": list(row), "value": dual}
                                for row, dual in duals.items()],
                      "columns_before": sum(map(len, pool.values())),
                      "pricing": [{"line": line["id"], "station": s, "reduced_cost": rc,
                                   "assignments": list(col.assignments)} for line, s, col, rc in candidates],
                      "columns_added": 0}
            if phase == 1:
                record["artificial_sum"] = -value
                record["artificials"] = [{"name": variable.name, "value": variable.value()}
                                         for variable in master.artificials]
            history.append(record)
            if phase == 2:
                last_master = master
                result.update(lp_objective=value, lp_upper_bound=upper)
            if best <= epsilon:
                if phase == 1:
                    # Full Phase I maximum is <= upper. Only certify if even this
                    # dual-repaired bound is strictly negative beyond tolerance.
                    if upper < -feasibility_tolerance:
                        result["status"] = "infeasible_full_column_LP"
                    else:
                        result["status"] = "phase_I_numerically_inconclusive"
                    result["phase_I_artificial_sum"] = -value
                    result["phase_I_lp_upper_bound"] = upper
                    result["final_duals"] = record["duals"]
                    return result, pool
                result.update(status="LP_optimal_within_tolerance", lp_converged=True)
                break
            if iteration == max_iterations:
                result["stopped_phase"] = phase
                if phase == 1:
                    result["phase_I_artificial_sum"] = -value
                    return result, pool
                break
            for line, s, col, rc in candidates:
                if rc > epsilon:
                    columns = pool[line["id"], s]
                    if any(old.assignments == col.assignments for old in columns):
                        raise RuntimeError("Positive reduced cost for an existing column; "
                                           "check numerical tolerances")
                    columns.append(col)
                    record["columns_added"] += 1
        if phase == 2:
            break
    result["column_counts"] = [{"line": l, "station": s, "count": len(cols)}
                               for (l, s), cols in pool.items()]
    if last_master is not None:
        result["lp_solution"] = [
            {"line": l, "station": s, "column": p, "weight": variable.value(),
             "assignments": list(pool[l, s][p].assignments)}
            for (l, s, p), variable in last_master.variables.items() if variable.value() > 1e-8]
        result["final_duals"] = [{"row": list(row), "value": value}
                                 for row, value in last_master.duals().items()]
        if recover:
            integer = recover_integer(data, pool, verbose)
            result["integer_recovery"] = integer
            if integer["has_feasible_solution"]:
                result["integer_upper_bound_gap"] = max(0, result["lp_upper_bound"] - integer["objective"])
    return result, pool


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--epsilon", type=float, default=1e-7)
    parser.add_argument("--max-iterations", type=int, default=1000, help="Maximum RMP solves per phase")
    parser.add_argument("--no-integer", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--solver", choices=("cbc", "cplex_py"), default="cbc")
    parser.add_argument("--verify", action="store_true", help="Tiny instances only: enumerate all columns")
    parser.add_argument("--enumeration-limit", type=int, default=100000)
    args = parser.parse_args()
    try:
        data = json.loads(args.instance.read_text(encoding="utf-8-sig"))
        from solver_backend import BackendConfig, use_backend
        with use_backend(BackendConfig(name=args.solver)):
            result, pool = run_cg(data, args.epsilon, max_iterations=args.max_iterations,
                                  recover=not args.no_integer, verbose=args.verbose)
            if args.verify:
                from verify import cross_validate
                result["verification"] = cross_validate(data, result, args.enumeration_limit)
        rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        verified = not args.verify or result["verification"]["passed"]
        return 0 if result["lp_converged"] and verified else 2
    except (ValueError, RuntimeError, OSError, pulp.PulpSolverError) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
