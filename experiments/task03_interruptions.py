"""Saved native-node interruption certificates, independently replayed offline."""
import json,sys,time
from pathlib import Path
from functools import partial
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code/dwcg'),str(ROOT/'docs/branch_and_price/task03')]
from branch_price_engine import run_branch_price
from node_master_optimized import solve_node
from node_state import NumericPolicy
from test_node_cg import small
from task03_verify import verify_tree,oracle

def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);rows=[]
    for version in ('V1','V2'):
        for name in ('node_limit','root_time_limit','child_time_limit','solver_error','cg_limit','tiny_rc_unclosed'):
            folder=out/(version+'_'+name);folder.mkdir();d=dict(oracle.cases())['two_lines']
            options=dict(solver='cplex_py',output_dir=folder/'tree');base=partial(solve_node,version=version)
            options['_node_solver']=base
            if name=='node_limit':options['node_limit']=1
            if name=='root_time_limit':options['time_limit']=1e-12
            if name=='cg_limit':options['max_cg_iterations']=1
            if name=='child_time_limit':
                calls=[]
                def expire(*args,**kw):
                    if calls:kw['deadline']=time.perf_counter()-1
                    calls.append(True);return base(*args,**kw)
                options['_node_solver']=expire
            if name=='solver_error':
                def fail(*args,**kw):raise RuntimeError('Explicit node API injection')
                options['_node_solver']=fail
            if name=='tiny_rc_unclosed':
                d=small()
                for t in d['lines'][0]['tasks']:
                    t['value']=3e-8
                    for m in t['modes'].values():m['cost']=0
                for s in d['lines'][0]['stations']:s.update(fixed_cost=0,human_cost=0,robot_cost=0)
                options['policy']=NumericPolicy(lp_dual_tolerance=1e-9,global_absolute_tolerance=1e-12,global_relative_tolerance=0)
            r=run_branch_price(d,**options)
            v=verify_tree(d,r,solve_oracles=False)
            assert not r['global_integer_optimal_proven'] and not r['global_infeasibility_proven'] and r['open_nodes']
            for file,data in (('instance.json',d),('result.json',r),('verification.json',v)):(folder/file).write_text(json.dumps(data,indent=2))
            rows.append(dict(version=version,case=name,status=r['status'],lb=r['global_lower_bound'],ub=r['global_upper_bound'],gap=r['absolute_gap'],open_nodes=len(r['open_nodes']),check='PASS'))
    (out/'summary.json').write_text(json.dumps(rows,indent=2));print(len(rows),'interruption certificates passed')
if __name__=='__main__':main()
