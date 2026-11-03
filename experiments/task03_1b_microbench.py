"""Fixed columns and duals: interface timings independent of any B&B tree."""
import sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'code/dwcg'),str(ROOT/'code')]
from test_node_cg import small
from common import enumerate_pool,empty_pool
from node_state import NumericPolicy,NodeRestrictions
from node_master_optimized import build_node_master,solve_node_master
from node_incremental_master import NodeIncrementalMaster
from node_persistent_pricing import NodePersistentPricing
from node_pricing import price_node
from solver_backend import BackendConfig,use_backend

out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);d=small();p=NumericPolicy();cfg=BackendConfig(name='cplex_py');r=NodeRestrictions();pool=enumerate_pool(d);rows=[]
with use_backend(cfg):
    dual={k:.3 for k in build_node_master(d,pool,r,1).rows};line=d['lines'][0]
    t=time.perf_counter();pp=NodePersistentPricing(line,1,r,p,cfg);init=time.perf_counter()-t
    for phase in (1,2,1,2):
        t=time.perf_counter();a=price_node(line,1,dual,phase,r,p);legacy=time.perf_counter()-t
        t=time.perf_counter();b=pp.run(dual,phase,None);wall=time.perf_counter()-t
        assert abs(a.certificate.reduced_cost-b.certificate.reduced_cost)<1e-6
        info=b.certificate.solver_result;parts={k:info[k] for k in ('objective_update_time','native_time','read_time')}
        rows.append(dict(kind='PP',phase=phase,legacy=legacy,native_wall=wall,initialization=init if len(rows)==0 else 0.,native_structure_seconds=pp.structure_seconds,native_creation_seconds=pp.native_creation_seconds,parts=parts,residual=wall-sum(parts.values())))
    pp.close();t=time.perf_counter();native=NodeIncrementalMaster(cfg);init=time.perf_counter()-t
    for phase in (1,2):
        t=time.perf_counter();m=build_node_master(d,pool,r,phase);mirror=time.perf_counter()-t
        expected=solve_node_master(m,p)[0]
        t=time.perf_counter();n=build_node_master(d,pool,r,phase);mirror2=time.perf_counter()-t
        t=time.perf_counter();native.sync(n);append=time.perf_counter()-t
        t=time.perf_counter();actual=solve_node_master(n,p)[0];solve=time.perf_counter()-t
        assert abs(actual-expected)<1e-6
        info=n.problem.backend_result
        rows.append(dict(kind='RMP',phase=phase,mirror=mirror2,append=append,native_solve=info['solver_time'],read=info['native_read_seconds'],certificate_check=solve-info['solver_time']-info['native_read_seconds'],init=init if phase==1 else 0.))
    native.close()
(out/'result.json').write_text(json.dumps(rows,indent=2));print('same-pool and same-dual checks passed')
