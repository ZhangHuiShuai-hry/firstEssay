import json,os,subprocess,sys,hashlib,shutil
from pathlib import Path
from datetime import datetime,timezone

root=Path(__file__).resolve().parents[1];out=root/'experiments/runs/hybrid_large_01';out.mkdir(exist_ok=False)
(out/'source').mkdir(); paths=[root/'experiments'/s for s in ('hybrid.py','hybrid_cg.py','test_hybrid.py')]
for p in paths:shutil.copy2(p,out/'source'/p.name)
(out/'provenance.json').write_text(json.dumps(dict(start_utc=datetime.now(timezone.utc).isoformat(),source={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},python=sys.executable,threads=1,solver_seed=11,python_hash_seed=11),indent=2))
for n in (120,150):
    for sec in (60,120,180):
        name=f'n{n}_hybrid{sec}';source=root/f'experiments/runs/large_120_150_600_01/instances/total{n}_L2_s11.json'
        print('START',name,datetime.now().isoformat(),flush=True)
        with (out/(name+'.log')).open('w') as log:
            p=subprocess.run([sys.executable,str(root/'experiments/hybrid.py'),str(source),'--out',str(out/name),'--budget','600','--mip-budget',str(sec)],env=dict(os.environ,PYTHONHASHSEED='11'),stdout=log,stderr=subprocess.STDOUT)
        print('DONE',name,p.returncode,datetime.now().isoformat(),flush=True)
        if p.returncode:raise RuntimeError(name)
(out/'finished.json').write_text(json.dumps(dict(end_utc=datetime.now(timezone.utc).isoformat())))
