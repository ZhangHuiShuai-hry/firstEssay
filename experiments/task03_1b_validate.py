"""New incremental searches, legacy mathematical replay, node oracle and forgeries."""
import sys,json,time,copy
from pathlib import Path
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'code/dwcg'),str(ROOT/'docs/branch_and_price/task03'),str(ROOT/'docs/branch_and_price')]
from task03 import run
from evidence_store import EvidenceStore,canonical
from incremental_evidence import materialize,certificate_fields
from task03_verify import oracle,verify_tree,verify_node
from run_validation import node_scenarios
from node_master_optimized import solve_node
from node_state import NumericPolicy
from solver_backend import BackendConfig,use_backend
from test_node_cg import small
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);rows=[]
cases=oracle.cases();d=small();d['lines'][0]['required_tasks']=['a','b']
for t in d['lines'][0]['tasks']:t['value']=-2
cases.append(('mandatory_negative',d))
for name,data in cases:
    for version in ('V0','V1','V2','V3'):
        folder=out/(name+'_'+version);folder.mkdir();(folder/'instance.json').write_text(json.dumps(data,indent=2));s=EvidenceStore(folder/'evidence.sqlite')
        tick=time.perf_counter();r=run(data,version,solver='cplex_py',time_limit=30,evidence_sink=s,incremental_evidence=True);s.put(r);hydrated=s.get()
        assert canonical(hydrated)==canonical(materialize(r))
        with use_backend(BackendConfig(name='cplex_py')):v=verify_tree(data,hydrated,solve_oracles=True)
        old=json.loads((ROOT/f'docs/branch_and_price/task03/evidence/sealed_validation/{name}_{version}/result.json').read_text())
        assert r['status']==old['status'] and (r['global_lower_bound'] is None and old['global_lower_bound'] is None or abs(r['global_lower_bound']-old['global_lower_bound'])<1e-5)
        rows.append(dict(case=name,version=version,passed=True,status=r['status'],lb=r['global_lower_bound'],ub=r['global_upper_bound'],seconds=time.perf_counter()-tick,bytes=(folder/'evidence.sqlite').stat().st_size,persistence_components=s.timings))
        s.close();(out/'summary.json').write_text(json.dumps(rows,indent=2));print(name,version,'PASS',flush=True)
nodes=[]
for name,data,restr,parent in node_scenarios():
    for version in ('V1','V2'):
        s=EvidenceStore(out/('node_'+name+'_'+version+'.sqlite'));a=solve_node(data,restr,parent,version=version,solver='cplex_py',deadline=time.perf_counter()+30,incremental_evidence=True)
        n=dict(node_id=0,node_status=a.status,restrictions=restr.to_records(),node_result=a.to_dict(),certificate=certificate_fields(a.certificate));s.put(n);n=s.get();s.close()
        with use_backend(BackendConfig(name='cplex_py')):verify_node(data,n,oracle.enumerate_patterns(data),asdict(NumericPolicy()),True)
        nodes.append(dict(case=name,version=version,passed=True))
(out/'nodes.json').write_text(json.dumps(nodes,indent=2))
faults=[];data=json.loads((out/'two_lines_V2/instance.json').read_text())
for p in (ROOT/'docs/branch_and_price/task03/evidence/sealed_replay').glob('*.json'):
    if p.name=='summary.json':continue
    s=EvidenceStore(out/('forged_'+p.stem+'.sqlite'));s.put(json.loads(p.read_text()));r=s.get();s.close()
    try:verify_tree(data,r,solve_oracles=False)
    except Exception as e:faults.append(dict(case=p.stem,rejected=True,error=str(e)))
    else:raise AssertionError('Accepted forgery '+p.stem)
(out/'faults.json').write_text(json.dumps(faults,indent=2));print('116 new searches,22 nodes,10 forgeries passed')
