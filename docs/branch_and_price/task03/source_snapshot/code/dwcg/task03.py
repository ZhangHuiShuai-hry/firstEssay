"""Version switches without monkeypatch or shared native node state."""
from functools import partial
from branch_price_engine import run_branch_price
from node_master_v0 import solve_node as legacy
from node_master_optimized import solve_node as optimized


def run(data,version='V0',**kwargs):
    if version not in ('V0','V1','V2','V3'):raise ValueError('Available versions: V0, V1, V2, V3')
    import time
    started=time.perf_counter();seed=None;acquisition=None
    if version=='V3':
        from common import compact,blocks
        from bp_solution import verify_integer_assignments
        from solver_backend import BackendConfig,use_backend,make_solver
        from pathlib import Path
        budget=kwargs.get('time_limit',300.)
        warm_logs=str(Path(kwargs['output_dir']).parent/'acquisition_logs') if kwargs.get('output_dir') else None
        with use_backend(BackendConfig(name=kwargs.get('solver','cbc'),deadline=started+min(2.,budget*.2),log_dir=warm_logs)):
            try:
                model=compact.build_model(data);model.problem.solve(make_solver(role='compact_ip'))
                acquisition=dict(model.problem.backend_result)
                if acquisition['has_incumbent']:
                    stations=[{'line':l['id'],'station':s,'assignments':[(i,m) for (li,i,ss,m),v in model.x.items() if li==l['id'] and ss==s and v.value()>.5]} for l,s in blocks(data)]
                    seed=verify_integer_assignments(data,stations,expected=acquisition['objective'])
            except Exception as e:acquisition={'error':repr(e)}
        kwargs['time_limit']=max(1e-12,budget-(time.perf_counter()-started))
    warm_seconds=time.perf_counter()-started
    solver=legacy if version=='V0' else partial(optimized,version='V2' if version=='V3' else version)
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
