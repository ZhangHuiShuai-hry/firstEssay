"""Fixed-dual mechanism probe; no changes to production solvers."""
import argparse,hashlib,json,sys,time,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE.parent),str(HERE.parent/'stage3')]
from persistent_line import LinePricing
from line_cg import solve_line
from solver_backend import BackendConfig,use_backend
from validate import check_column
def save(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False)
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    snapshots=[]
    for seed in (32,33,34,31):
        folder=HERE.parent/(f'stage12/evidence/formal600/tasks120_lines06_conflict_candidate_seed{seed}__balanced_bound' if seed!=31 else 'stage11/evidence/pilot120/tasks080_lines02_conflict_candidate_seed31__balanced_bound')
        blob=(folder/'result.json.zlib').read_bytes();r=json.loads(zlib.decompress(blob));d=json.loads((folder/'instance.json').read_bytes())
        cs=[c for h in r['base_result']['cg']['history'] if h['phase']==2 for c in h['pricing']]
        c=max(cs,key=lambda v:v['solver']['solver_time']) if seed!=31 else cs[0]
        line=next(l for l in d['lines'] if l['id']==c['line'])
        snapshots.append(dict(seed=seed,line=line,certificate=c,source=str(folder.relative_to(ROOT)),source_sha256=hashlib.sha256(blob).hexdigest()))
    save(a.output/'snapshots.json',snapshots);rows=[]
    for snap in snapshots:
        for repeat in (0,1):
            variants=['rebuild','persistent_no_explicit_start','persistent_explicit_start'];variants=variants[repeat:]+variants[:repeat]
            for variant in variants:
                line=snap['line'];source=snap['certificate'];events=[];dest=a.output/f"seed{snap['seed']}_r{repeat}_{variant}";dest.mkdir()
                cfg=BackendConfig(name='cplex_py',threads=1,seed=11,log_dir=str(dest/'logs'))
                session=None;tick=time.perf_counter();setup=None
                try:
                    with use_backend(cfg,events):
                        if variant!='rebuild':
                            session=LinePricing(cfg,events,warm_start=variant=='persistent_explicit_start')
                            _,setup=session.solve(line,phase=2,time_limit=3,purpose='probe_setup')
                        target_start=time.perf_counter()
                        price=solve_line if session is None else session.solve
                        col,cert=price(line,phase=2,human_price=source['human_price'],robot_price=source['robot_price'],sigma=source['sigma'],time_limit=5,purpose='fixed_dual_probe')
                        target=time.perf_counter()-target_start
                    if col:
                        v=check_column(line,col);rc=v['profit']-source['human_price']*col['human']-source['robot_price']*col['robot']-source['sigma'];assert abs(rc-cert['reduced_cost'])<=1e-5
                    known=source['reduced_cost'] if source['optimal'] else None;bound=cert['solver']['best_bound'];inc=cert['reduced_cost']
                    if known is not None:
                        if inc is not None:assert inc<=known+1e-5
                        if bound is not None:assert bound>=known-1e-5
                        if cert['optimal']:assert abs(inc-known)<=1e-5
                    if inc is not None and bound is not None:assert bound>=inc-1e-5
                    row=dict(seed=snap['seed'],repeat=repeat,variant=variant,target_seconds=target,total_seconds=time.perf_counter()-tick,known_optimum=known,incumbent=inc,best_bound=bound,optimal=cert['optimal'],at_known_optimum_but_unproven=bool(known is not None and inc is not None and abs(known-inc)<=1e-5 and not cert['optimal']),first_positive_rc_seconds=None,first_positive_rc_status='NOT MEASURED',certificate=cert,setup=setup,status='PASS')
                    rows.append(row);save(dest/'result.json',row);print(json.dumps({k:v for k,v in row.items() if k not in ('certificate','setup')}),flush=True)
                finally:
                    if session:session.close()
    save(a.output/'results.json',dict(status='PASS',rows=rows,scope='independent column arithmetic and saved/native bounds; limited fixed-dual development snapshots'))
if __name__=='__main__':main()
