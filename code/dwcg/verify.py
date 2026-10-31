"""Small-instance model consistency and CG termination verification.

Incomplete CG runs return an inconclusive report, never passed=True.
Contradictory claims, invalid bounds and nonfinite values raise RuntimeError.
"""
import math

import pulp

from common import compact, enumerate_pool, cbc, require_optimal, coefficients
from master import build_master, decode_integer


def _finite(value, label):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)):
        raise RuntimeError(f"{label} must be a finite number")
    return float(value)


def _objective(problem):
    """Evaluate nonzero terms explicitly; ignore PuLP's zero-coefficient dummy.

    Do not turn a missing value for a real objective term into a zero objective.
    """
    expression = problem.objective
    if expression is None:
        raise RuntimeError("Missing optimal objective expression")
    total = _finite(expression.constant, "Objective constant")
    for variable, coefficient in expression.items():
        coefficient = _finite(coefficient, "Objective coefficient")
        if coefficient != 0:
            total += coefficient * _finite(variable.value(), f"Objective variable {variable.name}")
    return _finite(total, "Optimal objective")


def _solve_and_status(problem, mip):
    problem.solve(cbc(mip=mip))
    if problem.status == pulp.LpStatusInfeasible:
        return False
    require_optimal(problem)
    return True


def _check_cg_bounds(cg_result, full_lp_value, tolerance):
    """Check every available Phase II bound, including truncated runs/history.

    Phase I has a different objective, so its bounds are never compared against
    the profit optimum. Its reported numbers must still be finite and ordered.
    """
    checked = 0

    def check_pair(record, label, profit_phase):
        nonlocal checked
        lower = record.get("lp_objective" if label == "CG" else "objective")
        upper = record.get("lp_upper_bound")
        if lower is not None:
            lower = _finite(lower, f"{label} objective")
        if upper is not None:
            upper = _finite(upper, f"{label} LP upper bound")
        if lower is not None and upper is not None and lower > upper + tolerance:
            raise RuntimeError(f"{label} objective exceeds its LP upper bound")
        if profit_phase and (lower is not None or upper is not None):
            if full_lp_value is None:
                raise RuntimeError(f"{label} reports a feasible profit LP but full-column LP is infeasible")
            if lower is not None and lower > full_lp_value + tolerance:
                raise RuntimeError(f"{label} RMP objective exceeds full-column LP optimum")
            if upper is not None:
                if upper + tolerance < full_lp_value:
                    raise RuntimeError(f"{label} LP upper bound is below full-column LP optimum")
                checked += 1

    check_pair(cg_result, "CG", True)
    history = cg_result.get("history", [])
    if not isinstance(history, list):
        raise RuntimeError("CG history must be a list")
    for index, record in enumerate(history):
        if not isinstance(record, dict) or record.get("phase") not in (1, 2):
            raise RuntimeError("CG history contains an invalid phase record")
        label = f"CG history[{index}]"
        check_pair(record, label, record["phase"] == 2)
        for field in ("maximum_reduced_cost", "artificial_sum"):
            if record.get(field) is not None:
                _finite(record[field], f"{label} {field}")
        pricing_records = record.get("pricing", [])
        if not isinstance(pricing_records, list) or any(not isinstance(p, dict) for p in pricing_records):
            raise RuntimeError(f"{label} pricing must be a list of objects")
        for pricing in pricing_records:
            if pricing.get("reduced_cost") is None:
                continue  # The certificate validator reports missing required fields.
            _finite(pricing.get("reduced_cost"), f"{label} pricing reduced cost")
    return checked


class _MissingCertificate(Exception):
    """An absent witness is inconclusive; a contradictory witness is an error."""


def _required(record, key, label):
    if key not in record or record[key] is None:
        raise _MissingCertificate(f"Missing {label}.{key}")
    return record[key]


def _close(left, right, tolerance, label):
    if abs(left - right) > tolerance:
        raise RuntimeError(f"{label} mismatch: {left} vs {right}")


