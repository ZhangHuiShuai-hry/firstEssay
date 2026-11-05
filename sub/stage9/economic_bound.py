"""仅使用零资源价格下的原生PP Best Bound；不驱动截断后的新CG轮。"""
import math,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'stage8'))
from demand_traced import run as base_run

def derive(data,base):
    records=[];bounds={l['id']:[] for l in data['lines']};cg=base['cg']
    candidates=[(f'initialization/{n}',c) for n,c in enumerate(cg['initialization'])]
    candidates += [(f'history/{n}/pricing/{j}',c) for n,h in enumerate(cg['history']) for j,c in enumerate(h['pricing'])]
    for path,c in candidates:
        if c['phase']!=2 or c['human_price']!=0. or c['robot_price']!=0. or c.get('caps') is not None:continue
        native=c['solver'];b=native.get('best_bound')
        if native.get('backend')!='cplex_py' or native.get('native_status') not in (101,102,107,108):continue
        if b is None or not math.isfinite(b) or abs(b)>=1e19:continue
        value=b+c['sigma']
        if c['column'] is not None and value<c['column']['profit']-cg['policy']['bound_consistency_tolerance']:raise ValueError('Economic bound below local witness')
        bounds[c['line']].append(value);records.append(dict(path=path,line=c['line'],economic_upper_bound=value))
    best={l:min(bs) if bs else None for l,bs in bounds.items()}
    return dict(records=records,line_upper_bounds=best,upper_bound=sum(best.values()) if all(b is not None for b in best.values()) else None)

def refine(data,base):
    evidence=derive(data,base);ub=base['global_upper_bound'];b=evidence['upper_bound']
    if b is not None:ub=b if ub is None else min(ub,b)
    lb=base['global_lower_bound'];policy=base['policy']
    if lb is not None and ub is not None and ub<lb-policy['bound_consistency_tolerance']:raise ValueError('Economic global upper bound below witness')
    closed=lb is not None and ub is not None and ub-lb<=max(policy['global_absolute_tolerance'],policy['global_relative_tolerance']*max(1,abs(lb)))
    return dict(algorithm='root_CG_profiles_with_zero_price_economic_bounds',certificate_version='economic-bound-1',proof_scope=base['proof_scope'],
        base_result=base,economic_evidence=evidence,global_lower_bound=lb,global_upper_bound=ub,witness=base['witness'],
        global_integer_optimal_proven=bool(base['global_integer_optimal_proven'] or closed),global_infeasibility_proven=base['global_infeasibility_proven'],
        status='optimal_within_tolerance' if closed else base['status'],absolute_gap=None if lb is None or ub is None else ub-lb,
        relative_gap=None if lb is None or ub is None else max(0,ub-lb)/max(1,abs(lb)),first_integer_seconds=base['first_integer_seconds'],profile_calls=base['profile_calls'])

def run(data,*,time_limit=30,progress=None,**kwargs):
    start=time.perf_counter()
    base=base_run(data,time_limit=max(.001,time_limit-.25),progress=progress,**kwargs)
    r=refine(data,base);r['wall_seconds']=time.perf_counter()-start
    if progress:progress('economic_bound_refinement',r['global_lower_bound'],r['global_upper_bound'],{})
    return r
