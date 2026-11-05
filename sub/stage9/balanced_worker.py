"""120秒连续轨迹诊断。预算包括导入/建模/核验/证据写入；Windows软限时。"""
import argparse,hashlib,json,os,subprocess,sys,time,traceback,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(HERE.parent),str(HERE.parent/'stage3'),str(HERE.parent/'stage6'),str(HERE.parent/'stage7'),str(HERE.parent/'stage8')]

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
        else:from balanced_bound import run
        kwargs=dict(pricing='warm',init_seconds=.5,quota=False) if a.worker=='cg' else dict(cg_fraction=.9,cg_cap_seconds=1000000) if a.worker=='balanced_bound' else {}
        observe={} if a.worker=='compact_plain' else dict(progress=progress)
        result=run(data,time_limit=max(.001,a.budget-5-(time.perf_counter()-start)),log_dir=a.output/'logs',**observe,**kwargs)
        if a.worker=='cg':result.update(global_lower_bound=result['lower_bound'],global_upper_bound=result['upper_bound'])
        result['progress_trace']=trace
        tick=time.perf_counter();blob=zlib.compress(json.dumps(result,allow_nan=False).encode())
        with (a.output/'result.json.zlib').open('xb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
        persistence=time.perf_counter()-tick
        source_manifest=json.loads(a.sources.read_bytes()) if a.sources else {}
        summary={k:result.get(k) for k in ('status','global_lower_bound','global_upper_bound','absolute_gap','global_integer_optimal_proven','global_infeasibility_proven','wall_seconds','algorithm_seconds','first_integer_seconds','first_verified_integer_seconds','profile_calls')}
        summary.update(method=a.worker,input_sha256=sha(raw),evidence_sha256=sha(blob),source_sha256=source_manifest,
            persistence_seconds=persistence,evidence_bytes=len(blob),uncompressed_bytes=len(zlib.decompress(blob)),worker_seconds=time.perf_counter()-start,
            settings=dict(budget=a.budget,reserve=5,threads=1,seed=11,solver='CPLEX 22.1.1.0',gap=0,**kwargs))
        dump(a.output/'summary.json',summary)
    except Exception as e:
        dump(a.output/'error.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
