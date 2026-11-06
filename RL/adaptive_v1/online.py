"""Non-learning online policies. Candidate objectives never certify raw pricing."""
import argparse,hashlib,json,sys,time,zlib
from pathlib import Path
from engine import run
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'RL/reuse_v1'))
from proof_cache import ProofCache
from persistent_line import LinePricing
from solver_backend import BackendConfig
POLICIES=('exact','short_raw','fixed','adaptive')

def solve(data,*,seconds=30,policy_name='exact',log_dir=None):
    if policy_name not in POLICIES:raise ValueError('Unknown policy')
    start=time.perf_counter();deadline=start+seconds;events=[];calls=[];caches={l['id']:ProofCache(l) for l in data['lines']}
    cfg=BackendConfig(name='cplex_py',threads=1,seed=11,deadline=deadline,log_dir=str(log_dir) if log_dir else None)
    pp=LinePricing(cfg,events,warm_start=True);candidate_spent=0.;candidate_rounds=0
    def price(line,**kw):
        cache=caches[line['id']];idx=len(calls);phase=kw.get('phase',2);q=None
        if phase==2 and kw.get('purpose','pricing')=='pricing':q=cache.query(line,[kw.get('human_price',0.),kw.get('robot_price',0.)])
        sigma=kw.get('sigma',0.)
        if q is not None and q['upper'] is not None and q['upper']-sigma<=1e-7:
            c=dict(line=line['id'],phase=2,human_price=kw['human_price'],robot_price=kw['robot_price'],sigma=sigma,
                   caps=None,optimal=False,status='nonpositive_rc_certified_by_history',column=None,reduced_cost=None,
                   reduced_cost_upper_bound=q['upper']-sigma,bound_certified=True,reuse_proof=q,
                   solver=dict(backend='proof_cache',optimal=False,has_incumbent=False,native_status=None,solver_time=0.),call_index=idx)
            calls.append(c);return None,c
        col,c=pp.solve(line,**kw);c['call_index']=idx;calls.append(c)
        if phase==2 and c['optimal']:cache.add(line,c,str(idx))
        return col,c
    def candidates(data,master,result):
        nonlocal candidate_spent,candidate_rounds
        cap=.2*seconds
        if candidate_spent>=cap-.01 or deadline-time.perf_counter()<.02:return None
        alpha=1. if policy_name=='short_raw' or (policy_name=='adaptive' and candidate_rounds>0) else .25
        prev=[(i,h) for i,h in enumerate(result['history'][:-1]) if h['phase']==2 and h['complete_certified_pricing'] and h['repaired_upper_bound'] is not None]
        selected=min(prev,key=lambda x:x[1]['repaired_upper_bound']) if prev else None
        ref=[selected[1]['rmp']['duals'][k] for k in ('human','robot')] if selected else [0.,0.]
        current=[master['duals'][k] for k in ('human','robot')];p=[alpha*x+(1-alpha)*y for x,y in zip(current,ref)]
        action=dict(alpha=alpha,reference=ref,reference_history_index=selected[0] if selected else None,
                    current=current,price=p,candidate_round=candidate_rounds,budget_before=candidate_spent)
        cs=[];candidate_rounds+=1
        for pos,line in enumerate(data['lines']):
            share=min(2.,(cap-candidate_spent)/(len(data['lines'])-pos),(deadline-time.perf_counter())/(len(data['lines'])-pos))
            if share<=.001:break
            tick=time.perf_counter()
            try:
                _,c=price(line,phase=2,human_price=p[0],robot_price=p[1],sigma=0.,time_limit=share,purpose='candidate')
                cs.append(c)
            finally:candidate_spent+=time.perf_counter()-tick
        action['budget_after']=candidate_spent
        return dict(action=action,certificates=cs)
    try:r=run(data,time_limit=seconds,init_seconds=.5,pricing='rebuild',price_override=price,candidate_override=None if policy_name=='exact' else candidates)
    finally:pp.close()
    r.update(policy_name=policy_name,pricing_strategy='persistent_warm_with_history_screen',pricing_audit_calls=calls,
             native_pricing_calls=len(events),screened_pricing_calls=sum(c.get('bound_certified',False) for c in calls),
             pricing_native_events=events,candidate_seconds=candidate_spent,online_wall_seconds=time.perf_counter()-start)
    r['timing']['PP_native_seconds']=sum(e['solver_time'] for e in events)
    return r

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('instance',type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--seconds',type=float,default=60);p.add_argument('--policy',choices=POLICIES,default='exact');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);raw=a.instance.read_bytes();(a.output/'instance.json').write_bytes(raw)
    (a.output/'sources.json').write_text(json.dumps({str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for folder in (ROOT/'RL',ROOT/'sub',ROOT/'code') for f in folder.rglob('*.py') if not any(v in f.parts for v in ('evidence','__pycache__','.venv'))},indent=2))
    t=time.perf_counter();r=solve(json.loads(raw),seconds=a.seconds,policy_name=a.policy,log_dir=a.output/'logs')
    with (a.output/'result.json.zlib').open('xb') as f:f.write(zlib.compress(json.dumps(r,allow_nan=False).encode()))
    (a.output/'accounting.json').write_text(json.dumps(dict(end_to_end_seconds=time.perf_counter()-t,nominal_seconds=a.seconds,scope='soft algorithm deadline, final persistence additionally accounted'),indent=2))
    print(json.dumps({k:r[k] for k in ('policy_name','status','lower_bound','upper_bound','native_pricing_calls','screened_pricing_calls','candidate_seconds','online_wall_seconds')}))
