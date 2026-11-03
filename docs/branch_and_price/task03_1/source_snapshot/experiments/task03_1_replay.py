"""Full independent replay of either legacy JSON or storage-v3 SQLite."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'code/dwcg'),str(ROOT/'docs/branch_and_price/task03')]
from evidence_store import load_result
from task03_verify import verify_tree
from solver_backend import use_backend,BackendConfig
p=argparse.ArgumentParser();p.add_argument('--instance',type=Path,required=True);p.add_argument('--result',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--offline',action='store_true');a=p.parse_args()
if a.output.exists():raise FileExistsError(a.output)
t=time.perf_counter();r=load_result(a.result);read=time.perf_counter()-t
with use_backend(BackendConfig(name='cplex_py')):v=verify_tree(json.loads(a.instance.read_text()),r,solve_oracles=not a.offline)
v.update(read_seconds=read,total_replay_seconds=time.perf_counter()-t)
with a.output.open('x') as f:json.dump(v,f,indent=2)
print('PASS',v['scope'])
