"""Fixed-state discrete action experiment; all states are development data."""
import argparse,hashlib,json,sys,time,zlib
from pathlib import Path
from pricing_actions import ALPHAS,prices,exact_upper_bound,ROOT
sys.path.insert(0,str(ROOT/'sub/stage3'))
from persistent_line import LinePricing
from solver_backend import BackendConfig,use_backend
def save(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False)
def snapshots():
    ans=[]
    for seed in (32,34,31):
        folder=ROOT/(f'sub/stage12/evidence/formal600/tasks120_lines06_conflict_candidate_seed{seed}__balanced_bound' if seed!=31 else 'sub/stage11/evidence/pilot120/tasks080_lines02_conflict_candidate_seed31__balanced_bound')
        blob=(folder/'result.json.zlib').read_bytes();data=json.loads((folder/'instance.json').read_bytes());cg=json.loads(zlib.decompress(blob))['base_result']['cg'];hist=cg['history'];indices=[i for i,h in enumerate(hist) if h['phase']==2 and h['pricing']]
        for label,i in [('early',indices[0])]+([] if seed==31 else [('late',indices[-1])]):
            h=hist[i];prev=[v for v in hist[:i] if v['phase']==2 and v['complete_exact_pricing'] and v['repaired_upper_bound'] is not None]
            ref=min(prev,key=lambda v:v['repaired_upper_bound'])['rmp']['duals'] if prev else dict(human=0.,robot=0.)
            ans.append(dict(id=f'seed{seed}_{label}',data=data,source=str(folder.relative_to(ROOT)),source_sha256=hashlib.sha256(blob).hexdigest(),history_index=i,current=[max(0.,h['rmp']['duals'][k]) for k in ('human','robot')],reference=[max(0.,ref[k]) for k in ('human','robot')],rmp=h['rmp'],pool={l:cg['pool'][l][:n] for l,n in h['rmp']['pool_sizes'].items()}))
    return ans
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    states=[s for s in snapshots() if s["id"]=="seed32_late"];save(a.output/'states.json',states);save(a.output/'sources.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for directory in (ROOT/'RL',ROOT/'sub',ROOT/'code') for p in directory.rglob('*.py') if not any(v in p.parts for v in ('evidence','__pycache__','.venv'))})
    rows=[]
    for si,s in enumerate(states):
        for rep in range(1):
            order=list(ALPHAS);rot=(si+rep)%4;order=order[rot:]+order[:rot]
            for alpha in order:
                dest=a.output/f"{s['id']}_r{rep}_a{alpha}";dest.mkdir();events=[];cfg=BackendConfig(name='cplex_py',threads=1,seed=11,log_dir=str(dest/'logs'));pp=LinePricing(cfg,events,warm_start=True);start=time.perf_counter();target=0.;cs=[];setup=[];new_positive=0;price=prices(s['current'],s['reference'],alpha)
                try:
                    with use_backend(cfg,events):
                        for line in s['data']['lines']:
                            _,init=pp.solve(line,phase=2,time_limit=.5,purpose='action_setup');setup.append(init)
                            tick=time.perf_counter();col,c=pp.solve(line,phase=2,human_price=price[0],robot_price=price[1],sigma=0,time_limit=10,purpose='action_probe');target+=time.perf_counter()-tick;cs.append(c)
                            if col:
                                rawrc=col['profit']-s['current'][0]*col['human']-s['current'][1]*col['robot']-s['rmp']['duals']['convexity'][line['id']]
                                fresh=not any(v['stations']==col['stations'] for v in s['pool'][line['id']])
                                if rawrc>1e-7 and fresh:new_positive+=1
                    ub=exact_upper_bound(s['data'],price,cs)
                    row=dict(state=s['id'],repeat=rep,alpha=alpha,prices=price,total_seconds=time.perf_counter()-start,target_seconds=target,complete_exact=all(c['optimal'] for c in cs),exact_lp_upper_bound=ub,proven_blocks=sum(c['optimal'] for c in cs),new_positive_columns=new_positive,certificates=cs,setup=setup,global_integer_optimal_proven=False,scope='fixed-state local action probe; not an online CG trajectory or RL policy')
                    rows.append(row);save(dest/'result.json',row);print(json.dumps({k:v for k,v in row.items() if k not in ('certificates','setup')}),flush=True)
                finally:pp.close()
    save(a.output/'results.json',dict(status='COMPLETED',rows=rows))
if __name__=='__main__':main()
