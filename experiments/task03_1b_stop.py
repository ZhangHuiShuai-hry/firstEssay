"""Kill our worker after a committed round. This is not a search-resume test."""
import sys,time,subprocess,sqlite3,json,hashlib,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code/dwcg'))
from evidence_store import EvidenceStore
from search_checkpoint import resume_search
source=ROOT/'docs/branch_and_price/task03_1b/evidence/pilot30/n20_s11.json';out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
start=time.perf_counter();digest=hashlib.sha256(source.read_bytes()).hexdigest()
with (out/'worker.txt').open('w') as log:
    p=subprocess.Popen([sys.executable,str(ROOT/'experiments/task03_1b_worker.py'),str(source),str(out.resolve()),'V2',digest,str(start+120),str(start)],stdout=log,stderr=log)
    rounds=0
    while time.perf_counter()-start<20 and p.poll() is None:
        if (out/'evidence.sqlite').exists():
            try:
                c=sqlite3.connect(str(out/'evidence.sqlite'),timeout=.01);rounds=c.execute("SELECT count(*) FROM roots WHERE kind='pricing_round'").fetchone()[0];c.close()
            except sqlite3.Error:pass
        if rounds:break
        time.sleep(.05)
    stopped=p.poll() is None
    if stopped:p.kill()
    p.wait()
s=EvidenceStore(out/'evidence.sqlite');checkpoint=s.get('checkpoint');s.close()
assert rounds>0 and stopped and not checkpoint['global_integer_optimal_proven'] and not checkpoint['global_infeasibility_proven']
try:resume_search(checkpoint)
except NotImplementedError:resume='NOT IMPLEMENTED'
else:raise AssertionError('Unsafe full search resume accepted')
(out/'result.json').write_text(json.dumps(dict(passed=True,rounds_observed=rounds,hard_stop=True,checkpoint=checkpoint,full_search_resume=resume,elapsed=time.perf_counter()-start),indent=2));print('PASS: safe checkpoint after forced stop; full search resume NOT IMPLEMENTED')
