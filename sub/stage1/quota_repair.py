"""LP资源用量附近的有限配额补列；只改善LB，不产生全局最优证明。"""
import itertools,json,math,sys,time
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from line_cg import solve_master,solve_line,column_key
from solver_backend import BackendConfig,use_backend

def repair(data,original_pool,time_limit=10,max_calls=8):
    start=time.perf_counter();pool=deepcopy(original_pool);records=[];witness=None
    with use_backend(BackendConfig(name='cplex_py',deadline=start+time_limit)):
        lp=solve_master(data,pool)
        if not lp['solver']['optimal']:return dict(status='unresolved',lp=lp,global_integer_optimal_proven=False)
        for line in data['lines']:
            l=line['id'];averages={r:sum(e['weight']*pool[l][e['column']][r] for e in lp['solution'] if e['line']==l) for r in ('human','robot')}
            caps=sorted(set(itertools.product(*[sorted(set([math.floor(averages[r]+1e-8),math.ceil(averages[r]-1e-8)])) for r in ('human','robot')])))
            for cap in caps:
                if len(records)>=max_calls or time.perf_counter()>=start+time_limit:break
                try:c,cert=solve_line(line,caps=cap,purpose='integer_quota_repair')
                except TimeoutError:break
                records.append(cert)
                if c is not None and column_key(c) not in {column_key(old) for old in pool[l]}:pool[l].append(c)
        try:
            rip=solve_master(data,pool,integer=True);witness=rip['witness']
        except TimeoutError:rip=None
    return dict(status='feasible' if witness else 'no_feasible_found',pool=pool,initial_lp=lp,
                pricing=records,restricted_IP=rip,witness=witness,lower_bound=None if not witness else witness['objective'],
                global_integer_optimal_proven=False,seconds=time.perf_counter()-start)

if __name__=='__main__':
    root=Path(__file__).resolve().parent/'evidence/pool_counterexample'
    d=json.loads((root/'instance.json').read_text());pool=json.loads((root/'restricted_pool.json').read_text())
    result=repair(d,pool)
    from validate import check_column,check_witness
    for line in d['lines']:
        for c in result['pool'][line['id']]:check_column(line,c)
    check_witness(d,result['witness'],result['lower_bound'])
    assert not result['global_integer_optimal_proven']
    with (root/'quota_repair.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(dict(status=result['status'],LB=result['lower_bound'],calls=len(result['pricing']),seconds=result['seconds'])))
