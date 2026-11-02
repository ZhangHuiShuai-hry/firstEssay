"""Two-phase root-node column generation. Run with an existing MILP JSON instance."""
from __future__ import annotations

import argparse
import json
import time
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
                "optimal": False, "objective": None, "restricted_master_optimal": False,
                "restricted_master_infeasible_proven": True, "original_integer_optimal_proven": False}
    from common import require_optimal
    require_optimal(master.problem)
    report = decode_integer(data, pool, master)
    report.update(restricted_master_optimal=True, original_integer_optimal_proven=False,
                  restricted_master_infeasible_proven=False,
                  solver_result=getattr(master.problem, "backend_result", {}))
    return report


def _primal_snapshot(master, pool):
    return [{"line": l, "station": s, "column": p, "weight": v.value(),
             "assignments": list(pool[l, s][p].assignments)}
            for (l, s, p), v in master.variables.items() if v.value() > 1e-10]


def _failure(result, pool, error, role):
    """Keep exception behavior for experiment adapters; preserve auditable evidence."""
    info = getattr(error, "solver_result", {})
    status = info.get("status")
    if isinstance(error, TimeoutError) or status in ("time_limit", "pricing_time_limit"):
        proof = "pricing_time_limit" if role == "pricing" else "lp_feasible_unproven"
    elif status == "infeasible" and role == "pricing":
        proof = "pricing_infeasible"  # empty column makes this a model/solver anomaly
    elif status in ("feasible_unproven", "not_solved", "unproven"):
        proof = "lp_feasible_unproven"
    elif isinstance(error, pulp.PulpSolverError):
        proof = "solver_error"
    else:
        proof = "numerical_uncertain" if isinstance(error, RuntimeError) else "solver_error"
    result.update(status=proof, lp_converged=False, certificate_status=proof, termination_reason=f"{role}: {error}",
                  failed_role=role, failed_solver_result=info)
    error.cg_result = result
    error.cg_pool = pool


