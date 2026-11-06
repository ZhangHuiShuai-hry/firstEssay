import argparse,json,subprocess,sys,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
POLICIES=['exact','short_raw','fixed','adaptive']
def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['small','medium'],required=True);a=p.parse_args()
    dest=HERE/'evidence'/a.stage;dest.mkdir(parents=True,exist_ok=False)
    if a.stage=='small':cases=[(n,ROOT/f'sub/stage7/evidence/validation/{n}_cplex_py/instance.json',20) for n in ('gap','tiny5_original','tiny6_original','lp_yes_ip_no')]
    else:
        assert (HERE/'evidence/small/summary.json').exists() and (HERE/'tests.txt').exists()
        cases=[('n80s32',ROOT/'sub/stage12/evidence/formal600/tasks080_lines04_conflict_candidate_seed32__balanced_bound/instance.json',60)]
        cases += [(f'n120tight{s}',ROOT/f'sub/stage13/evidence/robust180/tasks120_lines06_ratio80_seed{s}__balanced_bound/instance.json',60) for s in (32,34)]
    rows=[]
    for i,(name,source,seconds) in enumerate(cases):
        order=POLICIES[i%4:]+POLICIES[:i%4]
        for policy in order:
            folder=dest/f'{name}_{policy}';args=[sys.executable,str(HERE/'online.py'),str(source),'--output',str(folder),'--seconds',str(seconds),'--policy',policy]
            q=subprocess.run(args,cwd=ROOT,capture_output=True,text=True);(dest/f'{folder.name}.stdout.txt').write_text(q.stdout+q.stderr,encoding='utf-8');assert q.returncode==0,q.stderr
            q=subprocess.run([sys.executable,str(HERE/'audit.py'),str(folder/'instance.json'),str(folder/'result.json.zlib'),'--output',str(folder/'replay.json')]+(['--no-enumeration'] if a.stage=='medium' else []),cwd=ROOT,capture_output=True,text=True)
            (dest/f'{folder.name}.replay.stdout.txt').write_text(q.stdout+q.stderr,encoding='utf-8');assert q.returncode==0,q.stderr
            r=json.loads(zlib.decompress((folder/'result.json.zlib').read_bytes()));row=dict(case=name,**{k:r[k] for k in ('policy_name','status','lower_bound','upper_bound','global_integer_optimal_proven','lp_optimal_proven','native_pricing_calls','candidate_seconds','online_wall_seconds','first_integer_seconds','timing')},candidate_rounds=sum(h.get('candidate_action') is not None for h in r['history']),candidate_added=sum(len(h.get('candidate_added',[])) for h in r['history']),certification_rounds=sum(bool(h['pricing']) for h in r['history']))
            rows.append(row);print(json.dumps(row),flush=True)
    with (dest/'summary.json').open('x') as f:json.dump(rows,f,indent=2)
if __name__=='__main__':main()
