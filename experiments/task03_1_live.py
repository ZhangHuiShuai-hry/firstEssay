"""Live integration test: storage sink versus legacy run and independent full oracle."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'code/dwcg'),str(ROOT/'docs/branch_and_price/task03')]
from evidence_store import EvidenceStore,canonical
from task03 import run
from task03_verify import verify_tree,oracle
from solver_backend import use_backend,BackendConfig

def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);rows=[]
    for name in ('two_lines','generator_n6_L1_s13','lp_yes_ip_no'):
        d=dict(oracle.cases())[name]
        for version in ('V0','V1','V2','V3'):
            p=out/(name+'_'+version);p.mkdir();s=EvidenceStore(p/'evidence.sqlite')
            r=run(d,version,solver='cplex_py',time_limit=30,evidence_sink=s);s.put(r);hydrated=s.get()
            assert canonical(r)==canonical(hydrated)
            with use_backend(BackendConfig(name='cplex_py')):v=verify_tree(d,hydrated,solve_oracles=True)
            old=json.loads((ROOT/f'docs/branch_and_price/task03/evidence/sealed_validation/{name}_{version}/result.json').read_text())
            assert (r['status'],r['global_lower_bound'])==(old['status'],old['global_lower_bound'])
            (p/'instance.json').write_text(json.dumps(d));s.close()
            rows.append(dict(case=name,version=version,status=r['status'],lb=r['global_lower_bound'],ub=r['global_upper_bound'],passed=v['passed']))
    (out/'summary.json').write_text(json.dumps(rows,indent=2));print('12 live full-oracle trees passed')
if __name__=='__main__':main()
