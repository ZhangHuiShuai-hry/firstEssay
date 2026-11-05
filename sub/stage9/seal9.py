import json,hashlib,sys,platform
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    path=HERE/'SHA256.json'
    if '--check' in sys.argv:
        rows=json.loads(path.read_text(encoding='utf-8'))
        for p,h in rows.items():assert sha(ROOT/p)==h,p
        print('PASS',len(rows),'hashes');return
    sys.path[:0]=[str(ROOT/'code'),str(ROOT/'code/dwcg')]
    from solver_backend import load_cplex
    from node_state import NumericPolicy
    from dataclasses import asdict
    import pulp
    with (HERE/'ENVIRONMENT.json').open('x',encoding='utf-8') as f:json.dump(dict(baseline='3fa1073f',python=sys.version,pulp=pulp.__version__,cplex=load_cplex().__version__,platform=platform.platform(),numeric_policy=asdict(NumericPolicy()),threads=1,seed=11,gap=0),f,indent=2)
    files=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p!=path]
    files += [ROOT/p for p in ('sub/line_cg.py','sub/validate.py','sub/stage4/bp_verify.py','sub/stage4/line_bp_pricing.py','sub/stage2/stage2_verify.py','code/solver_backend.py','code/milp/model.py','code/dwcg/node_state.py','code/dwcg/bp_solution.py')]
    with path.open('x',encoding='utf-8') as f:json.dump({p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)},f,indent=2)
    print('Sealed',len(files),'files')
if __name__=='__main__':main()
