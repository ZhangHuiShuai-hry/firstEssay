"""Fixed-budget sequential paired scout; all failures and unknown bounds retained."""
import json,sys,time,traceback,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code/dwcg'),str(ROOT/'experiments')]
from task03 import run
from generate_instances import generate
from common import compact
from solver_backend import BackendConfig,use_backend,make_solver,load_cplex

def peak_memory():
    try:
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ('peak','working','p1','p2','n1','n2','page','peakpage')]
        c=Counters();c.cb=ctypes.sizeof(c)
        ctypes.windll.kernel32.GetCurrentProcess.restype=ctypes.c_void_p
        if not ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(ctypes.windll.kernel32.GetCurrentProcess()),ctypes.byref(c),c.cb):return None
        return c.peak
    except Exception:return None

def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
    stage=sys.argv[2];budget=float(sys.argv[3])
    specs=[(int(sys.argv[4]),int(sys.argv[5]))] if stage=='worker' else [(10,11),(20,11)] if stage=='scout' else [(n,s) for n in (20,30,40) for s in (11,21,31,41,51)]
    rows=[];native=load_cplex().Cplex();native.end()
    (out/'config.json').write_text(json.dumps(dict(budget=budget,stage=stage,threads=1,seed=11,specs=specs),indent=2))
    for idx,(n,seed) in enumerate(specs):
        data,_=generate(n=n,lines=2,seed=seed)
        (out/f'input_n{n}_s{seed}.json').write_text(json.dumps(data,indent=2))
        order=[sys.argv[6]] if stage=='worker' else ['V0','V1','V2','V3','Compact']
        if idx%2:order.reverse()
        for version in order:
            if stage!='worker':
                child=out/f'arm_n{n}_s{seed}_{version}'
                with (out/f'arm_n{n}_s{seed}_{version}.txt').open('w') as log:
                    proc=subprocess.Popen([sys.executable,__file__,str(child),'worker',str(budget),str(n),str(seed),version],stdout=log,stderr=log,env=dict(os.environ,PYTHONHASHSEED='11'))
                    try:proc.wait(timeout=budget+20)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait()
                if (child/'summary.json').exists():rows.extend(json.loads((child/'summary.json').read_text()))
                else:rows.append(dict(n=n,seed=seed,version=version,status='process_timeout_or_error',lb=None,ub=None,budget=budget))
                (out/'summary.json').write_text(json.dumps(rows,indent=2))
                print(n,seed,version,rows[-1]['status'],flush=True)
                continue
            folder=out/f'n{n}_s{seed}_{version}';folder.mkdir();t=time.perf_counter()
            try:
                if version=='Compact':
                    with use_backend(BackendConfig(name='cplex_py',deadline=t+budget,log_dir=str(folder/'logs'))):
                        m=compact.build_model(data);m.problem.solve(make_solver(role='compact_ip'));r=dict(m.problem.backend_result)
                    row=dict(status=r['status'],lb=r['objective'],ub=r['best_bound'],nodes=None,pricing=None,first_integer_seconds=None)
                    if r['has_incumbent']:
                        sol=compact.solution_report(m);assert sol['has_feasible_solution'];r['solution']=sol
                else:
                    r=run(data,version,solver='cplex_py',time_limit=budget,node_limit=10000,output_dir=folder/'tree')
                    row=dict(status=r['status'],lb=r['global_lower_bound'],ub=r['global_upper_bound'],nodes=r['total_nodes_processed'],pricing=r['total_pricing_calls'],first_integer_seconds=r['first_integer_seconds'])
                (folder/'result.json').write_text(json.dumps(r,indent=2))
            except Exception as e:
                row=dict(status='solver_error',lb=None,ub=None,error=traceback.format_exc());(folder/'failure.json').write_text(json.dumps(row,indent=2))
            row.update(n=n,seed=seed,version=version,budget=budget,seconds=time.perf_counter()-t)
            row['peak_process_memory_bytes']=peak_memory()
            row['overrun']=max(0,row['seconds']-budget)
            lo,up=row['lb'],row['ub'];row['absolute_gap']=None if lo is None or up is None else up-lo
            row['relative_gap']=None if lo is None or up is None else max(0,up-lo)/max(1,abs(lo))
            rows.append(row);(out/'summary.json').write_text(json.dumps(rows,indent=2))
            print(n,seed,version,row['status'],lo,up,round(row['seconds'],2),flush=True)
    return 0
if __name__=='__main__':raise SystemExit(main())
