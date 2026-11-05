"""120秒连续轨迹诊断。预算包括导入/建模/核验/证据写入；Windows软限时。"""
import argparse,hashlib,json,os,subprocess,sys,time,traceback,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(HERE.parent),str(HERE.parent/'stage3'),str(HERE.parent/'stage6'),str(HERE.parent/'stage7')]

def dump(path,value):
    raw=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False).encode()
    temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    temp.replace(path)

def sha(raw):return hashlib.sha256(raw).hexdigest()

def worker(a):
    start=time.perf_counter();a.output.mkdir(parents=True,exist_ok=False)
    raw=a.instance.read_bytes();(a.output/'instance.json').write_bytes(raw)
    data=json.loads(raw.decode('utf-8-sig'));trace=[]
    def progress(kind,lb,ub,details):
        row=dict(seconds=time.perf_counter()-start,kind=kind,lower_bound=lb,upper_bound=ub,**details)
        trace.append(row)
        with (a.output/'progress.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,allow_nan=False)+'\n');f.flush()
    try:
        if a.worker=='compact_plain':from compact_solver import run
        elif a.worker=='compact':from compact_traced import run
        elif a.worker=='cg':from cg_traced import run
        else:from demand_traced import run
        kwargs=dict(pricing='warm',init_seconds=.5,quota=False) if a.worker=='cg' else dict(cg_fraction=.9,cg_cap_seconds=1000000) if a.worker=='root_first' else {}
        observe={} if a.worker=='compact_plain' else dict(progress=progress)
        result=run(data,time_limit=max(.001,a.budget-3-(time.perf_counter()-start)),log_dir=a.output/'logs',**observe,**kwargs)
        if a.worker=='cg':result.update(global_lower_bound=result['lower_bound'],global_upper_bound=result['upper_bound'])
        result['progress_trace']=trace
        tick=time.perf_counter();blob=zlib.compress(json.dumps(result,allow_nan=False).encode())
        with (a.output/'result.json.zlib').open('xb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
        persistence=time.perf_counter()-tick
        source_manifest=json.loads(a.sources.read_bytes()) if a.sources else {}
        summary={k:result.get(k) for k in ('status','global_lower_bound','global_upper_bound','absolute_gap','global_integer_optimal_proven','global_infeasibility_proven','wall_seconds','algorithm_seconds','first_integer_seconds','first_verified_integer_seconds','profile_calls')}
        summary.update(method=a.worker,input_sha256=sha(raw),evidence_sha256=sha(blob),source_sha256=source_manifest,
            persistence_seconds=persistence,evidence_bytes=len(blob),uncompressed_bytes=len(zlib.decompress(blob)),worker_seconds=time.perf_counter()-start,
            settings=dict(budget=a.budget,reserve=3,threads=1,seed=11,solver='CPLEX 22.1.1.0',gap=0,**kwargs))
        dump(a.output/'summary.json',summary)
    except Exception as e:
        dump(a.output/'error.json',dict(error=repr(e),traceback=traceback.format_exc()));raise

def cases():
    return [HERE.parent/'evidence/inputs_v1'/n for n in ('existing40_original.json','tasks040_lines02_seed12.json','tasks040_lines02_seed13.json')]+[HERE.parent/'stage5/evidence/inputs/tasks020_lines04_tight_seed11.json']

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--worker',choices=['compact','compact_plain','cg','demand','root_first']);p.add_argument('--instance',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--budget',type=float,default=600);p.add_argument('--sources',type=Path);p.add_argument('--limit-cases',type=int,default=1);a=p.parse_args()
    if a.worker:return worker(a)
    a.output.mkdir(parents=True,exist_ok=False);rows=[]
    setup=time.perf_counter()
    source_paths=set(HERE.parent.rglob('*.py'))|set((ROOT/'code/dwcg').glob('*.py'))|set((ROOT/'code/milp').glob('*.py'))|{ROOT/'code/solver_backend.py'}
    source_paths={p for p in source_paths if 'evidence' not in p.parts}
    source_manifest={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(source_paths)}
    source_file=a.output/'sources.json';dump(source_file,source_manifest)
    dump(a.output/'preparation.json',dict(source_freeze_seconds=time.perf_counter()-setup,scope='one_time_experiment_preparation_outside_per_method_budget'))
    frozen=a.output/'inputs';frozen.mkdir()
    for n,case in enumerate(cases()[:a.limit_cases]):
        target=frozen/case.name;target.write_bytes(case.read_bytes())
        methods=['compact_plain','root_first']
        for method in methods:
            dest=a.output/(case.stem+'__'+method);tick=time.perf_counter();hard=False
            with (a.output/(dest.name+'.stdout.txt')).open('w',encoding='utf-8') as log:
                proc=subprocess.Popen([sys.executable,__file__,'--worker',method,'--instance',str(target),'--output',str(dest),'--budget',str(a.budget),'--sources',str(source_file)],stdout=log,stderr=subprocess.STDOUT)
                try:code=proc.wait(timeout=a.budget+5)
                except subprocess.TimeoutExpired:proc.kill();proc.wait();hard=True;code=proc.returncode
            elapsed=time.perf_counter()-tick
            summary=json.loads((dest/'summary.json').read_bytes()) if (dest/'summary.json').exists() else {}
            if summary:assert summary['input_sha256']==sha(target.read_bytes())
            row=dict(case=case.stem,**summary,end_to_end_seconds=elapsed,timely=elapsed<=a.budget and code==0,hard_stop=hard,exit_code=code)
            rows.append(row);dump(a.output/'accounting.json',rows)
            print(json.dumps({k:v for k,v in row.items() if k!='source_sha256'}),flush=True)

if __name__=='__main__':main()
