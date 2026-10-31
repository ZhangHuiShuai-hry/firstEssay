"""Small-instance exhaustive verifier for two-phase column generation.

Unlike the initial verify.py, an inconclusive or prematurely stopped CG run
never sets passed=True. This module does not alter the original MILP or CG.

Requires the same package layout/dependencies as common.py, master.py and solve.py.
"""

import math
import pulp

from common import compact, enumerate_pool, cbc, require_optimal
from master import build_master, decode_integer


def _solve_and_status(problem, mip):
    problem.solve(cbc(mip=mip))
    if problem.status == pulp.LpStatusInfeasible:
        return False
    require_optimal(problem)
    return True


def _objective(problem):
    val = pulp.value(problem.objective)
    if val is None or not math.isfinite(float(val)):
        raise RuntimeError("Missing or nonfinite optimal objective")
    return float(val)


def cross_validate(data, cg_result, enumeration_limit=100000, tolerance=1e-5):
    """Validate compact-vs-full models AND the reported CG termination.

    Return passed=False if CG is incomplete or numerically inconclusive.
    A model cross-check is reported separately as model_consistency_passed.
    """
    compact.validate_data(data)
    pool = enumerate_pool(data, enumeration_limit)
    full_lp = build_master(data, pool)
    full_ip = build_master(data, pool, integer=True)
    original = compact.build_model(data)
    relaxed = compact.build_model(data)
    for variable in relaxed.problem.variables():
        variable.cat = pulp.LpContinuous

    lp_feasible = _solve_and_status(full_lp.problem, mip=False)
    ip_feasible = _solve_and_status(full_ip.problem, mip=True)
    original_feasible = _solve_and_status(original.problem, mip=True)
    compact_lp_feasible = _solve_and_status(relaxed.problem, mip=False)

    if ip_feasible != original_feasible:
        raise RuntimeError("Full-column IP and compact MILP feasibility differ")
    if ip_feasible and not lp_feasible:
        raise RuntimeError("Full-column IP feasible but full-column LP infeasible")
    if original_feasible and not compact_lp_feasible:
        raise RuntimeError("Compact MILP feasible but its LP relaxation infeasible")
    if lp_feasible and not compact_lp_feasible:
        raise RuntimeError("DW LP feasible but compact LP infeasible")

    report = {
        "passed": False,
        "model_consistency_passed": True,
        "cg_verified": False,
        "cg_status": cg_result.get("status"),
        "full_column_counts": [
            {"line": l, "station": s, "count": len(cols)}
            for (l, s), cols in pool.items()
        ],
        "full_lp_feasible": lp_feasible,
        "full_ip_feasible": ip_feasible,
        "compact_ip_feasible": original_feasible,
        "compact_lp_feasible": compact_lp_feasible,
        "full_lp_objective": full_lp.value() if lp_feasible else None,
        "cg_vs_full_lp_checked": False,
    }

    if lp_feasible:
        dw_lp_value = full_lp.value()
        compact_lp_value = _objective(relaxed.problem)
        if dw_lp_value > compact_lp_value + tolerance:
            raise RuntimeError("DW LP upper bound exceeds compact LP upper bound")
        report["compact_lp_objective"] = compact_lp_value

    if ip_feasible:
        decode_integer(data, pool, full_ip)
        ip_value = full_ip.value()
        compact_report = compact.solution_report(original)
        if not compact_report.get("has_feasible_solution"):
            raise RuntimeError("Compact MILP solution report rejected an optimal solution")
        if abs(ip_value - compact_report["objective"]) > tolerance:
            raise RuntimeError("Full-column IP differs from compact MILP")
        if ip_value > full_lp.value() + tolerance:
            raise RuntimeError("Full-column IP exceeds DW LP relaxation")
        report.update(full_ip_objective=ip_value,
                      compact_ip_objective=compact_report["objective"],
                      decoded_original_constraints_valid=True)

    status = cg_result.get("status")
    converged = bool(cg_result.get("lp_converged"))
    if converged:
        if status != "LP_optimal_within_tolerance":
            raise RuntimeError("CG claims convergence with inconsistent status")
        if not lp_feasible:
            raise RuntimeError("CG claims LP convergence but full-column LP is infeasible")
        value = cg_result.get("lp_objective")
        if value is None or abs(value - full_lp.value()) > tolerance:
            raise RuntimeError("CG LP differs from full-column LP")
        upper = cg_result.get("lp_upper_bound")
        if upper is not None and upper + tolerance < full_lp.value():
            raise RuntimeError("Reported CG LP upper bound is invalid")
        report.update(passed=True, cg_verified=True,
                      cg_vs_full_lp_checked=True,
                      cg_lp_objective=value)
    elif status == "infeasible_full_column_LP":
        if lp_feasible:
            raise RuntimeError("CG incorrectly declared the full-column LP infeasible")
        report.update(passed=True, cg_verified=True,
                      cg_infeasibility_checked=True)
    else:
        report["reason"] = (
            "CG has not established full-column LP optimality or infeasibility; "
            "the model-to-model checks alone do not verify CG convergence"
        )

    return report
