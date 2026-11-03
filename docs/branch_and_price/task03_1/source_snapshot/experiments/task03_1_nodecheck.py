import json,sys
from pathlib import Path
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'code/dwcg'),str(ROOT/'docs/branch_and_price/task03')]
from evidence_store import EvidenceStore
from task03_verify import verify_node,oracle
from node_state import NumericPolicy
from solver_backend import BackendConfig,use_backend

out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);rows=[]
for f in sorted((ROOT/'docs/branch_and_price/task03/evidence/sealed_validation').glob('node_*/node.json')):
    d=json.loads((f.parent/'instance.json').read_text());n=json.loads(f.read_text());s=EvidenceStore(out/(f.parent.name+'.sqlite'));s.put(n);r=s.get();s.close()
    assert r==n
    with use_backend(BackendConfig(name='cplex_py')):v=verify_node(d,r,oracle.enumerate_patterns(d),asdict(NumericPolicy()),True)
    rows.append(dict(case=f.parent.name,passed=True))
(out/'summary.json').write_text(json.dumps(rows,indent=2));print(len(rows),'node full-oracle replays passed')
