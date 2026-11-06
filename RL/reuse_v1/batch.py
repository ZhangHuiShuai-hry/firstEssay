"""Serial same-engine cache-off/on comparison; no historical result overwritten."""
import json,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]

def main():
    rows=[];dest=HERE/'evidence/paired';dest.mkdir(parents=True,exist_ok=False)
    cases=[('tiny5',ROOT/'sub/stage7/evidence/validation/tiny5_original_cplex_py/instance.json',20,True),
           ('tiny6',ROOT/'sub/stage7/evidence/validation/tiny6_original_cplex_py/instance.json',20,True),
           ('lp_yes_ip_no',ROOT/'sub/stage7/evidence/validation/lp_yes_ip_no_cplex_py/instance.json',20,True),
           ('n80s32',ROOT/'sub/stage12/evidence/formal600/tasks080_lines04_conflict_candidate_seed32__balanced_bound/instance.json',60,False),
           ('n120tight32',ROOT/'sub/stage13/evidence/robust180/tasks120_lines06_ratio80_seed32__balanced_bound/instance.json',60,False)]
    for ci,(name,path,seconds,enum) in enumerate(cases):
        for reuse in ([False,True] if ci%2==0 else [True,False]):
            folder=dest/f'{name}_{"reuse" if reuse else "base"}'
            args=[sys.executable,str(HERE/'online.py'),str(path),'--output',str(folder),'--seconds',str(seconds)]+([] if reuse else ['--no-reuse'])
            p=subprocess.run(args,cwd=ROOT,capture_output=True,text=True)
            (dest/f'{folder.name}.stdout.txt').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,p.stderr
            args=[sys.executable,str(HERE/'audit_online.py'),str(folder/'instance.json'),str(folder/'result.json.zlib'),'--output',str(folder/'replay.json')]+([] if enum else ['--no-enumeration'])
            a=subprocess.run(args,cwd=ROOT,capture_output=True,text=True)
            (dest/f'{folder.name}.replay.stdout.txt').write_text(a.stdout+a.stderr,encoding='utf-8');assert a.returncode==0,a.stderr
            import zlib
            r=json.loads(zlib.decompress((folder/'result.json.zlib').read_bytes()))
            row=dict(case=name,reuse=reuse,**{k:r[k] for k in ('status','lower_bound','upper_bound','screened_pricing_calls','native_pricing_calls','online_wall_seconds','global_integer_optimal_proven')})
            rows.append(row);print(json.dumps(row),flush=True)
    with (dest/'summary.json').open('x') as f:json.dump(rows,f,indent=2)
if __name__=='__main__':main()
