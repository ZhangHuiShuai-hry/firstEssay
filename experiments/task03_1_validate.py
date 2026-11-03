"""Recompute storage equivalence, independent math and fault replays."""
import hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'code/dwcg'),str(ROOT/'docs/branch_and_price/task03')]
from evidence_store import EvidenceStore,canonical
from task03_verify import verify_tree
from solver_backend import use_backend,BackendConfig

def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);rows=[]
    base=ROOT/'docs/branch_and_price/task03/evidence/sealed_validation'
    for f in sorted(base.glob('*/result.json')):
        r=json.loads(f.read_text());data=json.loads((f.parent/'instance.json').read_text());name=f.parent.name
        tick=time.perf_counter();s=EvidenceStore(out/(name+'.sqlite'));s.put(r);write=time.perf_counter()-tick
        tick=time.perf_counter();hydrated=s.get();read=time.perf_counter()-tick;s.close()
        assert canonical(r)==canonical(hydrated)
        tick=time.perf_counter()
        with use_backend(BackendConfig(name='cplex_py')):v=verify_tree(data,hydrated,solve_oracles=True)
        rows.append(dict(case=name,passed=v['passed'],old_bytes=f.stat().st_size,new_bytes=(out/(name+'.sqlite')).stat().st_size,write_seconds=write,read_seconds=read,replay_seconds=time.perf_counter()-tick))
        (out/'summary.json').write_text(json.dumps(rows,indent=2))
    faults=[];data=json.loads((base/'two_lines_V2/instance.json').read_text())
    for f in sorted((ROOT/'docs/branch_and_price/task03/evidence/sealed_replay').glob('*.json')):
        if f.name=='summary.json':continue
        s=EvidenceStore(out/('forged_'+f.stem+'.sqlite'));s.put(json.loads(f.read_text()));r=s.get();s.close()
        try:verify_tree(data,r,solve_oracles=False)
        except Exception as e:faults.append(dict(case=f.stem,rejected=True,error=str(e)))
        else:raise AssertionError('Accepted forged evidence '+f.stem)
    (out/'faults.json').write_text(json.dumps(faults,indent=2));print(len(rows),'lossless full-oracle replays;',len(faults),'faults rejected')
if __name__=='__main__':main()
