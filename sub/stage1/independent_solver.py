"""整线独立经济求解对照；资源不兼容时停止，不做CG、不宣称不可行。"""
from pathlib import Path
import sys,time,math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from line_cg import solve_line,validate_column
from bp_solution import verify_integer_assignments
from solver_backend import BackendConfig,use_backend

def run(data,time_limit=30.,log_dir=None):
    start=time.perf_counter();deadline=start+time_limit;events=[]
    out=dict(algorithm='independent_lines_without_CG',initialization=[],witness=None,
             global_lower_bound=None,global_upper_bound=None,global_integer_optimal_proven=False,
             global_infeasibility_proven=False,status='time_limit',first_integer_seconds=None)
    try:
        with use_backend(BackendConfig(name='cplex_py',deadline=deadline,log_dir=str(log_dir) if log_dir else None),events):
            for n,line in enumerate(data['lines']):
                c,cert=solve_line(line,purpose='initialization',time_limit=max(.001,(deadline-time.perf_counter())/(len(data['lines'])-n)))
                out['initialization'].append(cert)
                if c is None:
                    if cert['status']=='infeasible':out.update(status='infeasible_proven',global_infeasibility_proven=True)
                    break
            else:
                cols=[e['column'] for e in out['initialization']]
                bounds=[c['profit'] if e['optimal'] else e['solver'].get('best_bound') for c,e in zip(cols,out['initialization'])]
                if all(b is not None and math.isfinite(b) for b in bounds):
                    assert all(b>=c['profit']-1e-5 for b,c in zip(bounds,cols))
                    out['global_upper_bound']=sum(bounds)
                if sum(c['human'] for c in cols)<=data['human_limit'] and sum(c['robot'] for c in cols)<=data['robot_limit']:
                    w=verify_integer_assignments(data,[s for c in cols for s in c['stations']])
                    out.update(witness=w,global_lower_bound=w['objective'],first_integer_seconds=time.perf_counter()-start,status='feasible_unproven')
                    ub=out['global_upper_bound']
                    if ub is not None and ub-w['objective']<=1e-5:
                        out.update(status='optimal_within_tolerance',global_integer_optimal_proven=True)
                else:out['status']='resource_incompatible_unresolved'
    except TimeoutError:pass
    lb,ub=out['global_lower_bound'],out['global_upper_bound']
    out.update(absolute_gap=None if lb is None or ub is None else ub-lb,
               algorithm_seconds=time.perf_counter()-start,solver_events=events)
    return out
