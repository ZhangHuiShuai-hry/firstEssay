"""Stage11 worker needs an explicit stage9 import path in the new directory."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
worker=(HERE/'worker.py').read_text(encoding='utf-8')
worker=worker.replace("ROOT=HERE.parents[1]","ROOT=HERE.parents[1]\nsys.path.insert(0,str(HERE.parent/'stage9'))")
with (HERE/'worker_v2.py').open('x',encoding='utf-8') as f:f.write(worker)
runner=(HERE/'run_plan.py').read_text(encoding='utf-8').replace("HERE / 'worker.py'","HERE / 'worker_v2.py'").replace("worker='sub/stage11/worker.py'","worker='sub/stage11/worker_v2.py'")
with (HERE/'run_plan_v2.py').open('x',encoding='utf-8') as f:f.write(runner)
verifier=(HERE/'verify11.py').read_text(encoding='utf-8').replace('from run_plan import audit, sha','from run_plan_v2 import audit, sha')
with (HERE/'verify_v2.py').open('x',encoding='utf-8') as f:f.write(verifier)
