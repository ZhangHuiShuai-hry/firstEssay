"""Small independent validation gate; no performance runs before this passes."""
import json,sys,time
from pathlib import Path
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code/dwcg'),str(ROOT/'docs/branch_and_price'),str(ROOT/'docs/branch_and_price/task03')]
from task03 import run
from task03_verify import oracle,verify_tree,verify_node
from run_validation import node_scenarios
from node_master_optimized import solve_node
from node_state import NumericPolicy
from solver_backend import BackendConfig,use_backend

def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);rows=[]
    cases=oracle.cases()
    from test_node_cg import small
    d=small();d['lines'][0]['required_tasks']=['a','b']
    for t in d['lines'][0]['tasks']:t['value']=-2
    cases.append(('mandatory_negative',d))
    for name,data in cases:
        for version in ('V0','V1','V2','V3'):
            folder=out/(name+'_'+version);folder.mkdir()
            (folder/'instance.json').write_text(json.dumps(data,indent=2))
            r=run(data,version,solver='cplex_py',time_limit=30,output_dir=folder/'tree')
            (folder/'result.json').write_text(json.dumps(r,indent=2))
            try:
                with use_backend(BackendConfig(name='cplex_py')):v=verify_tree(data,r,solve_oracles=True)
                assert r['status'] in ('optimal_within_tolerance','infeasible_proven')
                status='PASS';error=None
                (folder/'verification.json').write_text(json.dumps(v,indent=2))
            except Exception as e:status='FAIL';error=repr(e)
            rows.append(dict(case=name,version=version,check=status,error=error,status=r['status'],lb=r['global_lower_bound'],ub=r['global_upper_bound'],gap=r['absolute_gap'],seconds=r['wall_time'],nodes=r['total_nodes_processed'],pricing=r['total_pricing_calls']))
            (out/'summary.json').write_text(json.dumps(rows,indent=2))
            print(name,version,status,flush=True)
    for name,data,restr,parent in node_scenarios():
        for version in ('V1','V2'):
            folder=out/('node_'+name+'_'+version);folder.mkdir()
            r=solve_node(data,restr,parent,version=version,solver='cplex_py',deadline=time.perf_counter()+30,log_dir=folder/'logs')
            n=dict(node_id=0,node_status=r.status,restrictions=restr.to_records(),node_result=r.to_dict(),certificate=asdict(r.certificate))
            (folder/'instance.json').write_text(json.dumps(data));(folder/'node.json').write_text(json.dumps(n,indent=2))
            try:
                with use_backend(BackendConfig(name='cplex_py')):v=verify_node(data,n,oracle.enumerate_patterns(data),asdict(NumericPolicy()),True)
                (folder/'verification.json').write_text(json.dumps(v,indent=2));status='PASS';err=None
            except Exception as e:status='FAIL';err=repr(e)
            rows.append(dict(case='node_'+name,version=version,check=status,error=err));(out/'summary.json').write_text(json.dumps(rows,indent=2))
    return 0 if all(r['check']=='PASS' for r in rows) else 1
if __name__=='__main__':raise SystemExit(main())
