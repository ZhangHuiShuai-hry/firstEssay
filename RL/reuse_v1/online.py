"""Conservative online screen: skip only certified nonpositive-RC Phase-II blocks."""
import argparse,hashlib,json,time,zlib
from pathlib import Path
from proof_cache import ROOT,ProofCache
from engine import run
from persistent_line import LinePricing
from solver_backend import BackendConfig

def solve(data,*,seconds=30,reuse=True,log_dir=None):
    start=time.perf_counter();events=[];calls=[];caches={l['id']:ProofCache(l) for l in data['lines']}
    cfg=BackendConfig(name='cplex_py',threads=1,seed=11,deadline=start+seconds,log_dir=str(log_dir) if log_dir else None)
    pp=LinePricing(cfg,events,warm_start=True)
    def price(line,**kw):
        cache=caches[line['id']];idx=len(calls);phase=kw.get('phase',2);q=None
        if reuse and phase==2 and kw.get('purpose','pricing')=='pricing':
            q=cache.query(line,[kw.get('human_price',0.),kw.get('robot_price',0.)])
        sigma=kw.get('sigma',0.);eps=1e-7
        if q is not None and q['upper'] is not None and q['upper']-sigma<=eps:
            c=dict(line=line['id'],phase=2,human_price=kw['human_price'],robot_price=kw['robot_price'],sigma=sigma,
                   caps=None,optimal=False,status='nonpositive_rc_certified_by_history',column=None,reduced_cost=None,
                   reduced_cost_upper_bound=q['upper']-sigma,bound_certified=True,reuse_proof=q,
                   solver=dict(backend='proof_cache',optimal=False,has_incumbent=False,native_status=None,solver_time=0.),call_index=idx)
            calls.append(c);return None,c
        col,c=pp.solve(line,**kw);c['call_index']=idx;calls.append(c)
        if phase==2 and c['optimal']:cache.add(line,c,str(idx))
        return col,c
    try:
        r=run(data,time_limit=seconds,init_seconds=.5,pricing='rebuild',price_override=price)
    finally:pp.close()
    r.update(reuse_enabled=reuse,pricing_audit_calls=calls,native_pricing_calls=len(events),
             screened_pricing_calls=sum(c.get('bound_certified',False) for c in calls),pricing_native_events=events,
             online_wall_seconds=time.perf_counter()-start)
    return r

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('instance',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=float,default=30);p.add_argument('--no-reuse',action='store_true');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);raw=a.instance.read_bytes();(a.output/'instance.json').write_bytes(raw)
    (a.output/'sources.json').write_text(json.dumps({str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for folder in (ROOT/'RL/reuse_v1',ROOT/'sub',ROOT/'code') for f in folder.rglob('*.py') if not any(v in f.parts for v in ('evidence','__pycache__','.venv'))},indent=2))
    t=time.perf_counter();r=solve(json.loads(raw),seconds=a.seconds,reuse=not a.no_reuse,log_dir=a.output/'logs')
    with (a.output/'result.json.zlib').open('xb') as f:f.write(zlib.compress(json.dumps(r,allow_nan=False).encode()))
    (a.output/'accounting.json').write_text(json.dumps(dict(end_to_end_seconds=time.perf_counter()-t,budget_scope='soft algorithm deadline; final persistence separately accounted',nominal_seconds=a.seconds),indent=2))
    print(json.dumps({k:r[k] for k in ('status','lower_bound','upper_bound','screened_pricing_calls','native_pricing_calls','online_wall_seconds')}))