def _read_duals(entries, master, tolerance):
    if not isinstance(entries, list):
        raise RuntimeError("Certificate duals must be a list")
    duals = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise RuntimeError("Invalid dual certificate entry")
        row = _required(entry, "row", "dual")
        if not isinstance(row, (list, tuple)) or any(not isinstance(v, (str, int)) or isinstance(v, bool) for v in row):
            raise RuntimeError("Invalid dual row key")
        row = tuple(row)
        if row not in master.rows or row in duals:
            raise RuntimeError("Unknown or duplicate dual row")
        duals[row] = _finite(_required(entry, "value", "dual"), "Certificate dual value")
        if master.rows[row].sense == pulp.LpConstraintLE and duals[row] < -tolerance:
            raise RuntimeError("Invalid dual sign for a <= row")
    if duals.keys() != master.rows.keys():
        raise _MissingCertificate("Dual certificate does not cover every RMP row")
    if master.phase == 1:
        required_tasks = {row for row, constraint in master.rows.items()
                          if row[0] == "task" and constraint.sense == pulp.LpConstraintEQ}
        if any(duals[row] < -1 - tolerance for row in required_tasks):
            raise RuntimeError("Phase I dual violates a required-task artificial constraint")
        if any(duals[row] > 1 + tolerance for row in duals if row[0] == "recovery"):
            raise RuntimeError("Phase I dual violates a recovery artificial constraint")
    return duals


def _termination_certificate(data, pool, cg_result, master, phase, tolerance):
    """Independently enumerate c_p - dual*A_p using the saved final RMP duals.

    master is the full-column oracle for the same phase. Its row definitions
    match the RMP, but its own optimal dual solution is deliberately NOT used.
    """
    history = cg_result.get("history", [])
    if not history:
        raise _MissingCertificate(f"Missing final Phase {phase} history record")
    record = history[-1]
    if record.get("phase") != phase:
        raise _MissingCertificate(f"Last history record is not Phase {phase}")
    epsilon = _finite(_required(cg_result, "epsilon", "CG"), "CG epsilon")
    if epsilon <= 0:
        raise RuntimeError("CG epsilon must be positive")
    objective = _finite(_required(record, "objective", "last record"), "Final RMP objective")
    upper = _finite(_required(record, "lp_upper_bound", "last record"), "Final RMP upper bound")
    maximum = _finite(_required(record, "maximum_reduced_cost", "last record"), "Final maximum reduced cost")
    if maximum > epsilon + tolerance:
        raise RuntimeError("Termination certificate has a positive reduced cost above epsilon")
    if phase == 2:
        _close(objective, _finite(cg_result["lp_objective"], "CG objective"), tolerance, "Final RMP objective")
        _close(upper, _finite(cg_result["lp_upper_bound"], "CG upper bound"), tolerance, "Final RMP upper bound")
    duals = _read_duals(_required(record, "duals", "last record"), master, tolerance)
    final_duals = _read_duals(_required(cg_result, "final_duals", "CG"), master, tolerance)
    for row in duals:
        _close(duals[row], final_duals[row], tolerance, "Final vs last-record dual")
    dual_objective = _finite(sum(-master.rows[row].constant * value for row, value in duals.items()),
                             "RMP dual objective")
    _close(objective, dual_objective, tolerance, "Final RMP primal/dual objective")
    pricing = _required(record, "pricing", "last record")
    if not isinstance(pricing, list):
        raise RuntimeError("Final pricing certificate must be a list")
    reported = {}
    for entry in pricing:
        if not isinstance(entry, dict):
            raise RuntimeError("Invalid pricing certificate entry")
        line = _required(entry, "line", "pricing")
        station = _required(entry, "station", "pricing")
        if not isinstance(line, str) or isinstance(station, bool) or not isinstance(station, int):
            raise RuntimeError("Invalid pricing station key")
        key = (line, station)
        if key not in pool or key in reported:
            raise RuntimeError("Unknown or duplicate station in final pricing certificate")
        reported[key] = _finite(_required(entry, "reduced_cost", "pricing"), "Final station reduced cost")
    if reported.keys() != pool.keys():
        raise _MissingCertificate("Final pricing certificate does not cover every station")
    maxima, details = [], []
    for line in data["lines"]:
        l = line["id"]
        for s in range(1, len(line["stations"]) + 1):
            values = []
            for col in pool[l, s]:
                objective_coefficient = col.profit if phase == 2 else 0.0
                values.append(objective_coefficient - sum(
                    duals[row] * value for row, value in coefficients(line, s, col).items()))
            rho = _finite(max(values), "Enumerated maximum reduced cost")
            _close(rho, reported[l, s], tolerance, f"Pricing vs enumeration at {(l, s)}")
            if rho > epsilon + tolerance:
                raise RuntimeError("Enumerated column violates the termination certificate")
            maxima.append(rho)
            details.append({"line": l, "station": s, "reported": reported[l, s], "enumerated": rho})
    _close(max(reported.values()), maximum, tolerance, "Reported maximum reduced cost")
    _close(max(maxima), maximum, tolerance, "Enumerated maximum reduced cost")
    repaired_upper = objective + sum(max(0.0, rho) for rho in maxima)
    _close(repaired_upper, upper, tolerance, "Dual-repaired LP upper bound")
    details_report = {"phase": phase, "station_reduced_costs": details,
                      "maximum_reduced_cost": max(maxima), "dual_objective": dual_objective,
                      "recomputed_upper_bound": repaired_upper}
    if phase == 1:
        feasibility = _finite(_required(cg_result, "feasibility_tolerance", "CG"), "Feasibility tolerance")
        if feasibility <= 0:
            raise RuntimeError("Feasibility tolerance must be positive")
        artificial_sum = _finite(_required(record, "artificial_sum", "last record"), "Artificial sum")
        _close(artificial_sum, _finite(_required(cg_result, "phase_I_artificial_sum", "CG"),
                                     "CG artificial sum"), tolerance, "Phase I artificial sum")
        _close(upper, _finite(_required(cg_result, "phase_I_lp_upper_bound", "CG"),
                             "CG Phase I upper bound"), tolerance, "Final Phase I upper bound")
        artificials = _required(record, "artificials", "last record")
        if not isinstance(artificials, list):
            raise RuntimeError("Artificial certificate must be a list")
        expected = {variable.name for variable in master.artificials}
        actual = {}
        for entry in artificials:
            if not isinstance(entry, dict):
                raise RuntimeError("Invalid artificial certificate entry")
            name = _required(entry, "name", "artificial")
            if not isinstance(name, str) or name not in expected or name in actual:
                raise RuntimeError("Unknown or duplicate artificial variable")
            value = _finite(_required(entry, "value", "artificial"), "Artificial value")
            if value < -tolerance:
                raise RuntimeError("Negative artificial variable")
            actual[name] = value
        if actual.keys() != expected:
            raise _MissingCertificate("Artificial certificate does not cover every artificial variable")
        _close(sum(actual.values()), artificial_sum, tolerance, "Artificial component sum")
        _close(objective, -artificial_sum, tolerance, "Negative Phase I artificial objective")
        if artificial_sum <= feasibility or upper >= -feasibility:
            raise RuntimeError("Phase I artificial/upper-bound certificate does not prove infeasibility")
        # The dual repair gives a full Phase I upper bound, independently of CG.
        full_value = _objective(master.problem)
        if full_value > upper + tolerance:
            raise RuntimeError("Phase I upper bound is below the full Phase I optimum")
        _close(full_value, objective, tolerance, "Phase I RMP vs full Phase I optimum")
        details_report.update(artificial_sum=artificial_sum, full_phase_I_objective=full_value)
    return details_report


