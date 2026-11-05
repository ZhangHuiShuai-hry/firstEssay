"""CG证书引导的按需资源档MILP+整数DP。保留未知档，不截断成不可行。"""
import sys,time,math,json,zlib,argparse,traceback
from pathlib import Path
from copy import deepcopy
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent/'stage3'),str(HERE.parent/'stage6')]
import importlib.util
spec=importlib.util.spec_from_file_location('cg_seed_stage3',HERE.parent/'stage3/solver.py')
seed_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(seed_module)
from resource_dp import dynamic_program
from profile_pp import solve_line
from line_cg import compact,NumericPolicy,BackendConfig,use_backend,verify_integer_assignments

def bound_sources(data,cg):
    sources={l['id']:[] for l in data['lines']}
    for e in cg['initialization']:
        b=e['column']['profit'] if e['optimal'] else e['solver'].get('best_bound')
        if b is not None and math.isfinite(b) and abs(b)<1e19:sources[e['line']].append(dict(kind='economic_initialization',constant=b,human=0.,robot=0.))
    for h in cg['history']:
        if h['phase']!=2 or not h['complete_exact_pricing']:continue
        d=h['rmp']['duals']
        for e in h['pricing']:
            sources[e['line']].append(dict(kind='complete_phase2_pricing',iteration=h['iteration'],
                constant=d['convexity'][e['line']]+max(0.,e['reduced_cost']),human=d['human'],robot=d['robot']))
    return sources

def initial_table(data,cg,sources):
    table={}
    for l in data['lines']:
        lid=l['id'];rows=[]
        for h in range(min(len(l['stations']),data['human_limit'])+1):
            for r in range(min(len(l['stations']),data['robot_limit'])+1):
                bounds=[e['constant']+e['human']*h+e['robot']*r for e in sources[lid]]
                candidates=[c for c in cg['pool'][lid] if c['human']==h and c['robot']==r]
                col=deepcopy(max(candidates,key=lambda c:c['profit'])) if candidates else None
                rows.append(dict(human=h,robot=r,status='seeded' if col else 'not_run',
                    upper_bound=min(bounds) if bounds else None,column=col,attempts=0))
        table[lid]=rows
    return table

def update(entry,cert,tol):
    col=cert['column'];bound=col['profit'] if cert['optimal'] else cert['solver'].get('best_bound')
    if cert['status']=='infeasible':
        if entry['column']:raise RuntimeError('Infeasibility contradicts existing profile witness')
        entry.update(status='infeasible',upper_bound=None)
    else:
        if col and (entry['column'] is None or col['profit']>entry['column']['profit']):entry['column']=col
        if bound is not None and math.isfinite(bound) and abs(bound)<1e19:
            entry['upper_bound']=bound if entry['upper_bound'] is None else min(bound,entry['upper_bound'])
        entry['status']=cert['status']
        if entry['column'] and entry['upper_bound'] is not None and entry['upper_bound']<entry['column']['profit']-tol:
            raise RuntimeError('Profile bound below validated incumbent')
    entry['attempts']+=1

