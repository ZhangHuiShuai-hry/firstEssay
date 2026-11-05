import json,hashlib,sys,platform
from pathlib import Path
from dataclasses import asdict
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    path=HERE/'SHA256.json'
    if '--check' in sys.argv:
        records=json.loads(path.read_text(encoding='utf-8'))
        for p,h in records.items():assert sha(ROOT/p)==h,p
        print('PASS',len(records),'hashes');return
    sys.path[:0]=[str(ROOT/'code'),str(ROOT/'code/dwcg')]
    from solver_backend import load_cplex
    from node_state import NumericPolicy
    import pulp
    meta=dict(baseline='51aca487',branch='codex/sub-line-decomposition',python=sys.version,
              pulp=pulp.__version__,cplex=load_cplex().__version__,cbc_path=pulp.PULP_CBC_CMD().path,
              platform=platform.platform(),threads=1,seed=11,mip_gap=0,numeric_policy=asdict(NumericPolicy()))
    with (HERE/'ENVIRONMENT.json').open('x',encoding='utf-8') as f:json.dump(meta,f,indent=2)
    files=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p!=path]
    files += [ROOT/p for p in ['code/dwcg/common.py','code/dwcg/node_state.py','code/dwcg/bp_solution.py',
        'code/milp/model.py','code/solver_backend.py','sub/line_cg.py','sub/validate.py',
        'sub/stage2/stage2_verify.py','sub/compact_solver.py','sub/stage1/find_cases.py','sub/stage1/gap_case.py']]
    with path.open('x',encoding='utf-8') as f:json.dump({p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)},f,indent=2)
    print('Sealed',len(files),'files')
if __name__=='__main__':main()
