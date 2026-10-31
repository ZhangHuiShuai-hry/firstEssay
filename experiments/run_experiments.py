"""Sequential isolated runs, bounded process trees, immutable run directories."""
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from generate_instances import write_suite

ROOT=Path(__file__).resolve().parents[1]


def save_summary(rows,out):
    (out/'summary.json').write_text(json.dumps(rows,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    columns=sorted({k for r in rows for k in r})
    with (out/'summary.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
        writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)


def run(config_path,out,limit=None):
    config=json.loads(config_path.read_text(encoding='utf-8'));out.mkdir(parents=True,exist_ok=False)
    (out/'config.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    for folder in ('raw','tasks','logs','source'): (out/folder).mkdir()
    files=list((ROOT/'code').glob('**/*.py'))+list((ROOT/'experiments').glob('*.py'))
    hashes={}
    for path in files:
        relative=path.relative_to(ROOT);dest=out/'source'/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);hashes[str(relative)]=hashlib.sha256(path.read_bytes()).hexdigest()
    git=subprocess.run(['git','status','--porcelain=v1'],cwd=ROOT,capture_output=True,text=True)
    environment=ROOT/'experiments/runs/environment_confirmed/environment.json'
    if environment.exists():shutil.copy2(environment,out/'environment.json')
    frozen=subprocess.run([sys.executable,'-m','pip','freeze'],capture_output=True,text=True)
    (out/'requirements-lock.txt').write_text(frozen.stdout,encoding='utf-8')
    (out/'provenance.json').write_text(json.dumps(dict(start_utc=datetime.now(timezone.utc).isoformat(),
        python=sys.executable,git_available=git.returncode==0,git_status=git.stdout,git_error=git.stderr,source_sha256=hashes),indent=2),encoding='utf-8')
    manifest=write_suite(config,out/'instances')
    if limit:manifest=manifest[:limit]
    rows=[];total=len(manifest)*len(config['combinations'])
    estimate=dict(cases=len(manifest),jobs=total,hard_wall_upper_seconds=total*config['case_wall_limit'],
                  note='Upper bound, not prediction. Baselines and root have independent budgets; jobs run sequentially.')
    (out/'budget_estimate.json').write_text(json.dumps(estimate,indent=2),encoding='utf-8')
    for entry in manifest:
        for combo in config['combinations']:
            key=entry['instance_id']+'__'+combo['label']
            task=dict(entry=entry,combo=combo,config=config,
                      instance_path=str((out/'instances'/entry['instance']).resolve()),
                      output=str((out/'raw'/(key+'.json')).resolve()),verify=config.get('verify',False))
            path=out/'tasks'/(key+'.json');path.write_text(json.dumps(task,indent=2),encoding='utf-8')
            begin=time.perf_counter();timed_out=False
            with (out/'logs'/(key+'.stdout')).open('w') as stdout,(out/'logs'/(key+'.stderr')).open('w') as stderr:
                process=subprocess.Popen([sys.executable,str(ROOT/'experiments/worker.py'),'--task',str(path.resolve())],stdout=stdout,stderr=stderr,cwd=ROOT)
                try:exit_code=process.wait(timeout=config['case_wall_limit'])
                except subprocess.TimeoutExpired:
                    timed_out=True
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    exit_code=process.wait()
            raw=Path(task['output'])
            row=json.loads(raw.read_text(encoding='utf-8'))['summary'] if raw.exists() else dict(instance_id=entry['instance_id'],solver_combo=combo['label'],group=entry['group'],factor=entry['factor'],seed=entry['seed'])
            row.update(process_exit_code=exit_code,process_wall_time=time.perf_counter()-begin,process_timeout=timed_out)
            if exit_code!=0:
                row['execution_status']='wall_timeout' if timed_out else 'worker_exception'
                stage=json.loads(raw.read_text(encoding='utf-8')).get('current_stage') if raw.exists() else None
                row['interrupted_stage']=stage
                if stage=='cg':row.update(cg_status='time_limit' if timed_out else 'numerical_or_solver_exception',cg_converged=False)
                if stage=='verification':row['verification_status']='error'
                if stage=='compact_ip':row['milp_status']='time_limit' if timed_out else 'solver_exception'
                if stage=='compact_lp':row['compact_lp_status']='time_limit' if timed_out else 'solver_exception'
            else:row['execution_status']='complete'
            rows.append(row);save_summary(rows,out)
            print(f"[{len(rows)}/{total}] {key}: {row.get('cg_status')} LP={row.get('cg_lp_obj')} verify={row.get('verification_status')}",flush=True)
    (out/'finished.json').write_text(json.dumps(dict(finish_utc=datetime.now(timezone.utc).isoformat(),completed_jobs=len(rows))),encoding='utf-8')
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--limit',type=int)
    a=p.parse_args();rows=run(a.config,a.out,a.limit)
    stage_a=json.loads(a.config.read_text(encoding='utf-8'))['design']=='stage_a'
    failed=any(r.get('execution_status')!='complete' or (stage_a and r.get('verification_status')!='passed') for r in rows)
    raise SystemExit(1 if failed else 0)