def run(data,*,time_limit=30,cg_fraction=.35,cg_cap_seconds=6,per_profile_seconds=2,solver='cplex_py',log_dir=None):
    compact.validate_data(data)
    for key,value in [('time_limit',time_limit),('cg_cap_seconds',cg_cap_seconds),('per_profile_seconds',per_profile_seconds)]:compact.number(value,key,0,strict=True)
    if not 0<cg_fraction<1:raise ValueError('cg_fraction must be between zero and one')
    policy=NumericPolicy();start=time.perf_counter();deadline=start+time_limit
    cg=seed_module.run(data,time_limit=min(cg_cap_seconds,time_limit*cg_fraction),solver=solver,
        pricing='warm' if solver=='cplex_py' else 'rebuild',init_seconds=.5,quota=False,
        log_dir=Path(log_dir)/'cg' if log_dir else None)
    sources=bound_sources(data,cg);table=initial_table(data,cg,sources);queries=[];events=[];error=None
    r=dict(algorithm='CG_guided_demand_resource_profiles',certificate_version='demand-profiles-1',proof_scope='solver_floating_point_tolerances',
        policy=cg['policy'],cg=cg,bound_sources=sources,table=table,queries=queries,witness=None,
        global_lower_bound=None,global_upper_bound=None,global_integer_optimal_proven=False,global_infeasibility_proven=False,
        status='not_solved',first_integer_seconds=None,incumbent_history=[],error=None)
    def account():
        low=dynamic_program(data,table);up=dynamic_program(data,table,True)
        if low['feasible'] and (r['global_lower_bound'] is None or low['value']>r['global_lower_bound']):
            stations=[s for e in low['path'] for s in table[e['line']][e['index']]['column']['stations']]
            w=verify_integer_assignments(data,stations,expected=low['value'])
            r.update(witness=w,global_lower_bound=w['objective'])
            elapsed=time.perf_counter()-start;r['incumbent_history'].append(dict(seconds=elapsed,objective=w['objective']))
            if r['first_integer_seconds'] is None:r['first_integer_seconds']=elapsed
        ub=up['value'];cgub=cg['upper_bound']
        if cgub is not None:ub=cgub if ub is None else min(ub,cgub)
        r['global_upper_bound']=ub;r['lower_dp']=low;r['upper_dp']=up
        if r['global_lower_bound'] is not None and ub is not None and ub<r['global_lower_bound']-policy.bound_consistency_tolerance:raise RuntimeError('Global bound contradiction')
        if cg['global_infeasibility_proven'] or not up['feasible']:
            r.update(status='infeasible_proven',global_infeasibility_proven=True);return True
        if r['global_lower_bound'] is not None and ub is not None and ub-r['global_lower_bound']<=policy.allowance(r['global_lower_bound']):
            r.update(status='optimal_within_tolerance',global_integer_optimal_proven=True);return True
        return False
    cfg=BackendConfig(name=solver,deadline=deadline,threads=1,seed=11,log_dir=str(Path(log_dir)/'profiles') if log_dir else None)
    try:
        with use_backend(cfg,events):
            while True:
                if account():break
                if time.perf_counter()>=deadline:r['status']='time_limit';break
                path=r['upper_dp']['path']
                unresolved=[e for e in path if table[e['line']][e['index']]['status'] not in ('optimal','infeasible')]
                if not unresolved:r['status']='numerical_uncertain';break
                choice=min(unresolved,key=lambda e:(table[e['line']][e['index']]['attempts'],e['line'],e['index']))
                entry=table[choice['line']][choice['index']];line=next(l for l in data['lines'] if l['id']==choice['line'])
                record=dict(choice=choice,upper_path=deepcopy(path),upper_value=r['upper_dp']['value'],certificate=None)
                queries.append(record)
                _,cert=solve_line(line,profile=(entry['human'],entry['robot']),purpose='demand_resource_profile',
                    time_limit=min(per_profile_seconds*2**min(entry['attempts'],8),deadline-time.perf_counter()))
                record['certificate']=cert;update(entry,cert,policy.bound_consistency_tolerance)
    except TimeoutError:r['status']='time_limit'
    except Exception as exc:r.update(status='solver_error',error=dict(message=str(exc),traceback=traceback.format_exc()))
    # 最后一次已完成查询仍可产生真实LB/有效UB；异常时不提升证明标记。
    if r['error'] is None:account()
    r.update(absolute_gap=None if r['global_lower_bound'] is None or r['global_upper_bound'] is None else r['global_upper_bound']-r['global_lower_bound'],
        profile_calls=sum(q['certificate'] is not None for q in queries),profile_count=sum(map(len,table.values())),
        queried_profiles=sum(e['attempts']>0 for es in table.values() for e in es),wall_seconds=time.perf_counter()-start,solver_events=events)
    return r

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('instance',type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--time-limit',type=float,default=30);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);raw=a.instance.read_bytes();(a.output/'instance.json').write_bytes(raw)
    result=run(json.loads(raw.decode('utf-8-sig')),time_limit=a.time_limit,log_dir=a.output/'logs')
    (a.output/'result.json.zlib').write_bytes(zlib.compress(json.dumps(result,allow_nan=False).encode()))
    print(json.dumps({k:result[k] for k in ('status','global_lower_bound','global_upper_bound','profile_calls','wall_seconds')}))
