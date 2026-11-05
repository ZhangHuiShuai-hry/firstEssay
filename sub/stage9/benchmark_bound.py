"""中大规模配对：复用阶段8已审计worker，不改算法或物理模型。"""
import argparse,hashlib,importlib.util,json,os,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'stage8'))
spec=importlib.util.spec_from_file_location('stage8_budget_worker',HERE/'bound_worker.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
dump=previous.dump
sha=previous.sha

def freeze_sources(folder):
    start=time.perf_counter();paths=[]
    for directory in (ROOT/'sub',ROOT/'code'):
        for base,dirs,files in os.walk(directory):
            dirs[:]=[d for d in dirs if d not in ('evidence','__pycache__','.venv')]
            paths.extend(Path(base)/n for n in files if n.endswith('.py'))
    paths.append(ROOT/'experiments/generate_instances.py')
    source=folder/'sources.json';dump(source,{str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(set(paths))})
    dump(folder/'preparation.json',dict(source_freeze_seconds=time.perf_counter()-start,scope='shared_pre_run_preparation'))
    return source

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--worker',choices=['compact_plain','economic_bound']);p.add_argument('--instance',type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--sources',type=Path);p.add_argument('--budget',type=float,default=120);p.add_argument('--suite',choices=['pilot','confirm'],default='pilot');a=p.parse_args()
    if a.worker:return previous.worker(a)
    a.output.mkdir(parents=True,exist_ok=False);sources=freeze_sources(a.output)
    names=['tasks060_lines02_r90_seed21.json','tasks080_lines02_r90_seed21.json']
    if a.suite=='pilot':names.append('tasks060_lines02_r50_seed21.json')
    frozen=a.output/'inputs';frozen.mkdir();rows=[]
    for n,name in enumerate(names):
        case=HERE/'evidence/inputs'/name;target=frozen/name;target.write_bytes(case.read_bytes())
        methods=['compact_plain','economic_bound'] if n%2==0 else ['economic_bound','compact_plain']
        for method in methods:
            dest=a.output/(case.stem+'__'+method);tick=time.perf_counter();hard=False
            with (a.output/(dest.name+'.stdout.txt')).open('w',encoding='utf-8') as log:
                proc=subprocess.Popen([sys.executable,__file__,'--worker',method,'--instance',str(target),'--output',str(dest),'--budget',str(a.budget),'--sources',str(sources)],stdout=log,stderr=subprocess.STDOUT)
                try:code=proc.wait(timeout=a.budget+5)
                except subprocess.TimeoutExpired:proc.kill();proc.wait();hard=True;code=proc.returncode
            elapsed=time.perf_counter()-tick
            summary=json.loads((dest/'summary.json').read_bytes()) if (dest/'summary.json').exists() else {}
            if summary:assert summary['input_sha256']==sha(target.read_bytes())
            row=dict(case=case.stem,**summary,end_to_end_seconds=elapsed,timely=elapsed<=a.budget and code==0,hard_stop=hard,exit_code=code)
            rows.append(row);dump(a.output/'accounting.json',rows)
            print(json.dumps({k:v for k,v in row.items() if k!='source_sha256'}),flush=True)

if __name__=='__main__':main()
