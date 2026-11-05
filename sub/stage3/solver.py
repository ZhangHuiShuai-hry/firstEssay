"""短经济初始化+可选资源配额补列；旧整线求解器保持字节不变。
默认每线0.5秒初始经济求解，必要时0.5秒常数目标可行性恢复；精确定价停止标准不变。
补列只改善LB；只有原见证与有效全局UB闭合才证明整数最优。统一软预算包含全部操作。
"""
from pathlib import Path
import sys,math,time,traceback
from dataclasses import asdict
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'stage1')]
from line_cg import (compact,NumericPolicy,NumericalUncertain,BackendConfig,use_backend,
                     solve_line,solve_master,column_key,verify_integer_assignments)
from quota_repair import repair as quota_repair
from persistent_line import LinePricing

def run(data, *, time_limit=30., solver="cplex_py", log_dir=None, max_iterations=100,
        recovery_seconds=.5, policy=None, use_initial_bounds=True, init_seconds=None, quota=False, quota_seconds=2., quota_calls=4, pricing="rebuild"):
    """独立实验入口。pool/history 均可 JSON 序列化；不依赖完整列枚举。"""
    if pricing not in ("rebuild","reuse","warm"): raise ValueError("Unknown PP strategy")
    if solver != "cplex_py" and pricing != "rebuild": raise ValueError("Native PP requires CPLEX")
    started = time.perf_counter()
    compact.number(time_limit, 'time_limit', 0, strict=True)
    compact.integer(max_iterations, 'max_iterations', 1)
    compact.number(recovery_seconds, 'recovery_seconds', 0, strict=True)
    if init_seconds is not None:compact.number(init_seconds,'init_seconds',0,strict=True)
    compact.number(quota_seconds,'quota_seconds',0,strict=True)
    compact.integer(quota_calls,'quota_calls',1)
    policy = policy or NumericPolicy()
    compact.validate_data(data)
    deadline = started+time_limit
    pool = {line["id"]: [] for line in data["lines"]}
    keys = {l: set() for l in pool}
    events = []
    result = {"algorithm": "whole_line_CG_restricted_IP", "certificate_version": 4,
              "proof_scope": "solver_floating_point_tolerances", "policy": asdict(policy),
              "solver_backend": solver, "time_limit": time_limit,
              "status": "not_solved", "termination_reason": "", "pool": pool,
              "initialization": [], "history": [], "integer_recovery": [],
              "witness": None, "lower_bound": None, "upper_bound": None,
              "absolute_gap": None, "relative_gap": None,
              "global_integer_optimal_proven": False, "global_infeasibility_proven": False,
              "lp_optimal_proven": False, "lp_objective": None,
              "first_integer_seconds": None, "pricing_calls": 0,
              "solver_events": events, "error": None, "quota_repair": [], "initialization_fallback": [],
              "incumbent_history": [], "pricing_strategy": pricing,
              "settings": dict(init_seconds=init_seconds,quota=quota,quota_seconds=quota_seconds,quota_calls=quota_calls)}

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
            result["incumbent_history"].append(dict(seconds=time.perf_counter()-started,objective=witness["objective"]))
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

    def supplement():
        if not quota or deadline-time.perf_counter()<=.01:return
        before={l:len(cs) for l,cs in pool.items()}
        try:repair=quota_repair(data,pool,time_limit=min(quota_seconds,deadline-time.perf_counter()),max_calls=quota_calls)
        except TimeoutError:
            result['quota_repair'].append(dict(status='time_limit',before_sizes=before,added=[]));return
        repair['before_sizes']=before
        added=[]
        for l,cols in repair.get('pool',{}).items():
            for c in cols[before[l]:]:
                if add(c):added.append(dict(line=l,column=len(pool[l])-1))
        repair.pop('pool',None);repair['added']=added
        result['quota_repair'].append(repair)
        accept(repair.get('witness'))

    config = BackendConfig(name=solver, threads=1, seed=11, deadline=deadline,
                           primal_tolerance=policy.lp_primal_tolerance,
                           dual_tolerance=policy.lp_dual_tolerance,
                           mip_integrality_tolerance=policy.pricing_integrality_tolerance,
                           log_dir=str(log_dir) if log_dir else None)
    session = LinePricing(config, events, warm_start=pricing=="warm") if pricing != "rebuild" else None
    price = session.solve if session else solve_line
    try:
        with use_backend(config, events):
            # 本轮不从 Compact 全模型或生成器见证初始化；逐线经济最优方案独立求解。
            for position, line in enumerate(data["lines"]):
                share = max(.001, (deadline-time.perf_counter())/(len(data["lines"])-position))
                if init_seconds is not None:share=min(share,init_seconds)
                column, cert = price(line, phase=2, purpose="initialization",
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
                    # 短经济求解未找到incumbent，常数目标只用于局部可行性，不用于经济UB。
                    if init_seconds is not None:
                        fallback,fc=price(line,phase=1,purpose='initial_feasibility',time_limit=init_seconds)
                        result['initialization_fallback'].append(fc)
                        if fallback is not None:add(fallback);continue
                        if fc['status']=='infeasible':
                            result.update(status='infeasible_proven',global_infeasibility_proven=True,termination_reason='fallback_local_domain_empty');break
                    result.update(status=cert['status'],termination_reason='initial_line_not_resolved');break
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
                        if e['column'] is not None and bound < e['column']['profit']-policy.bound_consistency_tolerance:
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
                            column, cert = price(
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
                        if phase == 2 and (iteration % 5 == 0 or max(rho)<=policy.reduced_cost_epsilon or not result['quota_repair']):
                            supplement()
                            if closed():break
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
    finally:
        if session: session.close()
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

