"""独立分解/完整CG/Compact，同输入串行30秒软总预算，2秒收尾。"""
import argparse,hashlib,json,subprocess,sys,time,zlib,traceback
from pathlib import Path
SUB=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SUB))

def write(p,r):p.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def worker(a):
    t=time.perf_counter();a.output.mkdir(parents=True,exist_ok=False)
    raw=a.instance.read_bytes();(a.output/'instance.json').write_bytes(raw);data=json.loads(raw.decode('utf-8-sig'))
    try:
        if a.worker=='independent':from independent_solver import run
        elif a.worker=='line':from line_cg import run
        else:from compact_solver import run
        r=run(data,time_limit=max(.001,a.budget-2-(time.perf_counter()-t)),log_dir=a.output/'logs')
        if a.worker=='line':r.update(global_lower_bound=r['lower_bound'],global_upper_bound=r['upper_bound'],algorithm_seconds=r['wall_seconds'])
        encoded=zlib.compress(json.dumps(r,ensure_ascii=False,allow_nan=False).encode());(a.output/'result.json.zlib').write_bytes(encoded)
        s={k:r.get(k) for k in ('status','global_lower_bound','global_upper_bound','absolute_gap','global_integer_optimal_proven','global_infeasibility_proven','algorithm_seconds','first_integer_seconds')}
        s.update(method=a.worker,input_sha256=hashlib.sha256(raw).hexdigest(),evidence_sha256=hashlib.sha256(encoded).hexdigest(),worker_seconds=time.perf_counter()-t)
        write(a.output/'summary.json',s)
    except Exception as e:
        write(a.output/'error.json',dict(error=repr(e),traceback=traceback.format_exc()));raise

def main():
    p=argparse.ArgumentParser();p.add_argument('--worker',choices=('compact','independent','line'));p.add_argument('--instance',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--budget',type=float,default=30);a=p.parse_args()
    if a.worker:return worker(a)
    a.output.mkdir(parents=True,exist_ok=False);rows=[]
    cases=[SUB/'evidence/inputs_v1'/s for s in ('existing20_original.json','existing40_original.json','tasks040_lines02_seed12.json')]+[SUB/'evidence/stress_inputs_v2/tasks020_resource_H1_R2.json']
    for n,case in enumerate(cases):
        methods=['compact','independent','line'];methods=methods[n%3:]+methods[:n%3]
        for method in methods:
            dest=a.output/(case.stem+'__'+method);tick=time.perf_counter();hard=False
            with (a.output/(dest.name+'.stdout.txt')).open('w',encoding='utf-8') as log:
                proc=subprocess.Popen([sys.executable,__file__,'--worker',method,'--instance',str(case),'--output',str(dest),'--budget',str(a.budget)],stdout=log,stderr=subprocess.STDOUT)
                try:code=proc.wait(timeout=a.budget+5)
                except subprocess.TimeoutExpired:proc.kill();proc.wait();hard=True;code=proc.returncode
            elapsed=time.perf_counter()-tick;s=json.loads((dest/'summary.json').read_text()) if (dest/'summary.json').exists() else {}
            if s:assert s['input_sha256']==hashlib.sha256(case.read_bytes()).hexdigest()
            row=dict(case=case.stem,**s,end_to_end_seconds=elapsed,timely=elapsed<=a.budget and code==0,hard_stop=hard,exit_code=code)
            rows.append(row);write(a.output/'accounting.json',rows);print(json.dumps(row),flush=True)

if __name__=='__main__':main()
