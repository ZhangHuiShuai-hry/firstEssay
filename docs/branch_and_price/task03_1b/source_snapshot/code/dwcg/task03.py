"""Version switches without monkeypatch or shared native node state."""
from functools import partial
from branch_price_engine import run_branch_price
from node_master_v0 import solve_node as legacy
from node_master_optimized import solve_node as optimized


def run(data,version='V0',**kwargs):
    if version not in ('V0','V1','V2','V3'):raise ValueError('Available versions: V0, V1, V2, V3')
    import time
    started=time.perf_counter();seed=None;acquisition=None
    from node_state import NumericPolicy
    policy=kwargs.get('policy') or NumericPolicy()
    from pathlib import Path
    output=Path(kwargs['output_dir']) if kwargs.get('output_dir') else None
    if output and output.exists():raise FileExistsError(output)
    if version=='V3':
        from common import compact,blocks
        from bp_solution import verify_integer_assignments
        from solver_backend import BackendConfig,use_backend,make_solver
        from pathlib import Path
        budget=kwargs.get('time_limit',300.)
        warm_logs=str(output.parent/(output.name+'_acquisition_logs')) if output else None
        if warm_logs:Path(warm_logs).mkdir(parents=True,exist_ok=False)
        with use_backend(BackendConfig(name=kwargs.get('solver','cbc'),deadline=started+min(2.,budget*.2),log_dir=warm_logs,
             primal_tolerance=policy.lp_primal_tolerance,dual_tolerance=policy.lp_dual_tolerance,
             mip_integrality_tolerance=policy.pricing_integrality_tolerance)):
            try:
                model=compact.build_model(data);model.problem.solve(make_solver(role='compact_ip'))
                acquisition=dict(model.problem.backend_result)
                if acquisition['has_incumbent']:
                    stations=[{'line':l['id'],'station':s,'assignments':[(i,m) for (li,i,ss,m),v in model.x.items() if li==l['id'] and ss==s and v.value()>.5]} for l,s in blocks(data)]
                    seed=verify_integer_assignments(data,stations,policy=policy,expected=acquisition['objective'])
            except Exception as e:acquisition={'error':repr(e)}
        kwargs['time_limit']=max(1e-12,budget-(time.perf_counter()-started))
    warm_seconds=time.perf_counter()-started
    incremental=kwargs.pop('incremental_evidence',False)
    solver=legacy if version=='V0' and not incremental else partial(optimized,version='V2' if version=='V3' else version,incremental_evidence=incremental,round_sink=kwargs.get('evidence_sink') if incremental else None)
    metrics=[]
    def measured(*args,**kw):
        r=solver(*args,**kw)
        pp=sum(p.get('solve_seconds',0) for row in r.certificate.rounds for p in row.get('pricing',[]))
        rm=sum(e.get('wall_time',0) for e in r.certificate.solver_events if e.get('role')=='rmp')
        metrics.append(getattr(r.certificate,'timings',dict(pp_wall=pp,rmp_solve_read=rm,other=max(0,r.solve_seconds-pp-rm),node_total=r.solve_seconds)))
        return r
    result=run_branch_price(data,_node_solver=measured,seed_solution=seed,**kwargs)
    result['wall_time']+=warm_seconds
    result['acquisition']={'mode':'compact_warm_start' if version=='V3' else 'off','seconds':warm_seconds,'solver_result':acquisition}
    updates=[n['elapsed_at_completion'] for n in result['node_history'] if n.get('incumbent_update')]
    result['first_integer_seconds']=warm_seconds if seed else warm_seconds+min(updates) if updates else None
    result['task03_version']=version
    if version=='V3':result['certificate_version']=2
    result['component_timings']=metrics
    import hashlib
    from pathlib import Path
    result['adapter_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py') if 'node_' in p.name or p.name in ('task03.py','branch_price_engine.py')}
    return result


def main():
    import argparse,json,sys
    from pathlib import Path
    from dataclasses import asdict
    from common import compact
    from node_state import NumericPolicy
    p=argparse.ArgumentParser(description='Task03 exact B&P version switches')
    p.add_argument('instance',type=Path);p.add_argument('--version',choices=('V0','V1','V2','V3'),default='V2')
    p.add_argument('--solver',choices=('cbc','cplex_py'),default='cplex_py');p.add_argument('--time-limit',type=float,default=300)
    p.add_argument('--node-limit',type=int,default=10000);p.add_argument('--max-cg-iterations',type=int,default=1000)
    p.add_argument('--numeric-policy',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--verbose',action='store_true')
    args=p.parse_args()
    try:
        detail=args.output.parent/(args.output.stem+'_files')
        if args.output.exists() or detail.exists():raise FileExistsError('Output or detail directory exists')
        data=json.loads(args.instance.read_text(encoding='utf-8-sig'));compact.validate_data(data)
        compact.number(args.time_limit,'time_limit',0,strict=True);compact.integer(args.node_limit,'node_limit',0)
        compact.integer(args.max_cg_iterations,'max_cg_iterations',1)
        policy=NumericPolicy(**json.loads(args.numeric_policy.read_text())) if args.numeric_policy else NumericPolicy()
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x',encoding='utf-8') as f:json.dump({'status':'running'},f)
        r=run(data,args.version,solver=args.solver,time_limit=args.time_limit,node_limit=args.node_limit,
              max_cg_iterations=args.max_cg_iterations,policy=policy,output_dir=detail,verbose=args.verbose)
        (detail/'instance.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
        (detail/'config.json').write_text(json.dumps(dict(argv=sys.argv,numeric_policy=asdict(policy)),indent=2))
        args.output.write_text(json.dumps(r,indent=2,allow_nan=False),encoding='utf-8')
        print(json.dumps({k:r[k] for k in ('status','global_lower_bound','global_upper_bound','absolute_gap','wall_time')},indent=2))
        return 0 if r['status'] in ('optimal_within_tolerance','infeasible_proven') else 1 if r['status']=='solver_error' else 2
    except Exception as e:p.exit(1,str(e)+'\n')
if __name__=='__main__':raise SystemExit(main())
