"""重建式整线节点PP，分支固定是局部整数域的硬约束。"""
from pathlib import Path
import sys,math,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from line_cg import compact,local_data,validate_column,NumericPolicy,NumericalUncertain
import pulp
from solver_backend import make_solver,objective_value
from node_state import NodeRestrictions

def allows(column, restrictions):
    selected={(column['line'],i,e['station'],m) for e in column['stations'] for i,m in e['assignments']}
    return all(int((l,i,s,m) in selected)==v for l,i,s,m,v in restrictions.fixes if l==column['line'])

def solve_line(line, *, phase=2, human_price=0., robot_price=0., sigma=0.,
               policy=None, time_limit=None, purpose="pricing", caps=None, restrictions=None, profile=None):
    """精确单线 PP。返回列与显式证书；未证最优 incumbent 仅可作候选列。"""
    policy = policy or NumericPolicy()
    start = time.perf_counter()
    model = compact.build_model(local_data(line))
    if caps is not None:
        model.problem += pulp.lpSum(model.h.values()) <= caps[0], "repair_h_cap"
        model.problem += pulp.lpSum(model.r.values()) <= caps[1], "repair_r_cap"
    restrictions = restrictions or NodeRestrictions()
    restrictions.validate(local_data(line)) if all(e[0]==line['id'] for e in restrictions.fixes) else None
    for l,i,s,m,value in restrictions.fixes:
        if l==line['id']: model.problem += model.x[l,i,s,m] == value, f'branch_{len(model.problem.constraints)}'
    if profile is None:raise ValueError('Exact resource profile required')
    model.problem += pulp.lpSum(model.h.values()) == profile[0], 'exact_h'
    model.problem += pulp.lpSum(model.r.values()) == profile[1], 'exact_r'
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
    cert["profile"] = list(profile)
    cert["restrictions"] = restrictions.to_records()
    if column is not None and not allows(column, restrictions): raise NumericalUncertain("Illegal node column")
    return column, cert

