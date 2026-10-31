"""Two new scale probes; immutable previous runs, existing exact implementations."""
import argparse,csv,hashlib,json,os,shutil,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from generate_instances import generate,metadata
from compare_pricing import execute as cg_execute
from fair_compare import arm
from solver_backend import load_cplex,BackendConfig,use_backend,make_solver
from common import compact
import pulp
ROOT=Path(__file__).resolve().parents[1]

def worker(t):
    if t['kind']=='cg': return cg_execute(t)
    data=json.loads(Path(t['input']).read_text());compact.validate_data(data)
    native=load_cplex().Cplex();native.end()
    if t['kind']=='ip':
        r=arm(data,dict(equal_budget_seconds=600,solver_seed=11),'compact_ip',Path(t['logs']))
    else:
        events=[];start=time.perf_counter()
        with use_backend(BackendConfig(name='cplex_py',threads=1,seed=11,deadline=start+60,log_dir=t['logs']),events):
            m=compact.build_model(data)
            for v in m.problem.variables():v.cat=pulp.LpContinuous
            m.problem.solve(make_solver(mip=False,role='compact_lp'))
            r=dict(m.problem.backend_result,wall_time=time.perf_counter()-start)
    Path(t['output']).write_text(json.dumps(r,indent=2,allow_nan=False),encoding='utf-8')

def main(out):
    out.mkdir(parents=True,exist_ok=False)
    for s in ('instances','raw','logs','tasks','source'):(out/s).mkdir()
    hashes={}
    for p in list((ROOT/'code').rglob('*.py'))+list((ROOT/'experiments').glob('*.py')):
        rel=p.relative_to(ROOT);dest=out/'source'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        hashes[str(rel)]=hashlib.sha256(p.read_bytes()).hexdigest()
    (out/'provenance.json').write_text(json.dumps(dict(start_utc=datetime.now(timezone.utc).isoformat(),python=sys.executable,source_sha256=hashes,threads=1,solver_seed=11,python_hash_seed=11,budget_each=600,integer_recovery=False),indent=2))
    entries=[]
    for count in (120,150):
        data,gen=generate(n=count//2,lines=2,seed=11)
        key=f'total{count}_L2_s11';p=out/'instances'/f'{key}.json';p.write_text(json.dumps(data,indent=2))
        entries.append(dict(instance_id=key,factor=count//2,seed=11,metadata=metadata(data),generation=gen,instance=p.name))
    (out/'instances/manifest.json').write_text(json.dumps(entries,indent=2))
    for i,e in enumerate(entries):
        for kind in (('ip','cg','lp') if i==0 else ('cg','ip','lp')):
            key=e['instance_id']+'_'+kind
            t=dict(kind=kind,input=str((out/'instances'/e['instance']).resolve()),output=str((out/'raw'/f'{key}.json').resolve()),logs=str((out/'logs'/key).resolve()),entry=e,version='V2',budget=600,max_iterations=10000)
            p=out/'tasks'/f'{key}.json';p.write_text(json.dumps(t));Path(t['logs']).mkdir()
            print('START',key,datetime.now().isoformat(),flush=True)
            with (out/'logs'/f'{key}.stdout').open('w') as so,(out/'logs'/f'{key}.stderr').open('w') as se:
                completed=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--task',str(p.resolve())],env=dict(os.environ,PYTHONHASHSEED='11'),stdout=so,stderr=se)
            print('DONE',key,'exit',completed.returncode,flush=True)
            if completed.returncode:raise RuntimeError(f'Worker failed: {key}')
    rows=[]
    for e in entries:
        key=e['instance_id'];ip=json.loads((out/'raw'/f'{key}_ip.json').read_text());cg=json.loads((out/'raw'/f'{key}_cg.json').read_text());lp=json.loads((out/'raw'/f'{key}_lp.json').read_text())
        row=dict(instance_id=key,total_tasks=e['metadata']['total_tasks'],stations=e['metadata']['total_stations'],ip_status=ip['status'],ip_optimal=ip['optimal'],ip_time=ip['wall_time'],ip_incumbent=ip['incumbent'],ip_bound=ip['best_bound'],ip_gap=ip['relative_gap'],compact_lp=lp.get('objective') if lp['optimal'] else None,cg_status=cg['status'],cg_converged=cg['converged'],cg_time=cg['wall_time'],cg_lp=cg['lp_objective'],cg_lp_lower=cg['lower_bound'],cg_lp_upper=cg['upper_bound'],cg_gap=cg['final_lp_gap'],cg_iterations=cg['iterations'],cg_columns=cg['columns'],cg_pp_time=cg['pp_time'],cg_native_pp_time=cg['pp_native_time'],cg_phase1_time=cg['phase1_time'],cg_phase2_time=cg['phase2_time'])
        if ip['incumbent'] is not None and cg['upper_bound'] is not None:assert ip['incumbent']<=cg['upper_bound']+1e-4
        if cg['lower_bound'] is not None and row['compact_lp'] is not None:assert cg['lower_bound']<=row['compact_lp']+1e-4
        rows.append(row)
    with (out/'summary.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (out/'summary.json').write_text(json.dumps(rows,indent=2))
    (out/'finished.json').write_text(json.dumps(dict(finished_utc=datetime.now(timezone.utc).isoformat(),checks_passed=True)))
    print(json.dumps(rows,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--task',type=Path);p.add_argument('--out',type=Path);a=p.parse_args()
    if a.task:worker(json.loads(a.task.read_text()))
    else:main(a.out)
