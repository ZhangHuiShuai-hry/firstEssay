"""探索模型的直接 CPLEX 对照：读取同一冻结 JSON，原方程及数值精度不变。

单线程、seed=11、MIP gap=0。截止时间包含建模及整数见证核验；原生调用
使用剩余软预算。返回最优/限时状态、有效 Best Bound 和独立原约束检查。
"""
from __future__ import annotations
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'code/dwcg'), str(ROOT/'code')]
from common import compact, blocks
from bp_solution import verify_integer_assignments
from solver_backend import BackendConfig, use_backend, make_solver


def run(data, time_limit=30., solver='cplex_py', log_dir=None,progress=None):
    start = time.perf_counter()
    result = dict(algorithm='compact', status='time_limit', witness=None,
                  global_lower_bound=None, global_upper_bound=None,
                  global_integer_optimal_proven=False, global_infeasibility_proven=False,
                  first_integer_seconds=None)
    events = []
    try:
        with use_backend(BackendConfig(name=solver, deadline=start+time_limit,
                                       log_dir=str(log_dir) if log_dir else None), events):
            model = compact.build_model(data)
            from solver_backend import load_cplex
            import math
            cplex=load_cplex()
            variables=model.problem.variables()
            indices={v.name:i for i,v in enumerate(variables)}
            last=[None,-1.]
            class Observe(cplex.callbacks.MIPInfoCallback):
                def __call__(self):
                    now=time.perf_counter()-start
                    if now-last[1]<1.:return
                    last[1]=now
                    bound=float(self.get_best_objective_value())+float(model.problem.objective.constant)
                    if not math.isfinite(bound) or abs(bound)>=1e19:bound=None
                    if self.has_incumbent():
                        value=float(self.get_incumbent_objective_value())+float(model.problem.objective.constant)
                        if last[0] is None or value>last[0]:
                            values=self.get_incumbent_values()
                            records=[dict(line=l['id'],station=s,assignments=[(i,m)
                                for (li,i,ss,m),v in model.x.items()
                                if li==l['id'] and ss==s and values[indices[v.name]]>.5]) for l,s in blocks(data)]
                            witness=verify_integer_assignments(data,records,expected=value)
                            last[0]=witness['objective']
                            if result['first_integer_seconds'] is None:result['first_integer_seconds']=time.perf_counter()-start
                    if progress:progress('compact_native',last[0],bound,{})
            model.problem.solve(make_solver(role='compact_ip'),callback=[Observe] if progress else None)
        info = dict(model.problem.backend_result)
        result.update(status=info['status'], solver_result=info,
                      global_upper_bound=info['best_bound'],
                      global_infeasibility_proven=info['status']=='infeasible')
        if info['has_incumbent']:
            records = [dict(line=l['id'], station=s,
                            assignments=[(i,m) for (li,i,ss,m),v in model.x.items()
                                         if li==l['id'] and ss==s and v.value()>.5])
                       for l,s in blocks(data)]
            witness = verify_integer_assignments(data, records, expected=info['objective'])
            result.update(witness=witness, global_lower_bound=witness['objective'],
                          global_integer_optimal_proven=info['optimal'])
            # 未接 CPLEX incumbent callback，不能把返回时刻伪称首次求解器发现时刻。
            result['first_verified_integer_seconds'] = time.perf_counter()-start
    except TimeoutError:
        pass
    lb, ub = result['global_lower_bound'], result['global_upper_bound']
    if lb is not None and ub is not None and ub < lb-1e-5:
        raise RuntimeError('Invalid bound below verified witness')
    result.update(absolute_gap=None if lb is None or ub is None else ub-lb,
                  relative_gap=None if lb is None or ub is None else (ub-lb)/max(1,abs(lb)),
                  algorithm_seconds=time.perf_counter()-start, solver_events=events)
    if progress:progress('compact_finished',result['global_lower_bound'],result['global_upper_bound'],{})
    return result


if __name__ == '__main__':
    from benchmark import cli
    cli(default_method='compact')