def cross_validate(data, cg_result, enumeration_limit=100000, tolerance=1e-5):
    """Compare models independently, then verify the reported CG conclusion.

    passed = model_consistency_passed AND cg_verified. Iteration limits and
    inconclusive Phase I runs leave model checks intact but passed=False.
    """
    compact.validate_data(data)
    compact.number(tolerance, "tolerance", 0, strict=True)
    if not isinstance(cg_result, dict) or not isinstance(cg_result.get("lp_converged"), bool):
        raise RuntimeError("CG result must contain a boolean lp_converged")
    pool = enumerate_pool(data, enumeration_limit)
    full_lp = build_master(data, pool)
    full_ip = build_master(data, pool, integer=True)
    original = compact.build_model(data)
    relaxed = compact.build_model(data)
    for variable in relaxed.problem.variables():
        variable.cat = pulp.LpContinuous
    lp_feasible = _solve_and_status(full_lp.problem, False)
    ip_feasible = _solve_and_status(full_ip.problem, True)
    original_feasible = _solve_and_status(original.problem, True)
    compact_lp_feasible = _solve_and_status(relaxed.problem, False)
    if ip_feasible != original_feasible:
        raise RuntimeError("Full column IP and compact MILP feasibility differ")
    if ip_feasible and not lp_feasible:
        raise RuntimeError("Full column IP feasible but its LP is infeasible")
    if original_feasible and not compact_lp_feasible:
        raise RuntimeError("Compact MILP feasible but its LP is infeasible")
    if lp_feasible and not compact_lp_feasible:
        raise RuntimeError("Full column LP feasible but compact LP is infeasible")
    lp_value = _objective(full_lp.problem) if lp_feasible else None
    compact_lp_value = _objective(relaxed.problem) if compact_lp_feasible else None
    report = {"passed": False, "model_consistency_passed": True, "cg_verified": False,
              "verification_status": "inconclusive", "cg_status": cg_result.get("status"),
              "full_column_counts": [len(cols) for cols in pool.values()],
              "full_lp_feasible": lp_feasible, "full_ip_feasible": ip_feasible,
              "compact_ip_feasible": original_feasible, "compact_lp_feasible": compact_lp_feasible,
              "full_lp_objective": lp_value, "compact_lp_objective": compact_lp_value,
              "cg_vs_full_lp_checked": False, "cg_infeasibility_checked": False,
              "optimal_objective_cross_validated": False,
              "termination_certificate_verified": False,
              "pricing_termination_certificate_verified": False,
              "phase_I_infeasibility_certificate_verified": False,
              "certificate_status": "not_checked",
              "lp_relaxation_bound_checked": False}
    # The LP comparison remains meaningful even when both integer models are infeasible.
    if lp_feasible:
        if lp_value > compact_lp_value + tolerance:
            raise RuntimeError("DW LP upper bound exceeds compact LP upper bound")
        report["lp_relaxation_bound_checked"] = True
    if ip_feasible:
        decode_integer(data, pool, full_ip)
        compact_report = compact.solution_report(original)
        if not compact_report.get("has_feasible_solution"):
            raise RuntimeError("Compact MILP solution report rejected an optimal solution")
        ip_value = _objective(full_ip.problem)
        compact_value = _finite(compact_report["objective"], "Compact MILP profit")
        if abs(ip_value - compact_value) > tolerance:
            raise RuntimeError("Full column IP differs from compact MILP")
        if ip_value > lp_value + tolerance:
            raise RuntimeError("Full column IP exceeds DW LP relaxation")
        report.update(full_ip_objective=ip_value, compact_ip_objective=compact_value,
                      decoded_original_constraints_valid=True)
    report["cg_lp_upper_bounds_checked"] = _check_cg_bounds(cg_result, lp_value, tolerance)
    status = cg_result.get("status")
    converged = cg_result["lp_converged"]
    if converged != (status == "LP_optimal_within_tolerance"):
        raise RuntimeError("CG convergence flag and status are inconsistent")
    if converged:
        if not lp_feasible:
            raise RuntimeError("CG claims convergence but full column LP is infeasible")
        value = _finite(cg_result.get("lp_objective"), "CG optimal objective")
        _finite(cg_result.get("lp_upper_bound"), "CG final LP upper bound")
        if abs(value - lp_value) > tolerance:
            raise RuntimeError("CG LP differs from full column LP")
        report.update(cg_vs_full_lp_checked=True, optimal_objective_cross_validated=True,
                      cg_lp_objective=value)
        try:
            certificate = _termination_certificate(data, pool, cg_result, full_lp, 2, tolerance)
        except _MissingCertificate as error:
            report.update(certificate_status="missing", reason=str(error))
        else:
            report.update(cg_verified=True, termination_certificate_verified=True,
                          pricing_termination_certificate_verified=True,
                          certificate_status="verified", termination_certificate=certificate)
    elif status == "infeasible_full_column_LP":
        if lp_feasible:
            raise RuntimeError("CG incorrectly declared full LP infeasible")
        report["cg_infeasibility_checked"] = True
        full_phase_I = build_master(data, pool, phase=1)
        if not _solve_and_status(full_phase_I.problem, False):
            raise RuntimeError("Artificial Phase I oracle unexpectedly infeasible")
        try:
            certificate = _termination_certificate(data, pool, cg_result, full_phase_I, 1, tolerance)
        except _MissingCertificate as error:
            report.update(certificate_status="missing", reason=str(error))
        else:
            report.update(cg_verified=True, termination_certificate_verified=True,
                          pricing_termination_certificate_verified=True,
                          phase_I_infeasibility_certificate_verified=True,
                          certificate_status="verified", termination_certificate=certificate)
    else:
        report["reason"] = ("CG has not established full-column LP optimality or infeasibility; "
                            "model consistency alone does not verify CG termination")
    report["passed"] = report["model_consistency_passed"] and report["cg_verified"]
    if report["passed"]:
        report["verification_status"] = "passed"
    return report
