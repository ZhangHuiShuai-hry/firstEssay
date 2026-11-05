"""整线原生CPLEX PP会话：完整更新目标，固定域不变，每次独立核验原方案。

仅支持根节点整线域，不支持分支固定或配额。会话按线隔离，不使用全局monkeypatch。
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


class LinePricing:
    def __init__(self, config, events, *, warm_start=True):
        self.config, self.events = config, events
        self.warm_start = warm_start
        self.sessions = {}
        self.calls = 0

    def close(self):
        for session in self.sessions.values():
            session['native'].end()
        self.sessions.clear()

    def solve(self, line, *, phase=2, human_price=0., robot_price=0., sigma=0.,
              policy=None, time_limit=None, purpose='pricing', caps=None):
        if caps is not None:
            raise ValueError('Persistent root PP does not support quota or node restrictions')
        if phase not in (1, 2) or not all(math.isfinite(x) for x in (human_price, robot_price, sigma)):
            raise ValueError('Invalid pricing objective')
        policy = policy or NumericPolicy()
        start = time.perf_counter()
        cplex = load_cplex()
        session = self.sessions.get(line['id'])
        reused = session is not None
        if session is not None and session['line'] != line:
            raise ValueError('Line ID reused with different input')
        if session is None:
            from copy import deepcopy
            model = compact.build_model(local_data(line))
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
                           variables=model.problem.variables(), profit=model.problem.objective.copy(), last=None)
            self.sessions[line['id']] = session
        built = time.perf_counter()
        native, model = session['native'], session['model']
        import pulp
        objective = (session['profit'].copy() if phase == 2 else pulp.LpAffineExpression())
        objective -= human_price*pulp.lpSum(model.h.values()) + robot_price*pulp.lpSum(model.r.values()) + sigma
        model.problem.setObjective(objective)
        # 包括目标变成零的所有变量，防止阶段或价格切换残留旧系数。
        native.objective.set_linear([(i, float(objective.get(v, 0.))) for i, v in enumerate(session['variables'])])
        native.MIP_starts.delete()
        submitted = self.warm_start and session['last'] is not None
        if submitted:
            native.MIP_starts.add(cplex.SparsePair(ind=list(range(len(session['variables']))), val=session['last']),
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
            session['last'] = values
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
            rc = (column['profit'] if phase==2 else 0.)-human_price*column['human']-robot_price*column['robot']-sigma
            if abs(rc-value)>policy.bound_consistency_tolerance:
                raise NumericalUncertain('Persistent PP independent reduced cost mismatch')
            if bound is not None and bound < rc-policy.bound_consistency_tolerance:
                raise NumericalUncertain('Persistent PP bound below incumbent')
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
                  persistent=True,reused=reused,mip_start_submitted=submitted,profile=profile)
        return column,cert
