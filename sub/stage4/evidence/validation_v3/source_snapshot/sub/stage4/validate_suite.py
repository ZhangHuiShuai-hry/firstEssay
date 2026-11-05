"""完整小实例交叉验证及安全停止证据；生产搜索不枚举。"""
import json,sys,zlib,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'stage1')]
from branch_price import run
from bp_verify import audit
from compact_solver import run as compact_run
from gap_case import instance as gap
from cases import lp_yes_ip_no
from find_cases import instance as random_instance

def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def main():
    out=Path(sys.argv[1]) if len(sys.argv)>1 else HERE/'evidence/validation'
    out.mkdir(exist_ok=False)
    sources=list(HERE.glob('*.py'))+[HERE.parent/'line_cg.py',HERE.parent/'stage2/stage2_verify.py',HERE.parent/'validate.py',HERE.parents[1]/'code/milp/model.py',HERE.parents[1]/'code/solver_backend.py']
    hashes={p.relative_to(HERE.parents[1]).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    write(out/'SOURCE_SHA256.json',hashes)
    for p in sources:
        target=out/'source_snapshot'/p.relative_to(HERE.parents[1]);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
    datasets={name:json.loads((HERE.parent/'evidence/inputs_v1'/filename).read_bytes())
              for name,filename in [('tiny5','tiny5_original.json'),('tiny6','tiny6_original.json')]}
    datasets.update(gap=gap(),lp_yes_ip_no=lp_yes_ip_no(),pool_original=json.loads((HERE.parent/'stage1/evidence/pool_counterexample/instance.json').read_bytes()))
    datasets.update({f'random_{seed}':random_instance(seed) for seed in range(12)})
    rows=[]
    for name,d in datasets.items():
        for backend in ('cplex_py','cbc'):
            folder=out/f'{name}_{backend}';folder.mkdir();write(folder/'instance.json',d)
            r=run(d,time_limit=15,solver=backend,log_dir=folder/'logs')
            (folder/'result.json.zlib').write_bytes(zlib.compress(json.dumps(r).encode()))
            checked=audit(d,r);write(folder/'verification.json',checked)
            direct=compact_run(d,time_limit=15,solver=backend,log_dir=folder/'compact_logs');write(folder/'compact.json',direct)
            if direct['global_integer_optimal_proven']:
                assert r['global_integer_optimal_proven'];assert abs(r['global_lower_bound']-direct['global_lower_bound'])<1e-5
            elif direct['global_infeasibility_proven']:assert r['global_infeasibility_proven']
            else:raise AssertionError(('Compact unresolved',name,backend,direct['status']))
            row=dict(case=name,solver=backend,status=r['status'],LB=r['global_lower_bound'],UB=r['global_upper_bound'],
                     nodes=r['total_nodes_created'],seconds=r['wall_seconds'],pricing_calls=r['total_pricing_calls'],
                     compact_status=direct['status'],oracle=checked['full'],verification='PASS')
            rows.append(row);print(json.dumps(row),flush=True)
    for label,opts in [('node_limit',dict(node_limit=1)),('time_limit',dict(time_limit=1e-9)),('iteration_limit',dict(max_iterations=1))]:
        folder=out/label;folder.mkdir();write(folder/'instance.json',gap())
        r=run(gap(),**opts);checked=audit(gap(),r)
        assert not r['global_integer_optimal_proven'] and r['open_nodes']
        (folder/'result.json.zlib').write_bytes(zlib.compress(json.dumps(r).encode()));write(folder/'verification.json',checked)
        rows.append(dict(case=label,status=r['status'],LB=r['global_lower_bound'],UB=r['global_upper_bound'],verification='PASS'))
    write(out/'summary.json',rows)
    assert all(hashlib.sha256((HERE.parents[1]/p).read_bytes()).hexdigest()==h for p,h in hashes.items()),'Runtime source changed'
    print('PASS',len(rows),'saved trees')

if __name__=='__main__':main()
