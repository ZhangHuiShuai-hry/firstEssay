"""实验性整线方案列生成：保留原物理模型，只改变 Dantzig–Wolfe 的分块。

每条列是一整条拆卸线的整数可行方案；主问题只协调共享工人和机器人。
默认单线程 CPLEX、seed=11、零 MIP gap；每次精确定价重新建立单线 MILP。
这是根节点 CG + 受限整数恢复，不是 Branch-and-Price。只有经验证的整数
利润与有效全局上界闭合时才报告原问题整数最优；否则明确保留 Gap。
时间限制是从 run() 开始的软墙钟预算，含建模和验证，不含导入/最终写盘。
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "code/dwcg"))

import pulp
from common import compact
from bp_solution import verify_integer_assignments
from node_state import NumericPolicy, NumericalUncertain
from solver_backend import BackendConfig, make_solver, objective_value, use_backend


def local_data(line):
    """K 人/K 机器人是原配置逻辑下冗余的单线容量，非全局资源配额。"""
    count = len(line["stations"])
    return {"lines": [line], "human_limit": count, "robot_limit": count}


def column_key(column):
    return tuple((s["station"], tuple(map(tuple, s["assignments"])))
                 for s in column["stations"])


def validate_column(line, stations, expected=None, policy=None):
    """同时检查数据级约束和原 Compact 约束，含线内优先/必做/回收。"""
    witness = verify_integer_assignments(local_data(line), stations,
                                         policy=policy, expected=expected)
    return {"line": line["id"], "profit": witness["objective"],
            "human": witness["resources_used"]["humans"],
            "robot": witness["resources_used"]["robots"],
            "stations": witness["stations"]}


def solve_line(line, *, phase=2, human_price=0., robot_price=0., sigma=0.,
               policy=None, time_limit=None, purpose="pricing", caps=None):
    """精确单线 PP。返回列与显式证书；未证最优 incumbent 仅可作候选列。"""
    policy = policy or NumericPolicy()
    start = time.perf_counter()
    model = compact.build_model(local_data(line))
    if caps is not None:
        model.problem += pulp.lpSum(model.h.values()) <= caps[0], "repair_h_cap"
        model.problem += pulp.lpSum(model.r.values()) <= caps[1], "repair_r_cap"
    original_profit = model.problem.objective.copy()
    model.problem.setObjective((original_profit if phase == 2 else pulp.LpAffineExpression())
                               - human_price * pulp.lpSum(model.h.values())
                               - robot_price * pulp.lpSum(model.r.values()) - sigma)
    built = time.perf_counter()
    model.problem.solve(make_solver(role="pricing", time_limit=time_limit, gap=0))
    solved = time.perf_counter()
    info = dict(model.problem.backend_result)
    column = None
    rc = None
    if info["has_incumbent"]:
        if any(v.value() is None or not math.isfinite(v.value()) or
               abs(v.value()-round(v.value())) > policy.pricing_integrality_tolerance
               for v in model.x.values()):
            raise NumericalUncertain("PP x is not integral")
        stations = [{"line": line["id"], "station": s,
                     "assignments": sorted([i, m] for (l, i, t, m), v in model.x.items()
                                           if t == s and v.value() > .5)}
                    for s in range(1, len(line["stations"])+1)]
        column = validate_column(line, stations, policy=policy)
        rc = ((column["profit"] if phase == 2 else 0.)
              - human_price*column["human"] - robot_price*column["robot"] - sigma)
        value = objective_value(model.problem)
        if value is None or abs(rc-value) > policy.bound_consistency_tolerance:
            raise NumericalUncertain("Independent PP reduced cost mismatch")
    end = time.perf_counter()
    cert = {"line": line["id"], "phase": phase, "purpose": purpose,
            "human_price": human_price, "robot_price": robot_price, "sigma": sigma,
            "caps": caps, "solver": info, "optimal": info["optimal"],
            "status": info["status"], "reduced_cost": rc,
            "column": column, "build_seconds": built-start,
            "solve_seconds": solved-built, "validate_seconds": end-solved,
            "total_seconds": end-start}
    return column, cert


def build_master(data, pool, *, phase=2, integer=False):
    problem = pulp.LpProblem("whole_line_master", pulp.LpMaximize)
    variables = {}
    convexity = {}
    for li, line in enumerate(data["lines"]):
        l = line["id"]
        if not pool[l]:
            raise ValueError("Hard line convexity requires an initial legal line plan")
        for p, col in enumerate(pool[l]):
            variables[l, p] = pulp.LpVariable(f"lambda_{li}_{p}", 0,
                                            cat="Binary" if integer else "Continuous")
        row = pulp.lpSum(variables[l, p] for p in range(len(pool[l]))) == 1
        problem += row, f"convexity_{li}"
        convexity[l] = row
    resource = {}
    artificials = {}
    for name in ("human", "robot"):
        expression = pulp.lpSum(col[name]*variables[l, p]
                                for l, cols in pool.items() for p, col in enumerate(cols))
        if phase == 1:
            artificials[name] = pulp.LpVariable(f"elastic_{name}", 0)
            expression -= artificials[name]
        resource[name] = expression <= data[f"{name}_limit"]
        problem += resource[name], f"shared_{name}"
    if phase == 1:
        problem += -pulp.lpSum(artificials.values())
    elif phase == 2:
        problem += pulp.lpSum(col["profit"]*variables[l, p]
                              for l, cols in pool.items() for p, col in enumerate(cols))
    else:
        raise ValueError("phase must be 1 or 2")
    return problem, variables, convexity, resource, artificials


def solve_master(data, pool, *, phase=2, integer=False, policy=None, time_limit=None):
    policy = policy or NumericPolicy()
    start = time.perf_counter()
    problem, variables, convexity, resource, artificials = build_master(
        data, pool, phase=phase, integer=integer)
    built = time.perf_counter()
    problem.solve(make_solver(mip=integer, role="restricted_ip" if integer else "rmp",
                              time_limit=time_limit, gap=0))
    solved = time.perf_counter()
    info = dict(problem.backend_result)
    cert = {"phase": phase, "integer": integer, "solver": info,
            "pool_sizes": {l: len(cols) for l, cols in pool.items()},
            "objective": objective_value(problem) if info["has_incumbent"] else None,
            "solution": [], "artificials": {}, "duals": None,
            "dual_objective": None, "witness": None,
            "build_seconds": built-start, "solve_seconds": solved-built}
    if info["has_incumbent"]:
        if not problem.valid(policy.primal_validation_tolerance):
            raise NumericalUncertain("Master primal invalid")
        cert["solution"] = [{"line": l, "column": p, "weight": v.value()}
                            for (l, p), v in variables.items()]
        cert["artificials"] = {k: v.value() for k, v in artificials.items()}
        if integer:
            if any(abs(v.value()-round(v.value())) > policy.branch_integrality_tolerance
                   for v in variables.values()):
                raise NumericalUncertain("Restricted IP lambdas are not integral")
            records = [s for (l, p), v in variables.items() if v.value() > .5
                       for s in pool[l][p]["stations"]]
            cert["witness"] = verify_integer_assignments(
                data, records, policy=policy, expected=cert["objective"])
    if info["optimal"] and not integer:
        prices = {}
        for name, row in resource.items():
            value = row.pi
            if value is None or not math.isfinite(value) or value < -policy.lp_dual_tolerance:
                raise NumericalUncertain("Invalid resource dual")
            if phase == 1 and value > 1+policy.lp_dual_tolerance:
                raise NumericalUncertain("Invalid elastic dual upper bound")
            prices[name] = min(1., max(0., value)) if phase == 1 else max(0., value)
        sigma = {l: row.pi for l, row in convexity.items()}
        if any(v is None or not math.isfinite(v) for v in sigma.values()):
            raise NumericalUncertain("Invalid convexity dual")
        dual_objective = sum(sigma.values()) + sum(data[f"{k}_limit"]*v for k, v in prices.items())
        if abs(dual_objective-cert["objective"]) > policy.bound_consistency_tolerance:
            raise NumericalUncertain("Master primal/dual objective mismatch")
        for l, cols in pool.items():
            for col in cols:
                rc = ((col["profit"] if phase == 2 else 0.) - sigma[l]
                      - prices["human"]*col["human"] - prices["robot"]*col["robot"])
                if rc > policy.bound_consistency_tolerance:
                    raise NumericalUncertain("Existing column violates master dual")
        cert["duals"] = {**prices, "convexity": sigma}
        cert["raw_duals"] = {"human": resource["human"].pi, "robot": resource["robot"].pi,
                             "convexity": {l: row.pi for l, row in convexity.items()}}
        cert["dual_objective"] = dual_objective
    cert["validate_seconds"] = time.perf_counter()-solved
    cert["total_seconds"] = time.perf_counter()-start
    return cert


def run(data, *, time_limit=30., solver="cplex_py", log_dir=None, max_iterations=100,
        recovery_seconds=.5, policy=None, use_initial_bounds=True):
    """独立实验入口。pool/history 均可 JSON 序列化；不依赖完整列枚举。"""
    started = time.perf_counter()
    compact.number(time_limit, 'time_limit', 0, strict=True)
    compact.integer(max_iterations, 'max_iterations', 1)
    compact.number(recovery_seconds, 'recovery_seconds', 0, strict=True)
    policy = policy or NumericPolicy()
    compact.validate_data(data)
    deadline = started+time_limit
    pool = {line["id"]: [] for line in data["lines"]}
    keys = {l: set() for l in pool}
    events = []
    result = {"algorithm": "whole_line_CG_restricted_IP", "certificate_version": 2,
              "proof_scope": "solver_floating_point_tolerances", "policy": asdict(policy),
              "solver_backend": solver, "time_limit": time_limit,
              "status": "not_solved", "termination_reason": "", "pool": pool,
              "initialization": [], "history": [], "integer_recovery": [],
              "witness": None, "lower_bound": None, "upper_bound": None,
              "absolute_gap": None, "relative_gap": None,
              "global_integer_optimal_proven": False, "global_infeasibility_proven": False,
              "lp_optimal_proven": False, "lp_objective": None,
              "first_integer_seconds": None, "pricing_calls": 0,
              "solver_events": events, "error": None}

    def add(column):
        l = column["line"]
        key = column_key(column)
        if key in keys[l]:
            return False
        keys[l].add(key)
        pool[l].append(column)
        return True

    def accept(witness):
        if witness is not None and (result["lower_bound"] is None or
                                    witness["objective"] > result["lower_bound"]):
            result["lower_bound"] = witness["objective"]
            result["witness"] = witness
            if result["first_integer_seconds"] is None:
                result["first_integer_seconds"] = time.perf_counter()-started

    def closed():
        lb, ub = result["lower_bound"], result["upper_bound"]
        if lb is None or ub is None:
            return False
        if ub < lb-policy.bound_consistency_tolerance:
            raise NumericalUncertain("Global bound below verified incumbent")
        if ub-lb <= policy.allowance(lb):
            result["global_integer_optimal_proven"] = True
            result["status"] = "optimal_within_tolerance"
            result["termination_reason"] = "verified_integer_and_valid_upper_bound_close"
            return True
        return False

    def recover():
        if deadline-time.perf_counter() <= .002:
            return
        cert = solve_master(data, pool, integer=True, policy=policy,
                            time_limit=min(recovery_seconds, deadline-time.perf_counter()))
        result["integer_recovery"].append(cert)
        accept(cert["witness"])

    config = BackendConfig(name=solver, threads=1, seed=11, deadline=deadline,
                           primal_tolerance=policy.lp_primal_tolerance,
                           dual_tolerance=policy.lp_dual_tolerance,
                           mip_integrality_tolerance=policy.pricing_integrality_tolerance,
                           log_dir=str(log_dir) if log_dir else None)
    try:
        with use_backend(config, events):
            # 本轮不从 Compact 全模型或生成器见证初始化；逐线经济最优方案独立求解。
            for position, line in enumerate(data["lines"]):
                share = max(.001, (deadline-time.perf_counter())/(len(data["lines"])-position))
                column, cert = solve_line(line, phase=2, purpose="initialization",
                                          policy=policy, time_limit=share)
                result["initialization"].append(cert)
                result["pricing_calls"] += 1
                if column is not None:
                    add(column)
                elif cert["status"] == "infeasible":
                    result.update(status="infeasible_proven", global_infeasibility_proven=True,
                                  termination_reason="one_line_integer_domain_empty")
                    break
                else:
                    result.update(status=cert["status"], termination_reason="initial_line_not_resolved")
                    break
            else:
                # 这里只使用初始化时原经济单线MILP的原生最大化Best Bound。
                # 不启用截断对偶定价驱动的新轮CG，不把incumbent当成上界。
                # 单线域是原全局域的放松，故各线有效上界之和仍是全局安全上界。
                initial_bounds = []
                for e in result['initialization']:
                    if e['optimal']:
                        initial_bounds.append(e['column']['profit'])
                    elif use_initial_bounds:
                        bound=e['solver'].get('best_bound')
                        if bound is None or not math.isfinite(bound) or abs(bound)>=1e19:
                            break
                        if bound < e['column']['profit']-policy.bound_consistency_tolerance:
                            raise NumericalUncertain('Initialization MIP bound below incumbent')
                        initial_bounds.append(bound)
                    else:
                        break
                if len(initial_bounds)==len(data['lines']):
                    result["upper_bound"] = sum(initial_bounds)
                    result["initial_independent_upper_bound"] = result["upper_bound"]
                    result['initial_upper_bound_components'] = initial_bounds
                    result['initial_upper_bound_source'] = ('exact_line_optima' if all(e['optimal'] for e in result['initialization'])
                                                            else 'sum_native_economic_line_MIP_best_bounds')
                initial = [pool[line["id"]][0] for line in data["lines"]]
                if (sum(c["human"] for c in initial) <= data["human_limit"] and
                        sum(c["robot"] for c in initial) <= data["robot_limit"]):
                    accept(verify_integer_assignments(data, [s for c in initial for s in c["stations"]],
                                                       policy=policy))
                if closed():
                    result["lp_optimal_proven"] = True
                    result["lp_objective"] = result["lower_bound"]
                    result["termination_reason"] = "independent_line_optima_are_resource_compatible"
                else:
                    phase = 1
                    for iteration in range(1, max_iterations+1):
                        if time.perf_counter() >= deadline:
                            raise TimeoutError("whole-line CG deadline")
                        master = solve_master(data, pool, phase=phase, policy=policy)
                        record = {"iteration": iteration, "phase": phase, "rmp": master,
                                  "pricing": [], "complete_exact_pricing": False,
                                  "repaired_upper_bound": None, "added": [], "phase_transition": False}
                        result["history"].append(record)
                        if not master["solver"]["optimal"]:
                            result.update(status=master["solver"]["status"],
                                          termination_reason="RMP_not_proven_optimal")
                            break
                        if phase == 1 and sum(master["artificials"].values()) <= policy.artificial_tolerance:
                            # Phase II 的硬约束 RMP 会再次独立求解，失败不能声称可行。
                            record["phase_transition"] = True
                            phase = 2
                            continue
                        if phase == 2:
                            result["lp_objective"] = master["objective"]
                            recover()
                            if closed():
                                break
                        duals = master["duals"]
                        for line in data["lines"]:
                            column, cert = solve_line(
                                line, phase=phase, human_price=duals["human"],
                                robot_price=duals["robot"], sigma=duals["convexity"][line["id"]],
                                policy=policy)
                            result["pricing_calls"] += 1
                            record["pricing"].append(cert)
                            if column is not None and cert["reduced_cost"] > policy.reduced_cost_epsilon:
                                if add(column):
                                    record["added"].append({"line": line["id"], "column": len(pool[line["id"]])-1})
                                elif cert["optimal"]:
                                    raise NumericalUncertain("Positive pricing returned an existing line column")
                            if not cert["optimal"]:
                                result.update(status=cert["status"], termination_reason="pricing_not_proven_optimal")
                                break
                        record["complete_exact_pricing"] = (
                            len(record["pricing"]) == len(data["lines"])
                            and all(c["optimal"] for c in record["pricing"]))
                        if not record["complete_exact_pricing"]:
                            if result["termination_reason"] == "":
                                result.update(status="numerical_uncertain", termination_reason="incomplete_pricing")
                            break
                        rho = [c["reduced_cost"] for c in record["pricing"]]
                        # 修复对偶凸性价格给出完整列 LP 上界；基数为 L 而非工作站数。
                        repaired = master["dual_objective"]+sum(max(0., r) for r in rho)
                        record["repaired_upper_bound"] = repaired
                        if phase == 2:
                            result["upper_bound"] = min(result["upper_bound"], repaired) if result["upper_bound"] is not None else repaired
                        if phase == 1 and repaired < -policy.artificial_tolerance:
                            result.update(status="infeasible_proven", global_infeasibility_proven=True,
                                          termination_reason="complete_line_Phase_I_upper_bound_negative")
                            break
                        if max(rho) <= policy.reduced_cost_epsilon:
                            if phase == 1:
                                result.update(status="numerical_uncertain", termination_reason="Phase_I_tolerance_ambiguous")
                            else:
                                result["lp_optimal_proven"] = True
                                result.update(status="lp_optimal_integer_unproven", termination_reason="exact_line_pricing_converged")
                                recover()
                                closed()
                            break
                        if phase == 2 and closed():
                            break
                        if not record["added"]:
                            result.update(status="numerical_uncertain", termination_reason="positive_rc_without_new_column")
                            break
                    else:
                        result.update(status="iteration_limit", termination_reason="CG_iteration_limit")
    except TimeoutError as error:
        result.update(status="time_limit", termination_reason=str(error))
    except NumericalUncertain as error:
        result.update(status="numerical_uncertain", termination_reason=str(error),
                      error={"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()})
    except Exception as error:
        result.update(status="solver_error", termination_reason=str(error),
                      error={"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()})
    if result["lower_bound"] is not None and result["upper_bound"] is not None:
        difference = result["upper_bound"]-result["lower_bound"]
        result["absolute_gap"] = difference
        result["relative_gap"] = max(0., difference)/max(1., abs(result["lower_bound"]))
    result["columns"] = sum(map(len, pool.values()))
    result["wall_seconds"] = time.perf_counter()-started
    result["budget_overrun_seconds"] = max(0., result["wall_seconds"]-time_limit)
    result["timing"] = {
        "PP_native_seconds": sum(e.get("solver_time", 0.) or 0. for e in events if e["role"] == "pricing"),
        "RMP_native_seconds": sum(e.get("solver_time", 0.) or 0. for e in events if e["role"] == "rmp"),
        "restricted_IP_native_seconds": sum(e.get("solver_time", 0.) or 0. for e in events if e["role"] == "restricted_ip")}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", nargs="?", type=Path,
                        default=ROOT/"code/data/tasks005_lines02_each03-02.json")
    parser.add_argument("--time-limit", type=float, default=30., help="含建模/验证的软墙钟秒数")
    parser.add_argument("--max-iterations", type=int, default=100)
    parser.add_argument("--solver", choices=("cplex_py", "cbc"), default="cplex_py")
    parser.add_argument("--output", type=Path, required=True, help="新的结果目录，不覆盖已有目录")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    raw = args.instance.read_bytes()
    (args.output/"instance.json").write_bytes(raw)
    result = run(json.loads(raw.decode("utf-8-sig")), time_limit=args.time_limit,
                 max_iterations=args.max_iterations, solver=args.solver, log_dir=args.output/"logs")
    result["instance_sha256"] = hashlib.sha256(raw).hexdigest()
    (args.output/"result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "lower_bound", "upper_bound", "absolute_gap",
                                           "global_integer_optimal_proven", "columns", "wall_seconds")}, ensure_ascii=False))
    return 0 if result["global_integer_optimal_proven"] or result["global_infeasibility_proven"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