def run_cg(data, epsilon=1e-7, feasibility_tolerance=1e-7, max_iterations=1000,
           recover=True, verbose=False):
    compact.validate_data(data)
    compact.number(epsilon, "epsilon", 0, strict=True)
    compact.number(feasibility_tolerance, "feasibility_tolerance", 0, strict=True)
    compact.integer(max_iterations, "max_iterations", 1)
    pool = empty_pool(data)
    history = []
    result = {"algorithm": "two_phase_exact_pricing_CG", "status": "iteration_limit",
              "certificate_version": 2, "certificate_status": "numerical_uncertain",
              "full_lp_feasible_established": False,
              "proof_scope": "full_column_LP_with_floating_point_tolerances",
              "termination_reason": "iteration_limit",
              "lp_converged": False, "lp_objective": None, "lp_upper_bound": None,
              "epsilon": epsilon, "feasibility_tolerance": feasibility_tolerance,
              "history": history}
    last_master = None
    for phase in (1, 2):
        for iteration in range(1, max_iterations + 1):
            try:
                master = solve_master(build_master(data, pool, phase), verbose=verbose)
            except Exception as error:
                _failure(result, pool, error, "rmp")
                raise
            value = master.value()
            if phase == 2:
                result.update(lp_objective=value, full_lp_feasible_established=True,
                              certificate_status="lp_feasible_unproven")
            if phase == 1 and -value <= feasibility_tolerance:
                result["full_lp_feasible_established"] = True
                history.append({"phase": 1, "iteration": iteration, "artificial_sum": -value,
                                "objective": value, "event": "feasible_RMP_found"})
                break
            duals = master.duals()
            for line, s in blocks(data):
                for p, col in enumerate(pool[line["id"], s]):
                    rc = reduced_cost(line, s, col, duals, phase)
                    if abs(rc - master.variables[line["id"], s, p].dj) > 1e-5 or rc > 1e-5:
                        raise RuntimeError("RMP reduced costs do not match row dual prices")
            record = {"phase": phase, "iteration": iteration, "objective": value,
                      "rmp_status": "optimal", "complete_pricing": False, "pricing": [],
                      "duals": [{"row": list(row), "value": dual} for row, dual in duals.items()],
                      "rmp_solution": _primal_snapshot(master, pool),
                      "columns_before": sum(map(len, pool.values())), "columns_added": 0}
            if phase == 1:
                required_rows = [key for key,row in master.rows.items()
                                 if (key[0] == "task" and row.sense == 0) or key[0] == "recovery"]
                record["artificial_rows"] = [{"row": list(key), "value": v.value()}
                                             for key,v in zip(required_rows,master.artificials)]
            history.append(record)
            candidates = []
            for line, s in blocks(data):
                tick = time.perf_counter()
                try:
                    answer = price(line, s, duals, phase, verbose)
                    col, rc = answer
                    info = getattr(answer, "certificate", {})
                    if info and info.get("optimal") is not True:
                        error = RuntimeError("Pricing metadata does not prove optimality")
                        error.solver_result = info
                        raise error
                except Exception as error:
                    info = getattr(error, "solver_result", {})
                    record["pricing"].append({"line": line["id"], "station": s,
                        "status": "time_limit" if isinstance(error,TimeoutError) else info.get("status","solver_error"),
                        "optimal": False, "solver_result": info, "solve_seconds": time.perf_counter()-tick})
                    _failure(result, pool, error, "pricing")
                    raise
                info = getattr(answer, "certificate", {})
                # Legacy adapters return plain pairs only after an exact solve.
                # rc is a proven maximum under that contract, never a truncated incumbent.
                record["pricing"].append({"line": line["id"], "station": s, "reduced_cost": rc,
                    "assignments": list(col.assignments), "status": "optimal", "optimal": True,
                    "incumbent": rc, "best_bound": info.get("best_bound",rc),
                    "solve_seconds": time.perf_counter()-tick, "solver_result": info,
                    "evidence_source": "solver_metadata" if info else "exact_adapter_contract"})
                candidates.append((line, s, col, rc))
            upper = value + sum(max(0.0, rc) for _, _, _, rc in candidates)
            best = max(rc for _, _, _, rc in candidates)
            record.update(lp_upper_bound=upper, maximum_reduced_cost=best, complete_pricing=True,
                          lp_lower_bound=value, lp_gap=max(0.,upper-value),
                          upper_bound_source="proven_optimal_pricing_maxima")
            if phase == 1:
                record["artificial_sum"] = -value
                record["artificials"] = [{"name": variable.name, "value": variable.value()}
                                         for variable in master.artificials]
            if phase == 2:
                last_master = master
                result.update(lp_objective=value, lp_upper_bound=upper,
                              certificate_status="lp_feasible_unproven", full_lp_feasible_established=True)
            if best <= epsilon:
                if phase == 1:
                    # Full Phase I maximum is <= upper. Only certify if even this
                    # dual-repaired bound is strictly negative beyond tolerance.
                    if upper < -feasibility_tolerance:
                        result["status"] = "infeasible_full_column_LP"
                        result["certificate_status"] = "phase1_infeasible_proven"
                    else:
                        result["status"] = "phase_I_numerically_inconclusive"
                        result["certificate_status"] = "numerical_uncertain"
                    result["termination_reason"] = result["status"]
                    result["phase_I_artificial_sum"] = -value
                    result["phase_I_lp_upper_bound"] = upper
                    result["final_duals"] = record["duals"]
                    return result, pool
                result.update(status="LP_optimal_within_tolerance", lp_converged=True,
                              certificate_status="lp_optimal_proven", termination_reason="complete_exact_pricing")
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
            try:
                integer = recover_integer(data, pool, verbose)
            except Exception as error:
                result["integer_recovery"] = {"status": "solver_error", "error": str(error),
                    "has_feasible_solution": False, "restricted_master_optimal": False,
                    "original_integer_optimal_proven": False, "optimal": False}
                # An integer recovery error does not invalidate the completed LP proof.
                error.cg_result, error.cg_pool = result, pool
                raise
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
    except Exception as error:
        if args.output and hasattr(error, "cg_result"):
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(error.cg_result, ensure_ascii=False, indent=2,
                                             allow_nan=False) + "\n", encoding="utf-8")
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
