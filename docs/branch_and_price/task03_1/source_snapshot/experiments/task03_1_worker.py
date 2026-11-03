"""One frozen input, externally budgeted process; no generator imports."""
import cProfile,hashlib,json,os,pstats,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'code/dwcg'),str(ROOT/'code')]
from evidence_store import EvidenceStore

def main():
    source,out,version,expected=sys.argv[1:5];deadline=float(sys.argv[5]);out=Path(out)
    raw=Path(source).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Frozen input bytes mismatch')
    data=json.loads(raw);store=EvidenceStore(out/'evidence.sqlite')
    store.put(dict(status='time_limit',input_sha256=expected,global_lower_bound=None,global_upper_bound=None,
                   global_integer_optimal_proven=False,global_infeasibility_proven=False,
                   open_nodes=[dict(node_id=0,status='unresolved',safe_upper_bound=None)],reason='No completed global checkpoint'),'checkpoint')
    from task03 import run
    from common import compact
    from solver_backend import use_backend,BackendConfig,make_solver
    from task03_benchmark import peak_memory
    reserve=max(.5,(deadline-time.perf_counter())*.2)
    search_end=deadline-reserve;started=time.perf_counter();persist_before=store.seconds;profile=cProfile.Profile();profile.enable()
    if version=='Compact':
        with use_backend(BackendConfig(name='cplex_py',deadline=search_end,log_dir=str(out/'native_logs'))):
            m=compact.build_model(data);m.problem.solve(make_solver(role='compact_ip'));result=dict(m.problem.backend_result)
            if result['has_incumbent']:result['solution']=compact.solution_report(m)
    else:
        result=run(data,version,solver='cplex_py',time_limit=max(1e-12,search_end-time.perf_counter()),evidence_sink=store)
    profile.disable();algorithm_end=time.perf_counter();node_persist_seconds=store.seconds-persist_before
    # Full global root is published only after the algorithm returns a coherent tree.
    root_hash=store.put(result)
    persisted=time.perf_counter();stats=pstats.Stats(profile)
    exclusive=[dict(file=k[0],line=k[1],function=k[2],calls=v[1],exclusive=v[2],cumulative=v[3]) for k,v in stats.stats.items()]
    store.put(dict(algorithm_seconds=algorithm_end-started,evidence_total_seconds=store.seconds,
                   final_persist_seconds=persisted-algorithm_end,input_sha256=expected,
                   peak_memory_bytes=peak_memory(),exclusive_profile=exclusive),'metrics')
    keys=('status','global_lower_bound','global_upper_bound','absolute_gap','relative_gap','global_integer_optimal_proven','global_infeasibility_proven','first_integer_seconds','total_nodes_processed','total_pricing_calls','total_columns_generated','objective','best_bound','has_incumbent')
    store.put(dict(result={k:result[k] for k in keys if k in result},result_root_sha256=root_hash,
                   algorithm_seconds=algorithm_end-started,final_persist_seconds=persisted-algorithm_end,
                   node_persist_seconds=node_persist_seconds,algorithm_excluding_node_persistence=algorithm_end-started-node_persist_seconds,
                   evidence_total_seconds=store.seconds,peak_memory_bytes=peak_memory()),'summary')
    store.close()
if __name__=='__main__':main()
