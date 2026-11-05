"""最终源码/证据快照；历史清单只读核验。"""
import hashlib,json,platform,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    manifest=HERE/'SHA256.json'
    if '--check' in sys.argv:
        records=json.loads(manifest.read_text(encoding='utf-8'))
        for p,h in records.items():assert sha(ROOT/p)==h,p
        print('PASS:',len(records),'hashes');return
    sys.path[:0]=[str(ROOT/'code'),str(ROOT/'code/dwcg')]
    import pulp
    from solver_backend import load_cplex
    from node_state import NumericPolicy
    from dataclasses import asdict
    meta=dict(baseline='760819d0',branch='codex/sub-line-decomposition',python=sys.version,
              pulp=pulp.__version__,cplex=load_cplex().__version__,platform=platform.platform(),
              threads=1,seed=11,gap=0,numeric_policy=asdict(NumericPolicy()),
              note='Runtime source hashes also stored per worker; no main merge.')
    with (HERE/'ENVIRONMENT.json').open('x',encoding='utf-8') as f:json.dump(meta,f,indent=2)
    files=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p!=manifest]
    # 封存原入口和验证器的依赖，确保旧文件未改。
    files += [ROOT/p for p in ('sub/line_cg.py','sub/stage2/solver.py','sub/stage2/stage2_verify.py',
        'sub/validate.py','code/milp/model.py','code/solver_backend.py','code/dwcg/bp_solution.py')]
    with manifest.open('x',encoding='utf-8') as f:json.dump({p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)},f,indent=2)
    print('Sealed',len(files),'files')

if __name__=='__main__':main()
