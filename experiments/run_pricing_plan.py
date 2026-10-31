"""Serial 120/300 s study, gated on successful complete fixed-dual replay."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    replay=ROOT/'experiments/runs/pricing_replay_02/validation.json'
    if not replay.exists() or not json.loads(replay.read_text())['passed']:raise SystemExit('Complete fixed-dual replay must pass first')
    for budget in (120,300):
        out=ROOT/'experiments/runs'/f'persistent_pp_{budget}_02'
        subprocess.run([sys.executable,str(ROOT/'experiments/compare_pricing.py'),
            '--config',str(ROOT/'experiments/configs'/f'persistent_pp_{budget}.json'),'--out',str(out)],cwd=ROOT,check=True)
        rows=json.loads((out/'summary.json').read_text())
        if len(rows)!=30 or any(r['status'] in ('numerical_or_solver_exception','process_timeout_or_exception') for r in rows):
            raise SystemExit('Unexpected incomplete/exception state: audit before continuing')
        if any(r.get('python_hash_seed')!='11' for r in rows):raise SystemExit('Worker hash seed mismatch')
        print('Finished budget',budget,'V1 converged',sum(r['converged'] for r in rows if r['version']=='V1'),
              'V2 converged',sum(r['converged'] for r in rows if r['version']=='V2'),flush=True)
