"""整线原生CPLEX PP会话：完整更新目标，固定域不变，每次独立核验原方案。

固定节点域会话，不允许运行中更换分支固定；不支持配额。会话按线隔离，不使用全局monkeypatch。
复用会保留CPLEX内部重优化状态；warm_start额外显式提交上次完整整数解。
"""
import importlib
import math
import time
from dataclasses import asdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from line_cg import compact, local_data, validate_column, NumericPolicy, NumericalUncertain
from solver_backend import load_cplex
from node_state import NodeRestrictions
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"stage4"))
from line_bp_pricing import allows


class LinePricing:
    def __init__(self, config, events, *, warm_start=True, restrictions=None, seed_pool=None):
        from copy import deepcopy
        self.restrictions = restrictions or NodeRestrictions()
        self.seed_pool = deepcopy(seed_pool or {}) if warm_start else {}
        if config.name != 'cplex_py' or config.threads != 1: raise ValueError('Node native PP requires single-thread CPLEX')
        self.config, self.events = config, events
        self.warm_start = warm_start
        self.sessions = {}
        self.calls = 0

    def close(self):
        for session in self.sessions.values():
            session['native'].end()
        self.sessions.clear()

    def solve(self, line, *, phase=2, human_price=0., robot_price=0., sigma=0.,
              policy=None, time_limit=None, purpose='pricing', caps=None, restrictions=None):
        if restrictions is not None and restrictions != self.restrictions: raise ValueError('A node session cannot change its fixed domain')
        if caps is not None:
            raise ValueError('Persistent node PP does not support quota')
        if phase not in (1, 2) or not all(math.isfinite(x) for x in (human_price, robot_price, sigma)):
            raise ValueError('Invalid pricing objective')
        policy = policy or NumericPolicy()
        start = time.perf_counter()
        cplex = load_cplex()
        session = self.sessions.get(line['id'])
        reused = session is not None
        if session is not None and session['line'] != line:
            raise ValueError('Line ID reused with different input')
        if session is not None and session['policy'] != asdict(policy):raise ValueError('Numeric policy changed within node session')
        if session is None:
            from copy import deepcopy
            model = compact.build_model(local_data(line))
            for l,i,station,mode,value in self.restrictions.fixes:
                if l==line['id']: model.problem += model.x[l,i,station,mode] == value, f'node_fix_{len(model.problem.constraints)}'
            api = importlib.import_module('pulp.apis.cplex_api')
            if hasattr(api.CPLEX_PY, 'err'):
                api = importlib.reload(api)
            translator = api.CPLEX_PY(msg=False, threads=1, gapRel=0,
                **{'mip.tolerances.absmipgap': 0., 'mip.tolerances.integrality': policy.pricing_integrality_tolerance,
                   'simplex.tolerances.feasibility': policy.lp_primal_tolerance,
                   'simplex.tolerances.optimality': policy.lp_dual_tolerance,
                   'randomseed': self.config.seed, 'parallel': 1})
            translator.buildSolverModel(model.problem)
            session = dict(line=deepcopy(line), model=model, native=translator.solverModel,
                           variables=model.problem.variables(), profit=model.problem.objective.copy(), last=None, last_column=None, seeds=[],policy=asdict(policy))
            self.sessions[line['id']] = session
            for seed in self.seed_pool.get(line['id'],[]):
                if not allows(seed,self.restrictions): raise ValueError('Illegal inherited start')
                checked=validate_column(line,seed['stations'],expected=seed['profit'],policy=policy)
                if any(checked[k]!=seed[k] for k in ('human','robot')):raise ValueError('Wrong seed resource coefficients')
                selected={(i,e['station'],m) for e in seed['stations'] for i,m in e['assignments']}
                for v in session['variables']:v.varValue=0.
                for (l,i,station,mode),v in model.x.items():v.varValue=float((i,station,mode) in selected)
                for (l,i),v in model.y.items():v.varValue=float(any(t==i for t,station,mode in selected))
                for (l,station),v in model.u.items():v.varValue=float(any(station==s for i,s,m in selected))
                for (l,station),v in model.h.items():v.varValue=float(any(station==s and m in ('H','J') for i,s,m in selected))
                for (l,station),v in model.r.items():v.varValue=float(any(station==s and m in ('R','J') for i,s,m in selected))
                if not model.problem.valid(policy.primal_validation_tolerance):raise NumericalUncertain('Inherited MIP start violates node model')
                session['seeds'].append(dict(values=[v.value() for v in session['variables']],column=seed,source='inherited_pool'))
        built = time.perf_counter()
        native, model = session['native'], session['model']
        import pulp
        objective = (session['profit'].copy() if phase == 2 else pulp.LpAffineExpression())
        objective -= human_price*pulp.lpSum(model.h.values()) + robot_price*pulp.lpSum(model.r.values()) + sigma
        model.problem.setObjective(objective)
        # 包括目标变成零的所有变量，防止阶段或价格切换残留旧系数。
        native.objective.set_linear([(i, float(objective.get(v, 0.))) for i, v in enumerate(session['variables'])])
        native.MIP_starts.delete()
        candidates=list(session['seeds'])
        if session['last'] is not None:
            candidates.append(dict(values=session['last'],column=session['last_column'],source='previous_solution'))
        selected_start=max(candidates,key=lambda e:(e['column']['profit'] if phase==2 else 0.)-human_price*e['column']['human']-robot_price*e['column']['robot']) if candidates else None
        submitted = self.warm_start and selected_start is not None
        if submitted:
            native.MIP_starts.add(cplex.SparsePair(ind=list(range(len(session['variables']))),val=selected_start['values']),
                                  native.MIP_starts.effort_level.check_feasibility)
        updated = time.perf_counter()
        limit = time_limit
        if self.config.deadline is not None:
            remaining = self.config.deadline-time.perf_counter()
            limit = min(limit, remaining) if limit is not None else remaining
        if limit is not None and limit <= 0:
            raise TimeoutError('Persistent whole-line PP deadline')
        native.parameters.timelimit.set(limit if limit is not None else 1e75)
        log_path = None
        self.calls += 1
        handle = None
        if self.config.log_dir:
            folder = Path(self.config.log_dir); folder.mkdir(parents=True, exist_ok=True)
            log_path = str(folder / f'persistent_{self.calls:06d}.log')
            handle = open(log_path, 'w', encoding='utf-8')
        for setter in (native.set_log_stream, native.set_results_stream, native.set_warning_stream, native.set_error_stream):
            setter(handle)
        try:
            tick = time.perf_counter(); native.solve(); solved = time.perf_counter()
        finally:
            for setter in (native.set_log_stream, native.set_results_stream, native.set_warning_stream, native.set_error_stream):
                setter(None)
            if handle: handle.close()
        solution = native.solution
        code = solution.get_status()
        feasible = bool(solution.is_primal_feasible())
        if feasible:
            values = list(solution.get_values())
            for v, value in zip(session['variables'], values): v.varValue = value
            if not model.problem.valid(policy.primal_validation_tolerance):
                raise NumericalUncertain('Persistent PP primal invalid')
            if any(abs(v.value()-round(v.value())) > policy.pricing_integrality_tolerance for v in model.x.values()):
                raise NumericalUncertain('Persistent PP fractional task assignment')
        optimal = code == 101 and feasible
        status = ('optimal' if optimal else 'infeasible' if code == 103 else
                  'time_limit' if code in (107,108) else 'feasible_unproven' if feasible else 'not_solved')
        constant = float(objective.constant)
        value = solution.get_objective_value()+constant if feasible else None
        bound = None
        if status != 'infeasible':
            raw = float(solution.MIP.get_best_objective())
            if math.isfinite(raw) and abs(raw)<1e19: bound = raw+constant
        if optimal: bound = value
        read = time.perf_counter()
        column = rc = None
        if feasible:
            stations = [dict(line=line['id'],station=s,assignments=sorted(
                [i,m] for (l,i,t,m),v in model.x.items() if t==s and v.value()>.5))
                for s in range(1,len(line['stations'])+1)]
            column = validate_column(line,stations,policy=policy)
            if not allows(column,self.restrictions):raise NumericalUncertain('Native solution violates node restrictions')
            session['last_column']=column
            rc = (column['profit'] if phase==2 else 0.)-human_price*column['human']-robot_price*column['robot']-sigma
            if abs(rc-value)>policy.bound_consistency_tolerance:
                raise NumericalUncertain('Persistent PP independent reduced cost mismatch')
            if bound is not None and bound < rc-policy.bound_consistency_tolerance:
                raise NumericalUncertain('Persistent PP bound below incumbent')
            session['last'] = values
        end = time.perf_counter()
        info = dict(backend='cplex_py',role='pricing',status=status,native_status=code,
            native_status_text=solution.get_status_string(),optimal=optimal,has_incumbent=feasible,
            objective=value,best_bound=bound,relative_gap=(abs(bound-value)/(abs(value)+1e-10)
                if bound is not None and value is not None else None),
            solver_time=solved-tick,translation_time=built-start,effective_time_limit=limit,
            options=asdict(self.config),log_path=log_path)
        self.events.append(info)
        profile=dict(create_seconds=built-start,objective_start_update_seconds=updated-built,
                     pre_solve_seconds=tick-updated,native_seconds=solved-tick,
                     read_seconds=read-solved,validate_seconds=end-read)
        cert=dict(line=line['id'],phase=phase,purpose=purpose,human_price=human_price,
                  robot_price=robot_price,sigma=sigma,caps=None,solver=info,optimal=optimal,
                  status=status,reduced_cost=rc,column=column,build_seconds=built-start,
                  solve_seconds=solved-built,validate_seconds=end-solved,total_seconds=end-start,
                  restrictions=self.restrictions.to_records(),mip_start_column=selected_start['column'] if submitted else None,
                  mip_start_source=selected_start['source'] if submitted else None,persistent=True,reused=reused,mip_start_submitted=submitted,profile=profile)
        return column,cert
