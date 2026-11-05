"""精确资源档MILP+二维DP对照，非普通列生成。"""
import json,sys,time,math,traceback,argparse,zlib
from pathlib import Path
from dataclasses import asdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from line_cg import compact,NumericPolicy,BackendConfig,use_backend,verify_integer_assignments
from profile_pp import solve_line,NodeRestrictions

def dynamic_program(data,table,upper=False):
    states={(0,0):(0.,[])}
    for line in data['lines']:
        next_states={}
        for (h,r),(value,path) in states.items():
            for p,e in enumerate(table[line['id']]):
                if upper:
                    if e['status']=='infeasible':continue
                    coefficient=e['upper_bound'] if e['upper_bound'] is not None else math.inf
                else:
                    if e['column'] is None:continue
                    coefficient=e['column']['profit']
                hh,rr=h+e['human'],r+e['robot']
                if hh>data['human_limit'] or rr>data['robot_limit']:continue
                v=value+coefficient
                if (hh,rr) not in next_states or v>next_states[hh,rr][0]:next_states[hh,rr]=(v,path+[dict(line=line['id'],index=p)])
        states=next_states
    if not states:return dict(feasible=False,value=None,path=[],states=0)
    value,path=max(states.values(),key=lambda e:e[0])
    return dict(feasible=True,value=value if math.isfinite(value) else None,path=path,states=len(states))

def run(data,*,time_limit=30,per_profile_seconds=2,solver='cplex_py',restrictions=None,log_dir=None):
    compact.validate_data(data);compact.number(time_limit,'time_limit',0,strict=True)
    compact.number(per_profile_seconds,'per_profile_seconds',0,strict=True)
    policy=NumericPolicy();fix=(restrictions or NodeRestrictions()).validate(data)
    start=time.perf_counter();deadline=start+time_limit;table={};events=[];error=None
    for l in data['lines']:
        table[l['id']]=[dict(human=h,robot=r,status='not_run',upper_bound=None,column=None,certificate=None)
            for h in range(min(len(l['stations']),data['human_limit'])+1)
            for r in range(min(len(l['stations']),data['robot_limit'])+1)]
    work=sorted([(e['human']+e['robot'],e['human'],e['robot'],n,p) for n,l in enumerate(data['lines']) for p,e in enumerate(table[l['id']])])
    cfg=BackendConfig(name=solver,threads=1,seed=11,deadline=deadline,log_dir=str(log_dir) if log_dir else None)
    try:
        with use_backend(cfg,events):
            for _,h,r,n,p in work:
                if time.perf_counter()>=deadline:break
                line=data['lines'][n];entry=table[line['id']][p]
                col,cert=solve_line(line,profile=(h,r),restrictions=fix,purpose='exact_resource_profile',time_limit=min(per_profile_seconds,deadline-time.perf_counter()))
                if col and (col['human']!=h or col['robot']!=r):raise RuntimeError('Exact profile mismatch')
                bound=col['profit'] if cert['optimal'] else cert['solver'].get('best_bound')
                if bound is not None and (not math.isfinite(bound) or abs(bound)>=1e19):bound=None
                if col and bound is not None and bound<col['profit']-policy.bound_consistency_tolerance:raise RuntimeError('Profile bound below witness')
                entry.update(status=cert['status'],column=col,upper_bound=bound,certificate=cert)
    except TimeoutError:pass
    except Exception as exc:error=dict(message=str(exc),traceback=traceback.format_exc())
    lower=dynamic_program(data,table);upper=dynamic_program(data,table,True);witness=None
    if lower['feasible']:
        stations=[s for e in lower['path'] for s in table[e['line']][e['index']]['column']['stations']]
        witness=verify_integer_assignments(data,stations,expected=lower['value'])
    lb=lower['value'];ub=upper['value']
    interrupted=any(e['status'] in ('not_run','time_limit') for es in table.values() for e in es)
    status='solver_error' if error else 'time_limit' if interrupted else 'feasible_unproven' if witness else 'unresolved'
    optimal=False;infeasible=False
    if not error and not upper['feasible']:status='infeasible_proven';infeasible=True
    if lb is not None and ub is not None:
        if ub<lb-policy.bound_consistency_tolerance:raise RuntimeError('DP bound contradiction')
        if not error and ub-lb<=policy.allowance(lb):status='optimal_within_tolerance';optimal=True
    return dict(algorithm='resource_profile_MILP_DP',certificate_version='resource-dp-1',proof_scope='solver_floating_point_tolerances',
        policy=asdict(policy),restrictions=fix.to_records(),table=table,lower_dp=lower,upper_dp=upper,witness=witness,
        global_lower_bound=lb,global_upper_bound=ub,absolute_gap=None if lb is None or ub is None else ub-lb,
        global_integer_optimal_proven=optimal,global_infeasibility_proven=infeasible,status=status,error=error,
        complete_profiles=all(e['status'] in ('optimal','infeasible') for es in table.values() for e in es),
        profile_calls=sum(e['certificate'] is not None for es in table.values() for e in es),
        profile_count=sum(map(len,table.values())),wall_seconds=time.perf_counter()-start,solver_events=events)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('instance',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--time-limit',type=float,default=30);p.add_argument('--solver',choices=['cplex_py','cbc'],default='cplex_py');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);raw=a.instance.read_bytes();(a.output/'instance.json').write_bytes(raw)
    r=run(json.loads(raw.decode('utf-8-sig')),time_limit=a.time_limit,solver=a.solver,log_dir=a.output/'logs')
    (a.output/'result.json.zlib').write_bytes(zlib.compress(json.dumps(r,allow_nan=False).encode()))
    print(json.dumps({k:r[k] for k in ('status','global_lower_bound','global_upper_bound','wall_seconds','profile_calls')}))
